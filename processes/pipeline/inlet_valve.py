"""
inlet_valve.py — Inlet Isolation Valve
On/off valve only — not modulating.
Opens on process start. Closes on shutdown or fault.
Motorized actuator — takes ~15 seconds to fully open or close.
"""

import random


class InletValve:

    def __init__(self, config: dict):
        self._tau          = config["inlet_valve"]["tau"]
        self._fail_pos     = config["inlet_valve"]["fail_position"]

        self.position_pct: float = 0.0    # 0=closed 100=open
        self.commanded:    bool  = False   # True=open False=closed
        self.fault:        bool  = False

    def open(self):
        self.commanded = True

    def close(self):
        self.commanded = False

    def fail_safe(self):
        self.commanded = (self._fail_pos == "open")

    def update(self, dt: float, state):
        target = 100.0 if self.commanded else 0.0
        error  = target - self.position_pct
        self.position_pct += (error / self._tau) * dt
        self.position_pct  = max(0.0, min(100.0, self.position_pct))
        self.position_pct += random.gauss(0, 0.05)
        self.position_pct  = max(0.0, min(100.0, self.position_pct))

        with state:
            state.inlet_valve_open     = self.commanded
            state.inlet_valve_position = self.position_pct