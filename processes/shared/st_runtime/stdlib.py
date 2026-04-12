"""
stdlib.py — IEC 61131-3 Standard Library Function Blocks
MORBION SCADA v02

Stateful function blocks — one instance persists across scan cycles.
TON, TOF: timer blocks — require dt (scan interval) passed by interpreter.
CTU: counter block — counts rising edges.
SR, RS: flip-flop latches.
Stateless functions: LIMIT, ABS, MAX, MIN, SQRT, INT, REAL, BOOL.
"""

import math


class TON:
    """
    Timer On Delay.
    Q goes TRUE after IN has been TRUE continuously for PT seconds.
    Q resets immediately when IN goes FALSE.
    ET = elapsed time (seconds), clamped to PT.
    """

    def __init__(self):
        self.IN   = False
        self.PT   = 0.0
        self.Q    = False
        self.ET   = 0.0
        self._acc = 0.0

    def __call__(self, IN: bool, PT: float, dt: float) -> bool:
        self.IN = IN
        self.PT = PT
        if IN:
            self._acc += dt
            self.ET   = min(self._acc, PT)
            self.Q    = self._acc >= PT
        else:
            self._acc = 0.0
            self.ET   = 0.0
            self.Q    = False
        return self.Q


class TOF:
    """
    Timer Off Delay.
    Q goes TRUE immediately when IN goes TRUE.
    Q goes FALSE after IN has been FALSE continuously for PT seconds.
    ET = elapsed time since IN went FALSE.
    """

    def __init__(self):
        self.IN   = False
        self.PT   = 0.0
        self.Q    = False
        self.ET   = 0.0
        self._acc = 0.0

    def __call__(self, IN: bool, PT: float, dt: float) -> bool:
        self.IN = IN
        self.PT = PT
        if IN:
            self.Q    = True
            self._acc = 0.0
            self.ET   = 0.0
        else:
            if self.Q:
                self._acc += dt
                self.ET    = min(self._acc, PT)
                if self._acc >= PT:
                    self.Q = False
        return self.Q


class CTU:
    """
    Counter Up.
    CV increments on each rising edge of CU.
    Q goes TRUE when CV >= PV.
    R resets CV to 0 immediately (dominant over CU).
    """

    def __init__(self):
        self.CU       = False
        self.R        = False
        self.PV       = 0
        self.Q        = False
        self.CV       = 0
        self._prev_CU = False

    def __call__(self, CU: bool, R: bool, PV: int) -> bool:
        self.R  = R
        self.PV = PV
        if R:
            self.CV = 0
        elif CU and not self._prev_CU:
            self.CV += 1
        self._prev_CU = CU
        self.Q = self.CV >= PV
        return self.Q


class SR:
    """
    SR Flip-Flop — Set dominant.
    S1=TRUE sets Q1 TRUE.
    R=TRUE resets Q1 FALSE.
    If both TRUE: S1 wins (set dominant).
    """

    def __init__(self):
        self.Q1 = False

    def __call__(self, S1: bool, R: bool) -> bool:
        if S1:
            self.Q1 = True
        elif R:
            self.Q1 = False
        return self.Q1


class RS:
    """
    RS Flip-Flop — Reset dominant.
    S=TRUE sets Q1 TRUE.
    R1=TRUE resets Q1 FALSE.
    If both TRUE: R1 wins (reset dominant).
    """

    def __init__(self):
        self.Q1 = False

    def __call__(self, S: bool, R1: bool) -> bool:
        if R1:
            self.Q1 = False
        elif S:
            self.Q1 = True
        return self.Q1


# ── Stateless standard functions ──────────────────────────────────────────────
# Called inline in expressions. No state. No instance needed.

STDLIB_FUNCTIONS = {
    'LIMIT': lambda mn, val, mx: max(float(mn), min(float(mx), float(val))),
    'ABS':   lambda x: abs(x),
    'MAX':   lambda a, b: max(a, b),
    'MIN':   lambda a, b: min(a, b),
    'SQRT':  lambda x: math.sqrt(max(0.0, float(x))),
    'INT':   lambda x: int(x),
    'REAL':  lambda x: float(x),
    'BOOL':  lambda x: bool(x),
}

# Function block registry — maps ST name to class
FB_CLASSES = {
    'TON': TON,
    'TOF': TOF,
    'CTU': CTU,
    'SR':  SR,
    'RS':  RS,
}