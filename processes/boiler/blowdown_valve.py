"""
blowdown_valve.py — Bottom Blowdown Valve
Removes concentrated boiler water to maintain water quality.
Normally closed. Opens periodically or on high TDS indication.
Small valve — 2% of steam flow typical.
Fail-closed — loss of signal keeps boiler water in drum.
"""

import random


class BlowdownValve:

    def __init__(self, config: dict):
        cfg = config["blowdown_valve"]

        self._Cv_max       = cfg["Cv_max"]
        self._tau          = cfg["tau"]
        self._fail_pos     = cfg["fail_position"]

        self.position_pct:  float = 0.0
        self.commanded_pct: float = 0.0

    def set_position(self, pct: float):
        self.commanded_pct = max(0.0, min(100.0, pct))

    def fail_safe(self):
        self.commanded_pct = 0.0

    def update(self, dt: float, state):
        error = self.commanded_pct - self.position_pct
        self.position_pct += (error / self._tau) * dt
        self.position_pct  = max(0.0, min(100.0, self.position_pct))
        self.position_pct += random.gauss(0, 0.02)
        self.position_pct  = max(0.0, min(100.0, self.position_pct))

        with state:
            state.blowdown_valve_pos_pct = self.position_pct
            state.blowdown_valve_cmd_pct = self.commanded_pct
            state.blowdown_flow_kghr     = (self.position_pct / 100.0) * (
                state.drum_pressure_bar / 10.0) * 150.0