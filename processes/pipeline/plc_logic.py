"""
plc_logic.py — Pipeline PLC Logic (Python fallback)
MORBION SCADA v02

NOTE: In v02 the primary PLC logic runs in the ST runtime via
plc_runtime.py + plc_program.st. This Python file is kept as a
fallback only — it is NOT called from main.py unless the ST
runtime fails to load.

KEY FIXES FROM v01:
  - Duty-standby reset properly handled
  - Standby started only after duty confirmed faulted
  - fault_code cleared correctly when operator resets
  - leak_flag typed as bool throughout (was int in v01)
  - Alarm states properly latched with deadband

This file documents the control logic for reference.
The ST program in plc_program.st is the authoritative implementation.
"""

import logging

log = logging.getLogger("pipeline.plc_logic")


class PipelinePLC:
    """
    Python fallback PLC for pipeline.
    Only used if ST runtime fails to load.
    Called from main.py only if plc.status["loaded"] is False.
    """

    def __init__(self, config: dict, duty_pump, standby_pump,
                 inlet_valve, outlet_valve):
        self._cfg          = config
        self._duty         = duty_pump
        self._standby      = standby_pump
        self._inlet_valve  = inlet_valve
        self._outlet_valve = outlet_valve

        self._alarm_outlet_high: bool  = False
        self._alarm_outlet_low:  bool  = False
        self._alarm_inlet_low:   bool  = False
        self._alarm_flow_low:    bool  = False
        self._alarm_leak:        bool  = False

        # Latch flags — require operator reset
        self._duty_fault_latched:  bool  = False
        self._both_fault_latched:  bool  = False
        self._overpressure_latched:bool  = False

        # Standby start delay accumulator
        self._standby_delay: float = 0.0

    def scan(self, state, dt: float = 0.1):
        self._read_inputs(state)
        self._update_latches(state)
        self._safety_checks(state)
        self._control_logic(state, dt)
        self._alarm_logic(state)
        self._leak_detection(state)

    def _read_inputs(self, state):
        with state:
            self._process_running   = state.process_running
            self._outlet_pressure   = state.outlet_pressure_bar
            self._inlet_pressure    = state.inlet_pressure_bar
            self._flow              = state.flow_rate_m3hr
            self._duty_fault        = state.duty_pump_fault
            self._standby_fault     = state.standby_pump_fault
            self._duty_running      = state.duty_pump_running
            self._standby_running   = state.standby_pump_running
            self._fault_code        = state.fault_code

    def _update_latches(self, state):
        """Update SR latches for faults."""
        # Overpressure latch
        if self._outlet_pressure > 55.0:
            self._overpressure_latched = True
        if self._fault_code == 0 and self._outlet_pressure < 52.0:
            self._overpressure_latched = False

        # Both fault latch
        if self._duty_fault and self._standby_fault:
            self._both_fault_latched = True
        if self._fault_code == 0 and not self._duty_fault and not self._standby_fault:
            self._both_fault_latched = False

        # Duty fault latch
        if self._duty_fault:
            self._duty_fault_latched = True
        if self._fault_code == 0 and not self._duty_fault:
            self._duty_fault_latched = False

    def _safety_checks(self, state):
        """Latched safety interlocks."""
        if self._overpressure_latched:
            self._duty.stop()
            self._standby.stop()
            self._inlet_valve.close()
            self._outlet_valve.set_position(0.0)
            with state:
                state.fault_code = 3
            return

        if self._both_fault_latched:
            self._duty.stop()
            self._standby.stop()
            self._inlet_valve.close()
            with state:
                state.fault_code = 2

    def _control_logic(self, state, dt: float):
        if not self._process_running:
            self._duty.stop()
            self._standby.stop()
            self._inlet_valve.close()
            self._outlet_valve.fail_safe()
            return

        if self._overpressure_latched or self._both_fault_latched:
            return

        if self._duty_fault_latched:
            self._duty.stop()
            with state:
                state.fault_code = 1
            # Delay before starting standby
            self._standby_delay += dt
            if self._standby_delay >= 2.0 and not self._standby_fault:
                if not self._standby.running:
                    self._standby.start()
                    self._standby.set_speed(
                        self._cfg["standby_pump"]["setpoint_rpm"])
        else:
            self._standby_delay = 0.0
            self._inlet_valve.open()
            if not self._duty.running and not self._duty_fault:
                self._duty.start()
                self._duty.set_speed(
                    self._cfg["duty_pump"]["setpoint_rpm"])
            # Stop standby if duty recovered
            if self._standby.running:
                self._standby.stop()

        # Pressure control via outlet valve
        op_cfg        = self._cfg["operating_conditions"]
        target_P      = op_cfg["outlet_pressure_nominal"]
        error         = target_P - self._outlet_pressure
        new_pos       = self._cfg["outlet_valve"]["setpoint_pct"] + (error * 1.5)
        new_pos       = max(20.0, min(95.0, new_pos))
        self._outlet_valve.set_position(new_pos)

    def _alarm_logic(self, state):
        alm = self._cfg["alarms"]

        lim = alm["outlet_pressure_high"]["limit"]
        db  = alm["outlet_pressure_high"]["deadband"]
        if self._outlet_pressure > lim:
            self._alarm_outlet_high = True
        elif self._outlet_pressure < lim - db:
            self._alarm_outlet_high = False

        lim = alm["outlet_pressure_low"]["limit"]
        db  = alm["outlet_pressure_low"]["deadband"]
        if self._outlet_pressure < lim and self._process_running:
            self._alarm_outlet_low = True
        elif self._outlet_pressure > lim + db:
            self._alarm_outlet_low = False

        lim = alm["inlet_pressure_low"]["limit"]
        db  = alm["inlet_pressure_low"]["deadband"]
        if self._inlet_pressure < lim:
            self._alarm_inlet_low = True
        elif self._inlet_pressure > lim + db:
            self._alarm_inlet_low = False

        lim = alm["flow_low"]["limit"]
        db  = alm["flow_low"]["deadband"]
        if self._flow < lim and self._process_running:
            self._alarm_flow_low = True
        elif self._flow > lim + db:
            self._alarm_flow_low = False

        with state:
            state.alarm_outlet_high = self._alarm_outlet_high
            state.alarm_outlet_low  = self._alarm_outlet_low
            state.alarm_inlet_low   = self._alarm_inlet_low
            state.alarm_flow_low    = self._alarm_flow_low

    def _leak_detection(self, state):
        with state:
            duty_speed  = state.duty_pump_speed_rpm
            meter_flow  = state.flow_rate_m3hr
            running     = state.duty_pump_running

        if not running:
            with state:
                state.leak_flag  = False
                state.alarm_leak = False
            return

        threshold     = self._cfg["alarms"]["leak_suspected"]["threshold"]
        rated_speed   = self._cfg["duty_pump"]["rated_speed_rpm"]
        rated_flow    = self._cfg["duty_pump"]["rated_flow_m3hr"]
        expected_flow = (duty_speed / rated_speed) * rated_flow if rated_speed > 0 else 0.0
        discrepancy   = abs(expected_flow - meter_flow)

        leak = discrepancy > threshold

        with state:
            state.leak_flag          = leak
            state.flow_balance_error = discrepancy
            state.alarm_leak         = leak
