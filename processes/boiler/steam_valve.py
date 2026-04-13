"""
steam_valve.py — Steam Outlet Control Valve
Controls steam flow leaving the drum to process users.
Modulating globe valve. Equal percentage characteristic.
Fail-closed on loss of signal — steam stays in drum on fault.
"""

import random


class SteamValve:

    def __init__(self, config: dict):
        cfg = config["steam_valve"]

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
            state.steam_valve_pos_pct = self.position_pct
            state.steam_valve_cmd_pct = self.commanded_pct