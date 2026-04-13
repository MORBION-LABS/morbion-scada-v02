"""
cold_pump.py — Cold Side Pump
Drives feedwater through the cold side of the exchanger.
Same affinity law physics as hot pump. Independent equipment.
"""

import random
import time


class ColdPump:
    """
    Centrifugal pump on feedwater circuit.
    Identical physics to HotPump — different nameplate ratings.
    """

    def __init__(self, config: dict):
        cfg = config["cold_pump"]

        self._N_rated    = cfg["rated_speed_rpm"]
        self._Q_rated    = cfg["rated_flow_lpm"]
        self._H_rated    = cfg["rated_head_bar"]
        self._tau        = cfg["tau"]

        self._P_rated_kW = (self._Q_rated / 60000 *
                            self._H_rated * 1e5) / (0.75 * 1000)
        self._I_rated_A  = self._P_rated_kW * 1000 / (400 * 1.732 * 0.88)

        self.speed_rpm:  float = 0.0
        self.flow_lpm:   float = 0.0
        self.head_bar:   float = 0.0
        self.power_kW:   float = 0.0
        self.current_A:  float = 0.0
        self.running:    bool  = False
        self.fault:      bool  = False

        self._speed_setpoint: float = 0.0
        self._run_hours:      float = 0.0

    def set_speed(self, rpm: float):
        self._speed_setpoint = max(0.0, min(rpm, self._N_rated))

    def start(self):
        self.running = True

    def stop(self):
        self.running         = False
        self._speed_setpoint = 0.0

    def update(self, dt: float, state):
        if self.fault:
            self._write_state(state)
            return

        if not self.running:
            self.speed_rpm = max(0.0,
                self.speed_rpm - (self._N_rated / self._tau) * dt)
        else:
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))
            self._run_hours += dt / 3600.0

        ratio = self.speed_rpm / self._N_rated if self._N_rated > 0 else 0.0

        self.flow_lpm  = self._Q_rated    * ratio         + random.gauss(0, 2.0)
        self.head_bar  = self._H_rated    * ratio ** 2    + random.gauss(0, 0.02)
        self.power_kW  = self._P_rated_kW * ratio ** 3
        self.current_A = self._I_rated_A  * ratio ** 2    + random.gauss(0, 0.1)

        self.flow_lpm  = max(0.0, self.flow_lpm)
        self.head_bar  = max(0.0, self.head_bar)
        self.power_kW  = max(0.0, self.power_kW)
        self.current_A = max(0.0, self.current_A)

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.cold_pump_speed_rpm = self.speed_rpm
            state.cold_pump_running   = self.running
            state.cold_pump_fault     = self.fault
            state.cold_pump_current_A = self.current_A
            state.flow_cold           = self.flow_lpm
            state.pressure_cold_in    = self.head_bar + random.gauss(0, 0.01)
            state.pressure_cold_out   = self.head_bar * 0.85 + random.gauss(0, 0.01)