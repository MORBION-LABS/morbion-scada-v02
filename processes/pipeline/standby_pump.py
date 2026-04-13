"""
standby_pump.py — Standby Pump
Identical to duty pump physically.
Starts automatically when duty pump faults.
Normally at rest — speed = 0, running = False.
"""

import math
import random


class StandbyPump:

    def __init__(self, config: dict):
        cfg      = config["standby_pump"]
        pipe_cfg = config["pipeline"]

        self._N_rated   = cfg["rated_speed_rpm"]
        self._Q_rated   = cfg["rated_flow_m3hr"] / 3600.0
        self._H_rated   = cfg["rated_head_bar"] * 1e5 / (850 * 9.81)
        self._eta       = cfg["rated_efficiency"]
        self._tau       = cfg["tau"]
        self._SG        = cfg["specific_gravity"]
        self._rho       = self._SG * 1000.0
        self._A_pipe    = math.pi / 4.0 * pipe_cfg["diameter_m"] ** 2

        self._P_rated_kW = (self._rho * 9.81 *
                            self._Q_rated * self._H_rated) / (self._eta * 1000)
        self._I_rated_A  = self._P_rated_kW * 1000 / (math.sqrt(3) * 6600 * 0.9 * 0.95)

        self.speed_rpm:  float = 0.0
        self.flow_m3s:   float = 0.0
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

        if not self.running:
            self.speed_rpm = max(
                0.0, self.speed_rpm - (self._N_rated / self._tau) * dt)
            self.flow_m3s  = 0.0
            self.head_bar  = 0.0
            self.power_kW  = 0.0
            self.current_A = 0.0
        else:
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))

            ratio          = self.speed_rpm / self._N_rated
            self.flow_m3s  = self._Q_rated   * ratio
            self.head_bar  = (self._H_rated * ratio ** 2 *
                              self._rho * 9.81 / 1e5)
            self.power_kW  = self._P_rated_kW * ratio ** 3
            self.current_A = self._I_rated_A  * ratio ** 2

            self.flow_m3s  = max(0.0, self.flow_m3s  + random.gauss(0, 0.001))
            self.current_A = max(0.0, self.current_A + random.gauss(0, 0.2))

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.standby_pump_speed_rpm = self.speed_rpm
            state.standby_pump_running   = self.running
            state.standby_pump_fault     = self.fault
            state.standby_pump_current_A = self.current_A
            # If standby running, override flow
            if self.running:
                state.flow_rate_m3hr   = self.flow_m3s * 3600.0
                state.flow_velocity_ms = (self.flow_m3s / self._A_pipe
                                          if self._A_pipe > 0 else 0.0)