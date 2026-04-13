"""
flow_meter.py — Turbine Flow Meter
Measures volumetric flow rate of petroleum product.
Realistic noise and scaling.
Critical for leak detection — compares measured flow
against pump output flow. Discrepancy = leak indicator.
"""

import random


class FlowMeter:

    def __init__(self, config: dict):
        cfg = config["flow_meter"]

        self._noise_std = cfg["noise_std"]
        self._scale_lo  = cfg["scale_lo"]
        self._scale_hi  = cfg["scale_hi"]

        self.flow_m3hr:      float = 0.0
        self.flow_raw_reg:   int   = 0

    def update(self, dt: float, state):
        with state:
            true_flow = state.flow_rate_m3hr

        # Realistic turbine meter noise
        measured = true_flow + random.gauss(0, self._noise_std)
        measured = max(self._scale_lo, min(self._scale_hi, measured))

        self.flow_m3hr    = measured
        self.flow_raw_reg = int(measured * 10)

        with state:
            state.flow_rate_m3hr = self.flow_m3hr