"""
pressure_sensor.py — Pump Discharge Pressure Sensor
Pressure transmitter on pump discharge header.
4-20mA output scaled to 0-20 bar.
High pressure alarm protects pump and pipe from overpressure.
No pressure while pump running = discharge blocked or valve closed.
"""

import random


class PressureSensor:

    def __init__(self, config: dict):
        cfg = config["pressure_sensor"]

        self._noise_std = cfg["noise_std"]
        self._scale_lo  = cfg["scale_lo"]
        self._scale_hi  = cfg["scale_hi"]

        self.pressure_bar: float = 0.0

    def update(self, dt: float, state):
        with state:
            true_pressure = state.discharge_pressure_bar

        measured = true_pressure + random.gauss(0, self._noise_std)
        measured = max(self._scale_lo, min(self._scale_hi, measured))

        self.pressure_bar = measured

        with state:
            state.discharge_pressure_bar = self.pressure_bar