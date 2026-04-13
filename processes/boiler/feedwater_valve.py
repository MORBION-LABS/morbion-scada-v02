"""
feedwater_valve.py — Feedwater Control Valve
Modulates feedwater flow into the drum.
Three-element control positions this valve.
Fail-closed — loss of signal stops feedwater.
"""

import random


class FeedwaterValve:

    def __init__(self, config: dict):
        cfg = config["feedwater_valve"]

        self._Cv_max       = cfg["Cv_max"]
        self._tau          = cfg["tau"]
        self._fail_pos     = cfg["fail_position"]
        self._setpoint_pct = cfg["setpoint_pct"]

        self.position_pct:  float = 0.0
        self.commanded_pct: float = self._setpoint_pct
        self.Cv_actual:     float = 0.0

    def set_position(self, pct: float):
        self.commanded_pct = max(0.0, min(100.0, pct))

    def fail_safe(self):
        self.commanded_pct = 100.0 if self._fail_pos == "open" else 0.0

    def update(self, dt: float, state):
        error = self.commanded_pct - self.position_pct
        self.position_pct += (error / self._tau) * dt
        self.position_pct  = max(0.0, min(100.0, self.position_pct))
        self.position_pct += random.gauss(0, 0.05)
        self.position_pct  = max(0.0, min(100.0, self.position_pct))

        R = 50.0
        if self.position_pct > 0.1:
            self.Cv_actual = self._Cv_max * (
                R ** ((self.position_pct - 100.0) / 100.0))
        else:
            self.Cv_actual = 0.0

        with state:
            state.fw_valve_pos_pct  = self.position_pct
            state.fw_valve_cmd_pct  = self.commanded_pct
            # Feedwater flow = pump flow × valve modulation
            state.feedwater_flow_kghr = state.fw_pump_speed_rpm / 1450.0 * (
                self.position_pct / 100.0) * 4500.0