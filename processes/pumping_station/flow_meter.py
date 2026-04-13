"""
flow_meter.py — Discharge Flow Meter
Electromagnetic flow meter on pump discharge line.
Measures volumetric flow rate.
Critical for dry run detection and conservation law validation.
No flow while pump running = dry run or blocked line.
"""

import random


class FlowMeter:

    def __init__(self, config: dict):
        cfg = config["flow_meter"]

        self._noise_std = cfg["noise_std"]
        self._scale_lo  = cfg["scale_lo"]
        self._scale_hi  = cfg["scale_hi"]

        self.flow_m3hr: float = 0.0

    def update(self, dt: float, state):
        with state:
            true_flow = state.flow_m3hr

        measured = true_flow + random.gauss(0, self._noise_std)
        measured = max(self._scale_lo, min(self._scale_hi, measured))

        self.flow_m3hr = measured

        with state:
            state.flow_m3hr = self.flow_m3hr