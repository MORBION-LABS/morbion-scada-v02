"""
hot_pump.py — Hot Side Pump
Drives geothermal brine through the hot side of the exchanger.
Pump affinity laws govern flow and pressure relationships.
Owns its own state. Reads setpoint from ProcessState. Writes results back.
"""

import math
import random
import time


class HotPump:
    """
    Centrifugal pump on geothermal brine circuit.

    Affinity Laws:
        Q  ∝  N          (flow proportional to speed)
        H  ∝  N²         (head proportional to speed squared)
        P  ∝  N³         (power proportional to speed cubed)

    Motor current modeled from shaft power.
    """

    def __init__(self, config: dict):
        cfg = config["hot_pump"]

        # Nameplate data
        self._N_rated   = cfg["rated_speed_rpm"]   # RPM
        self._Q_rated   = cfg["rated_flow_lpm"]    # L/min
        self._H_rated   = cfg["rated_head_bar"]    # bar
        self._tau       = cfg["tau"]               # seconds — speed ramp time constant

        # Motor constants derived from nameplate
        self._P_rated_kW = (self._Q_rated / 60000 *
                            self._H_rated * 1e5) / (0.75 * 1000)  # shaft power kW
        self._I_rated_A  = self._P_rated_kW * 1000 / (400 * 1.732 * 0.88)  # 400V 3-phase

        # State
        self.speed_rpm:   float = 0.0
        self.flow_lpm:    float = 0.0
        self.head_bar:    float = 0.0
        self.power_kW:    float = 0.0
        self.current_A:   float = 0.0
        self.running:     bool  = False
        self.fault:       bool  = False

        # Internal
        self._speed_setpoint: float = 0.0
        self._run_hours:      float = 0.0
        self._start_time:     float = 0.0

    def set_speed(self, rpm: float):
        """PLC sets target speed."""
        self._speed_setpoint = max(0.0, min(rpm, self._N_rated))

    def start(self):
        self.running = True
        self._start_time = time.time()

    def stop(self):
        self.running      = False
        self._speed_setpoint = 0.0

    def update(self, dt: float, state):
        """
        Advance pump physics by dt seconds.
        Writes results into ProcessState.
        """
        if self.fault:
            self._write_state(state)
            return

        if not self.running:
            # Ramp speed down
            self.speed_rpm = max(0.0,
                self.speed_rpm - (self._N_rated / self._tau) * dt)
        else:
            # First order lag toward setpoint
            error = self._speed_setpoint - self.speed_rpm
            self.speed_rpm += (error / self._tau) * dt
            self.speed_rpm  = max(0.0, min(self.speed_rpm, self._N_rated))
            self._run_hours += dt / 3600.0

        # Affinity laws from current speed ratio
        ratio = self.speed_rpm / self._N_rated if self._N_rated > 0 else 0.0

        self.flow_lpm  = self._Q_rated   * ratio          + random.gauss(0, 1.5)
        self.head_bar  = self._H_rated   * ratio ** 2     + random.gauss(0, 0.02)
        self.power_kW  = self._P_rated_kW * ratio ** 3
        self.current_A = self._I_rated_A  * ratio ** 2    + random.gauss(0, 0.1)

        # Clamp negatives
        self.flow_lpm  = max(0.0, self.flow_lpm)
        self.head_bar  = max(0.0, self.head_bar)
        self.power_kW  = max(0.0, self.power_kW)
        self.current_A = max(0.0, self.current_A)

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.hot_pump_speed_rpm = self.speed_rpm
            state.hot_pump_running   = self.running
            state.hot_pump_fault     = self.fault
            state.hot_pump_current_A = self.current_A
            state.flow_hot           = self.flow_lpm
            state.pressure_hot_in    = self.head_bar + random.gauss(0, 0.01)
            state.pressure_hot_out   = self.head_bar * 0.85 + random.gauss(0, 0.01)