"""
duty_pump.py — Pipeline Duty Pump with Operating Point Solver
MORBION SCADA v02

KEY FIX FROM v01:
  v01 used pure affinity laws ignoring pipeline system curve.
  v02 solves the operating point every scan.

Pipeline system curve:
    H_static  = elevation head (50m of petroleum product)
    k_sys     = Darcy-Weisbach coefficient for 15km pipeline
    H_sys(Q)  = H_static + k_sys × Q²

  At nominal conditions (450 m³/hr, SG=0.85):
    H_friction ≈ 5.09 bar
    H_elevation ≈ 4.17 bar
    H_total ≈ 9.26 bar
    Pump rated head = 46 bar — plenty of margin

  Outlet pressure:
    P_outlet = P_inlet + pump_head - H_friction - H_elevation
             ≈ 2.0 + 46.0 - 5.09 - 4.17 = 38.7 bar nominal

Physics:
    Petroleum product density: ρ = SG × 1000 = 850 kg/m³
    Pump curve in bar not metres (petroleum, not water)
    Head conversion: H_bar = H_m × ρ × g / 1e5

    Motor: 6600V three-phase high voltage
    I_rated = P_rated / (√3 × 6600 × PF × η_motor)
"""

import math
import random


class DutyPump:

    def __init__(self, config: dict):
        cfg      = config["duty_pump"]
        pipe_cfg = config["pipeline"]

        # Nameplate
        self._N_rated = cfg["rated_speed_rpm"]
        self._Q_rated = cfg["rated_flow_m3hr"] / 3600.0     # m³/s
        self._H_rated = cfg["rated_head_bar"]                # bar
        self._eta     = cfg["rated_efficiency"]
        self._tau     = cfg["tau"]
        self._SG      = cfg["specific_gravity"]
        self._rho     = self._SG * 1000.0                   # kg/m³

        # Pipeline geometry
        self._D    = pipe_cfg["diameter_m"]
        self._L    = pipe_cfg["length_m"]
        self._f    = pipe_cfg["friction_factor"]
        self._elev = pipe_cfg["elevation_m"]
        self._A    = math.pi / 4.0 * self._D ** 2

        # Static head in bar (elevation loss for petroleum product)
        self._H_static_bar = (self._rho * 9.81 * self._elev) / 1e5

        # Darcy-Weisbach system curve coefficient in bar/(m³/s)²
        # H_friction_bar = k_sys × Q²
        if self._A > 0:
            self._k_sys = (self._f * (self._L / self._D) *
                           self._rho / (2.0 * self._A ** 2)) / 1e5
        else:
            self._k_sys = 0.0

        # Rated power and motor current
        # P_shaft = ρ × g × Q × H_m / η
        # H_m = H_bar × 1e5 / (ρ × g)
        H_rated_m = self._H_rated * 1e5 / (self._rho * 9.81)
        self._P_rated_kW = (self._rho * 9.81 *
                            self._Q_rated * H_rated_m) / (self._eta * 1000.0)
        self._I_rated_A  = self._P_rated_kW * 1000.0 / (
                            math.sqrt(3) * 6600.0 * 0.90 * 0.95)

        # State
        self.speed_rpm:  float = 0.0
        self.flow_m3hr:  float = 0.0
        self.head_bar:   float = 0.0
        self.power_kW:   float = 0.0
        self.current_A:  float = 0.0
        self.running:    bool  = False
        self.fault:      bool  = False

        self._speed_setpoint: float = 0.0

    def set_speed(self, rpm: float):
        self._speed_setpoint = max(0.0, min(rpm, self._N_rated))

    def start(self):
        self.running = True

    def stop(self):
        self.running         = False
        self._speed_setpoint = 0.0

    def update(self, dt: float, state):
        if self.fault:
            self._write_state(state)
            return

        # Speed dynamics
        if not self.running:
            self.speed_rpm = max(
                0.0, self.speed_rpm - (self._N_rated / self._tau) * dt)
        else:
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))

        ratio = self.speed_rpm / self._N_rated if self._N_rated > 0 else 0.0

        if ratio < 0.01:
            self.flow_m3hr = 0.0
            self.head_bar  = 0.0
            self.power_kW  = 0.0
            self.current_A = 0.0
            self._write_state(state)
            return

        # Pump curve at current speed (in bar)
        Q_max     = self._Q_rated * ratio
        H_shutoff = self._H_rated * ratio ** 2

        # Solve operating point analytically
        # H_shutoff × (1 - Q²/Q_max²) = H_static + k_sys × Q²
        # Q² = (H_shutoff - H_static) / (H_shutoff/Q_max² + k_sys)
        numerator   = H_shutoff - self._H_static_bar
        denominator = (H_shutoff / (Q_max ** 2) + self._k_sys) if Q_max > 0 else 1.0

        if numerator <= 0 or denominator <= 0:
            Q_m3s = 0.0
        else:
            Q_m3s = math.sqrt(numerator / denominator)
            Q_m3s = max(0.0, min(Q_m3s, Q_max))

        # Head at operating point
        self.head_bar = self._H_static_bar + self._k_sys * Q_m3s ** 2

        # Power and current
        self.flow_m3hr = Q_m3s * 3600.0
        self.power_kW  = self._P_rated_kW * ratio ** 3
        self.current_A = self._I_rated_A  * ratio ** 2

        # Noise
        self.flow_m3hr = max(0.0, self.flow_m3hr + random.gauss(0, 1.5))
        self.head_bar  = max(0.0, self.head_bar  + random.gauss(0, 0.05))
        self.current_A = max(0.0, self.current_A + random.gauss(0, 0.2))

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.duty_pump_speed_rpm = self.speed_rpm
            state.duty_pump_running   = self.running
            state.duty_pump_fault     = self.fault
            state.duty_pump_current_A = self.current_A
            state.duty_pump_power_kW  = self.power_kW
            state.duty_pump_head_bar  = self.head_bar
            state.flow_rate_m3hr      = self.flow_m3hr
            if self._A > 0:
                state.flow_velocity_ms = (self.flow_m3hr / 3600.0) / self._A
