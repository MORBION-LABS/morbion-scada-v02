"""
level_sensor.py — Tank Level Sensor
Ultrasonic level sensor mounted at top of tank.
Measures distance to water surface — converted to level %.
Noise and drift modeled for realism.
Critical measurement — controls pump start/stop.
Stuck sensor or drifting sensor caught by conservation law.
"""

import random


class LevelSensor:

    def __init__(self, config: dict):
        cfg = config["level_sensor"]

        self._noise_std = cfg["noise_std"]
        self._tank_h    = config["tank"]["height_m"]

        self.level_pct: float = 50.0
        self.level_mm:  float = self._tank_h * 1000.0 * 0.5

        self._drift_accum: float = 0.0
        self._stuck:       bool  = False
        self._stuck_value: float = 0.0

    def inject_stuck(self, current_pct: float):
        self._stuck       = True
        self._stuck_value = current_pct

    def clear_fault(self):
        self._stuck = False

    def update(self, dt: float, state):
        if self._stuck:
            with state:
                state.level_sensor_pct = self._stuck_value
                state.level_sensor_mm  = (self._stuck_value / 100.0 *
                                           self._tank_h * 1000.0)
            return

        with state:
            true_level = state.tank_level_pct

        measured = true_level + random.gauss(0, self._noise_std)
        measured = max(0.0, min(100.0, measured))

        self.level_pct = measured
        self.level_mm  = measured / 100.0 * self._tank_h * 1000.0

        with state:
            state.level_sensor_pct = self.level_pct
            state.level_sensor_mm  = self.level_mm