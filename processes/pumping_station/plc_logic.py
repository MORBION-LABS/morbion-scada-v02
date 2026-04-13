"""
plc_logic.py — Pumping Station PLC Logic (Python fallback)
MORBION SCADA v02

NOTE: In v02 the primary PLC logic runs in the ST runtime via
plc_runtime.py + plc_program.st. This Python file is kept as a
fallback only — it is NOT called from main.py unless the ST
runtime fails to load.

KEY FIXES FROM v01:
  - Fault codes properly latched — require operator reset
  - Dry run protection uses dt accumulation not hardcoded sleep
  - HIGH_LEVEL fault (code 1) clears correctly with deadband
  - LOW_LEVEL fault (code 2) requires operator reset
  - DRY_RUN fault (code 4) requires operator reset

This file documents the control logic for reference.
The ST program in plc_program.st is the authoritative implementation.
"""

import logging

log = logging.getLogger("pumping_station.plc_logic")


class PumpingStationPLC:
    """
    Python fallback PLC for pumping station.
    Only used if ST runtime fails to load.
    """

    def __init__(self, config: dict, pump, inlet_valve, outlet_valve):
        self._cfg          = config
        self._pump         = pump
        self._inlet_valve  = inlet_valve
        self._outlet_valve = outlet_valve

        ctrl = config["control"]
        self._level_start   = ctrl["level_start_pct"]
        self._level_stop    = ctrl["level_stop_pct"]
        self._dry_run_delay = ctrl["dry_run_delay_s"]

        # Alarm states with deadband
        self._alarm_high:     bool  = False
        self._alarm_low:      bool  = False
        self._alarm_low_low:  bool  = False
        self._alarm_no_flow:  bool  = False
        self._alarm_pressure: bool  = False
        self._alarm_dry_run:  bool  = False

        # Latch flags — require operator reset
        self._low_low_latched:  bool  = False
        self._dry_run_latched:  bool  = False
        self._pressure_latched: bool  = False

        # Dry run timer — accumulates actual dt
        self._no_flow_accum: float = 0.0

    def scan(self, state, dt: float = 0.1):
        """dt must be passed — never hardcoded."""
        self._read_inputs(state)
        self._update_latches(state)
        self._safety_checks(state, dt)
        self._control_logic(state)
        self._alarm_logic(state)

    def _read_inputs(self, state):
        with state:
            self._running   = state.process_running
            self._level     = state.level_sensor_pct
            self._flow      = state.flow_m3hr
            self._pressure  = state.discharge_pressure_bar
            self._pump_run  = state.pump_running
            self._pump_flt  = state.pump_fault
            self._fault     = state.fault_code

    def _update_latches(self, state):
        """SR latch logic — set on fault, reset when operator writes 0."""

        # Low-low level latch
        if self._level < 5.0:
            self._low_low_latched = True
        if self._fault == 0 and self._level > 8.0:
            self._low_low_latched = False

        # Dry run latch
        # Set by safety_checks. Reset: operator clears AND level recovered.
        if self._fault == 0 and self._level > 15.0:
            self._dry_run_latched = False
            self._alarm_dry_run   = False

        # High pressure latch
        if self._pressure > 8.0:
            self._pressure_latched = True
        if self._fault == 0 and self._pressure < 7.5:
            self._pressure_latched = False

    def _safety_checks(self, state, dt: float):
        """Hard safety stops — checked every scan."""

        # Critical low level — immediate stop
        if self._low_low_latched:
            self._pump.stop()
            self._inlet_valve.close()
            self._outlet_valve.set_position(0.0)
            with state:
                state.fault_code = 2
            return

        # High pressure — stop pump
        if self._pressure_latched:
            self._pump.stop()
            self._inlet_valve.close()
            with state:
                state.fault_code = 3
            return

        # Dry run protection — TON equivalent using dt accumulation
        if self._pump_run and self._flow < 5.0:
            self._no_flow_accum += dt
            if self._no_flow_accum >= self._dry_run_delay:
                self._dry_run_latched = True
                self._alarm_dry_run   = True
                self._pump.stop()
                self._inlet_valve.close()
                with state:
                    state.fault_code    = 4
                    state.alarm_dry_run = True
        else:
            self._no_flow_accum = 0.0

        if self._dry_run_latched:
            self._pump.stop()
            self._inlet_valve.close()
            with state:
                state.fault_code = 4

    def _control_logic(self, state):
        if not self._running:
            self._pump.stop()
            self._inlet_valve.close()
            self._outlet_valve.fail_safe()
            return

        # Any latched fault — hold until operator resets
        if self._fault > 1:
            self._pump.stop()
            self._inlet_valve.close()
            return

        # Level control — start pump when low
        if not self._pump_run and self._level < self._level_start and self._fault == 0:
            self._pump.start()
            self._pump.set_speed(self._cfg["pump"]["setpoint_rpm"])
            self._inlet_valve.open()

        # Level control — stop pump when high
        if self._pump_run and self._level > self._level_stop:
            self._pump.stop()
            self._inlet_valve.close()

        # Outlet valve — modulate on high level alarm
        if self._alarm_high:
            self._outlet_valve.set_position(20.0)
            with state:
                state.fault_code = 1
        elif self._level < 82.0 and self._fault == 1:
            # High level alarm cleared with deadband
            with state:
                state.fault_code = 0
            self._outlet_valve.set_position(
                self._cfg["outlet_valve"]["setpoint_pct"])
        elif self._alarm_low_low:
            self._outlet_valve.set_position(0.0)
        else:
            self._outlet_valve.set_position(
                self._cfg["outlet_valve"]["setpoint_pct"])

    def _alarm_logic(self, state):
        alm = self._cfg["alarms"]

        # High level
        lim = alm["level_high"]["limit"]
        db  = alm["level_high"]["deadband"]
        if self._level > lim:
            self._alarm_high = True
        elif self._level < lim - db:
            self._alarm_high = False

        # Low level
        lim = alm["level_low"]["limit"]
        db  = alm["level_low"]["deadband"]
        if self._level < lim:
            self._alarm_low = True
        elif self._level > lim + db:
            self._alarm_low = False

        # Low-low level
        lim = alm["level_low_low"]["limit"]
        db  = alm["level_low_low"]["deadband"]
        if self._level < lim:
            self._alarm_low_low = True
        elif self._level > lim + db:
            self._alarm_low_low = False

        # Pressure high
        lim = alm["pressure_high"]["limit"]
        db  = alm["pressure_high"]["deadband"]
        if self._pressure > lim:
            self._alarm_pressure = True
        elif self._pressure < lim - db:
            self._alarm_pressure = False

        with state:
            state.alarm_level_high    = self._alarm_high
            state.alarm_level_low     = self._alarm_low
            state.alarm_level_low_low = self._alarm_low_low
            state.alarm_pressure_high = self._alarm_pressure
            state.alarm_dry_run       = self._alarm_dry_run
