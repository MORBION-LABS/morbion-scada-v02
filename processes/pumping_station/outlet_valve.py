"""
outlet_valve.py — Outlet Control Valve
Modulating valve on tank outlet.
Controls flow from tank to distribution network.
Normally open at setpoint — closes on high level alarm.
Fail-closed — loss of signal stops distribution.
"""

import random


class OutletValve:

    def __init__(self, config: dict):
        cfg = config["outlet_valve"]

        self._tau          = cfg["tau"]
        self._fail_pos     = cfg["fail_position"]
        self._setpoint_pct = cfg["setpoint_pct"]

        self.position_pct:  float = self._setpoint_pct
        self.commanded_pct: float = self._setpoint_pct

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

        with state:
            state.outlet_valve_pos_pct = self.position_pct
            state.outlet_valve_cmd_pct = self.commanded_pct