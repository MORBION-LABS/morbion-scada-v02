"""
control_valve.py — Control Valves (Hot and Cold Side)
Modulates flow on each side of the heat exchanger.
Each valve instance is independent equipment.
Valve position affects flow through Cv equation.
"""

import random


class ControlValve:
    """
    Globe control valve with pneumatic actuator.

    Flow equation:
        Q = Cv × √(ΔP / SG)

    Where:
        Cv   = valve flow coefficient (function of position)
        ΔP   = differential pressure across valve (bar)
        SG   = specific gravity of fluid
        Q    = flow (L/min)

    Actuator modeled as first order lag.
    Fail position configurable (fail-open or fail-closed).
    """

    def __init__(self, name: str, config: dict):
        cfg = config[name]

        self._Cv_max       = cfg["Cv_max"]         # max flow coefficient
        self._tau          = cfg["tau"]             # actuator time constant (s)
        self._fail_pos     = cfg["fail_position"]  # "open" or "closed"
        self._setpoint_pct = cfg["setpoint_pct"]   # initial setpoint

        # State
        self.position_pct:  float = 0.0    # actual position 0-100%
        self.commanded_pct: float = self._setpoint_pct
        self.Cv_actual:     float = 0.0
        self.fault:         bool  = False

    def set_position(self, pct: float):
        """PLC commands valve position."""
        self.commanded_pct = max(0.0, min(100.0, pct))

    def fail_safe(self):
        """Drive to fail-safe position on loss of signal."""
        if self._fail_pos == "open":
            self.commanded_pct = 100.0
        else:
            self.commanded_pct = 0.0

    def update(self, dt: float):
        """
        Advance valve actuator by dt seconds.
        First order lag toward commanded position.
        """
        error = self.commanded_pct - self.position_pct
        self.position_pct += (error / self._tau) * dt
        self.position_pct  = max(0.0, min(100.0, self.position_pct))

        # Equal percentage characteristic
        # Cv = Cv_max × R^((position-100)/100)  where R=50 rangeability
        R = 50.0
        if self.position_pct > 0.1:
            self.Cv_actual = self._Cv_max * (R ** ((self.position_pct - 100.0) / 100.0))
        else:
            self.Cv_actual = 0.0

        # Add small hysteresis noise
        self.position_pct += random.gauss(0, 0.05)
        self.position_pct  = max(0.0, min(100.0, self.position_pct))

    def flow_lpm(self, delta_pressure_bar: float, specific_gravity: float = 1.0) -> float:
        """
        Calculate flow through valve given differential pressure.
        Q = Cv × √(ΔP / SG)    [result in L/min approximate]
        """
        if delta_pressure_bar <= 0 or self.Cv_actual <= 0:
            return 0.0
        import math
        return self.Cv_actual * math.sqrt(delta_pressure_bar / specific_gravity) * 16.67