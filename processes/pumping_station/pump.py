"""
pump.py — Centrifugal Pump with Operating Point Solver
MORBION SCADA v02

KEY FIX FROM v01:
  v01 used pure affinity laws — pump delivered rated flow regardless
  of what it was pumping against. System curve was ignored entirely.

  v02 solves the operating point every scan:
    Pump curve:   H_pump(Q) = H_shutoff × (1 - (Q/Q_max)²)
    System curve: H_sys(Q)  = H_static + k_sys × Q²
    Operating point: where H_pump(Q) = H_sys(Q)
    Solved analytically — one quadratic equation.

  This means:
    - If outlet valve closes → system resistance rises → Q drops, H rises
    - If tank fills (higher static head) → Q drops
    - If pump speed drops → both curves shift → new operating point
    - Power and current derived from actual operating Q, not rated Q

Physics:
    Affinity laws from rated point at current speed ratio:
        Q_max    = Q_rated × ratio
        H_shutoff= H_rated × ratio²
        P_rated  = P_rated × ratio³  (shaft power)
        I_rated  = I_rated × ratio²  (motor current)

    System curve:
        H_static  = static head (tank elevation above pump)
        k_sys     = f × (L/D) / (2g × A²)
        H_sys(Q)  = H_static + k_sys × Q²

    Operating point (analytical solution):
        H_shutoff × (1 - Q²/Q_max²) = H_static + k_sys × Q²
        H_shutoff - H_shutoff/Q_max² × Q² = H_static + k_sys × Q²
        H_shutoff - H_static = Q² × (H_shutoff/Q_max² + k_sys)
        Q² = (H_shutoff - H_static) / (H_shutoff/Q_max² + k_sys)
        Q  = sqrt(Q²)  if Q² > 0 else 0

    Discharge pressure:
        P = ρ × g × H_operating / 1e5  [bar]
"""

import math
import random


class Pump:

    def __init__(self, config: dict):
        cfg = config["pump"]

        self._N_rated   = cfg["rated_speed_rpm"]
        self._Q_rated   = cfg["rated_flow_m3hr"] / 3600.0   # m³/s
        self._H_rated   = cfg["rated_head_m"]               # metres
        self._eta       = cfg["rated_efficiency"]
        self._tau       = cfg["tau"]
        self._D         = cfg["pipe_diameter_m"]
        self._L         = cfg["pipe_length_m"]
        self._f         = cfg["friction_factor"]
        self._H_static  = cfg["static_head_m"]
        self._A_pipe    = math.pi / 4.0 * self._D ** 2

        # System curve resistance coefficient
        # H_sys(Q) = H_static + k_sys × Q²  [Q in m³/s, H in metres]
        if self._A_pipe > 0:
            self._k_sys = self._f * (self._L / self._D) / (
                          2.0 * 9.81 * self._A_pipe ** 2)
        else:
            self._k_sys = 0.0

        # Rated shaft power and motor current
        self._P_rated_kW = (1000.0 * 9.81 * self._Q_rated * self._H_rated) / (
                            self._eta * 1000.0)
        self._I_rated_A  = self._P_rated_kW * 1000.0 / (
                            math.sqrt(3) * 400.0 * 0.88 * 0.92)

        # State
        self.speed_rpm:    float = 0.0
        self.flow_m3hr:    float = 0.0
        self.head_m:       float = 0.0
        self.power_kW:     float = 0.0
        self.current_A:    float = 0.0
        self.pressure_bar: float = 0.0
        self.running:      bool  = False
        self.fault:        bool  = False

        self._speed_setpoint: float = 0.0
        self._starts_today:   int   = 0

    def set_speed(self, rpm: float):
        self._speed_setpoint = max(0.0, min(rpm, self._N_rated))

    def start(self):
        if not self.running:
            self.running       = True
            self._starts_today += 1

    def stop(self):
        self.running          = False
        self._speed_setpoint  = 0.0

    def update(self, dt: float, state):
        if self.fault:
            self._write_state(state)
            return

        # Speed dynamics — first order lag
        if not self.running:
            self.speed_rpm = max(
                0.0, self.speed_rpm - (self._N_rated / self._tau) * dt)
        else:
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))

        ratio = self.speed_rpm / self._N_rated if self._N_rated > 0 else 0.0

        if ratio < 0.01:
            # Pump effectively stopped
            self.flow_m3hr    = 0.0
            self.head_m       = 0.0
            self.power_kW     = 0.0
            self.current_A    = 0.0
            self.pressure_bar = 0.0
            self._write_state(state)
            return

        # Pump curve at current speed
        Q_max     = self._Q_rated   * ratio        # max flow (m³/s)
        H_shutoff = self._H_rated   * ratio ** 2   # shutoff head (m)

        # Solve operating point analytically
        # Q² = (H_shutoff - H_static) / (H_shutoff/Q_max² + k_sys)
        numerator   = H_shutoff - self._H_static
        denominator = (H_shutoff / (Q_max ** 2) + self._k_sys) if Q_max > 0 else 1.0

        if numerator <= 0 or denominator <= 0:
            # Pump cannot overcome static head at this speed
            Q_m3s = 0.0
        else:
            Q_m3s = math.sqrt(numerator / denominator)
            Q_m3s = max(0.0, min(Q_m3s, Q_max))

        # Head at operating point from system curve
        H_operating = self._H_static + self._k_sys * Q_m3s ** 2

        # Power and current from affinity laws
        # Use ratio³ and ratio² from rated values
        self.flow_m3hr    = Q_m3s * 3600.0
        self.head_m       = H_operating
        self.power_kW     = self._P_rated_kW * ratio ** 3
        self.current_A    = self._I_rated_A  * ratio ** 2
        self.pressure_bar = (1000.0 * 9.81 * H_operating) / 1e5

        # Realistic sensor noise
        self.flow_m3hr    = max(0.0, self.flow_m3hr  + random.gauss(0, 0.8))
        self.current_A    = max(0.0, self.current_A  + random.gauss(0, 0.1))
        self.pressure_bar = max(0.0, self.pressure_bar + random.gauss(0, 0.01))

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.pump_speed_rpm         = self.speed_rpm
            state.pump_running           = self.running
            state.pump_fault             = self.fault
            state.pump_current_A         = self.current_A
            state.pump_power_kW          = self.power_kW
            state.pump_head_m            = self.head_m
            state.pump_starts_today      = self._starts_today
            state.flow_m3hr              = self.flow_m3hr
            state.discharge_pressure_bar = self.pressure_bar
