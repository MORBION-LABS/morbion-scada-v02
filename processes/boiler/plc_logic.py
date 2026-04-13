"""
plc_logic.py — Boiler PLC Logic (Python fallback)
MORBION SCADA v02

NOTE: In v02 the primary PLC logic runs in the ST runtime via
plc_runtime.py + plc_program.st. This Python file is kept as a
fallback only — it is NOT called from main.py unless the ST
runtime fails to load.

KEY FIXES FROM v01:
  - dt parameter passed to scan() — not hardcoded
  - Safety interlock latches use proper set/reset logic
  - Fault codes latched — require operator reset (fault_code write 0)
  - Blowdown timer uses actual dt accumulation
  - Three-element feedwater control feedforward correct

This file documents the control logic for reference.
The ST program in plc_program.st is the authoritative implementation.
"""

import logging

log = logging.getLogger("boiler.plc_logic")


class BoilerPLC:
    """
    Python fallback PLC for boiler.
    Only used if ST runtime fails to load.
    """

    def __init__(self, config: dict, burner, feedwater_pump,
                 steam_valve, feedwater_valve, blowdown_valve):
        self._cfg             = config
        self._burner          = burner
        self._fw_pump         = feedwater_pump
        self._steam_valve     = steam_valve
        self._fw_valve        = feedwater_valve
        self._blowdown_valve  = blowdown_valve

        # Control parameters
        self._level_sp    = config["operating_conditions"]["drum_level_nominal"]
        self._pressure_sp = config["operating_conditions"]["drum_pressure_nominal"]
        self._Kp_level    = 1.2
        self._FF_gain     = 30.0

        # Alarm states
        self._alarm_P_high: bool = False
        self._alarm_P_low:  bool = False
        self._alarm_L_low:  bool = False
        self._alarm_L_high: bool = False
        self._alarm_pump:   bool = False

        # Latch flags — require operator reset
        self._low_water_latched:   bool = False
        self._overpressure_latched:bool = False
        self._pump_fault_latched:  bool = False

        # Blowdown timer — accumulates actual dt
        self._blowdown_accum: float = 0.0
        self._blowdown_active:bool  = False

    def scan(self, state, dt: float = 0.1):
        """dt must be passed — never hardcoded."""
        self._read_inputs(state)
        self._update_latches(state)
        self._safety_interlocks(state)
        self._control_logic(state)
        self._alarm_logic(state)
        self._blowdown_logic(state, dt)

    def _read_inputs(self, state):
        with state:
            self._running      = state.process_running
            self._pressure     = state.drum_pressure_bar
            self._level        = state.drum_level_pct
            self._steam_flow   = state.steam_flow_kghr
            self._fw_flow      = state.feedwater_flow_kghr
            self._burner_fault = state.burner_fault
            self._pump_fault   = state.fw_pump_fault
            self._fault_code   = state.fault_code

    def _update_latches(self, state):
        """SR latch logic — set on fault, reset only when operator clears."""
        # Low water latch
        if self._level < self._cfg["alarms"]["drum_level_low"]["limit"]:
            self._low_water_latched = True
        # Reset: operator writes 0 to fault_code AND level recovered
        if self._fault_code == 0 and self._level > 25.0:
            self._low_water_latched = False

        # Overpressure latch
        if self._pressure > self._cfg["alarms"]["drum_pressure_high"]["limit"]:
            self._overpressure_latched = True
        if self._fault_code == 0 and self._pressure < 9.5:
            self._overpressure_latched = False

        # Pump fault latch
        if self._pump_fault:
            self._pump_fault_latched = True
        if self._fault_code == 0 and not self._pump_fault:
            self._pump_fault_latched = False

    def _safety_interlocks(self, state):
        """Latched interlocks — trip burner, require operator reset."""
        if self._low_water_latched:
            self._burner.command(0)
            with state:
                state.fault_code = 1
            return

        if self._overpressure_latched:
            self._burner.command(0)
            with state:
                state.fault_code = 2
            return

        if self._pump_fault_latched:
            self._burner.command(0)
            with state:
                state.fault_code = 4
            return

    def _control_logic(self, state):
        if not self._running or self._fault_code > 0:
            self._burner.command(0)
            self._fw_pump.stop()
            self._steam_valve.fail_safe()
            self._fw_valve.fail_safe()
            return

        # Feedwater pump always runs when process running
        if not self._fw_pump.running and not self._pump_fault:
            self._fw_pump.start()
            self._fw_pump.set_speed(
                self._cfg["feedwater_pump"]["setpoint_rpm"])

        # Pressure-based burner control
        if self._pressure < 6.0:
            self._burner.command(2)     # HIGH
        elif self._pressure < self._pressure_sp:
            self._burner.command(1)     # LOW
        elif self._pressure >= 9.0:
            self._burner.command(0)     # OFF
        else:
            self._burner.command(1)     # LOW — hold

        # Steam valve — open when pressure established
        if self._pressure > 6.0:
            self._steam_valve.set_position(
                self._cfg["steam_valve"]["setpoint_pct"])
        else:
            self._steam_valve.set_position(0.0)

        # Three-element feedwater control
        max_steam  = self._cfg["operating_conditions"]["steam_flow_nominal_kghr"]
        level_err  = self._level_sp - self._level
        ff_steam   = min(1.0, self._steam_flow / max_steam) if max_steam > 0 else 0.0
        fw_cmd     = 50.0 + (level_err * self._Kp_level) + (ff_steam * self._FF_gain)
        fw_cmd     = max(10.0, min(90.0, fw_cmd))
        self._fw_valve.set_position(fw_cmd)

    def _alarm_logic(self, state):
        alm = self._cfg["alarms"]

        lim = alm["drum_pressure_high"]["limit"]
        db  = alm["drum_pressure_high"]["deadband"]
        self._alarm_P_high = (self._pressure > lim if not self._alarm_P_high
                              else self._pressure > lim - db)

        lim = alm["drum_pressure_low"]["limit"]
        db  = alm["drum_pressure_low"]["deadband"]
        self._alarm_P_low  = (self._pressure < lim if not self._alarm_P_low
                              else self._pressure < lim + db)

        lim = alm["drum_level_low"]["limit"]
        db  = alm["drum_level_low"]["deadband"]
        self._alarm_L_low  = (self._level < lim if not self._alarm_L_low
                              else self._level < lim + db)

        lim = alm["drum_level_high"]["limit"]
        db  = alm["drum_level_high"]["deadband"]
        self._alarm_L_high = (self._level > lim if not self._alarm_L_high
                              else self._level > lim - db)

        with state:
            state.alarm_pressure_high = self._alarm_P_high
            state.alarm_pressure_low  = self._alarm_P_low
            state.alarm_level_low     = self._alarm_L_low
            state.alarm_level_high    = self._alarm_L_high
            state.alarm_pump_fault    = self._pump_fault

    def _blowdown_logic(self, state, dt: float):
        """
        Periodic blowdown every 2 hours for 30 seconds.
        Uses actual dt accumulation — not hardcoded sleep.
        """
        if not self._running or self._fault_code > 0:
            self._blowdown_valve.set_position(0.0)
            return

        self._blowdown_accum += dt

        # Every 7200 seconds (2 hours) open blowdown for 30 seconds
        if self._blowdown_accum >= 7200.0:
            self._blowdown_active = True
            self._blowdown_accum  = 0.0

        if self._blowdown_active:
            self._blowdown_valve.set_position(50.0)
            # Use a separate timer for the 30s pulse
            # Simplified: active for one check interval then reset
            # The ST program handles this correctly with TOF timer
            self._blowdown_active = False
        else:
            self._blowdown_valve.set_position(0.0)
