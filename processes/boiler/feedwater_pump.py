"""
feedwater_pump.py — Feedwater Pump
Delivers treated feedwater to steam drum.
Centrifugal pump — same affinity law physics as other processes.
Must overcome drum pressure plus pipe losses.

Physics:
    Affinity laws:
        Q ∝ N
        H ∝ N²
        P ∝ N³

    Feedwater flow to drum:
        m_fw = pump_flow × feedwater_valve_position
        Temperature of feedwater: 80°C (preheated)
"""

import math
import random


class FeedwaterPump:

    def __init__(self, config: dict):
        cfg = config["feedwater_pump"]

        self._N_rated    = cfg["rated_speed_rpm"]
        self._Q_rated    = cfg["rated_flow_kghr"] / 3600.0   # kg/s
        self._H_rated    = cfg["rated_head_bar"]
        self._eta        = cfg["rated_efficiency"]
        self._tau        = cfg["tau"]

        self._P_rated_kW = (self._Q_rated *
                            self._H_rated * 1e5) / (self._eta * 1000.0)
        self._I_rated_A  = self._P_rated_kW * 1000.0 / (
                            math.sqrt(3) * 400.0 * 0.88 * 0.92)

        self.speed_rpm:  float = 0.0
        self.flow_kghr:  float = 0.0
        self.head_bar:   float = 0.0
        self.power_kW:   float = 0.0
        self.current_A:  float = 0.0
        self.running:    bool  = False
        self.fault:      bool  = False

        self._speed_setpoint: float = 0.0

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
            self.speed_rpm = max(
                0.0, self.speed_rpm - (self._N_rated / self._tau) * dt)
        else:
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))

        ratio = self.speed_rpm / self._N_rated if self._N_rated > 0 else 0.0

        self.flow_kghr = self._Q_rated   * ratio * 3600.0
        self.head_bar  = self._H_rated   * ratio ** 2
        self.power_kW  = self._P_rated_kW * ratio ** 3
        self.current_A = self._I_rated_A  * ratio ** 2

        self.flow_kghr = max(0.0, self.flow_kghr + random.gauss(0, 2.0))
        self.current_A = max(0.0, self.current_A + random.gauss(0, 0.1))

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.fw_pump_speed_rpm = self.speed_rpm
            state.fw_pump_running   = self.running
            state.fw_pump_fault     = self.fault
            state.fw_pump_current_A = self.current_A