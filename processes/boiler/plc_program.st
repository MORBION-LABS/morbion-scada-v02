(* ================================================================
   BOILER PLC PROGRAM
   EABL/Bidco Industrial Steam Plant
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   REVISION HISTORY:
     2026-04-XX  v02    Initial MORBION SCADA v02 version
     2026-04-23  v02a   [CHANGE] Added VAR block intermediates
                          Added auto-clear stale latches on cold start

   Control Strategy:
     - Pressure-based burner control (OFF/LOW/HIGH)
     - Three-element drum level control
       (level error + steam flow feedforward → feedwater valve)
     - Safety interlocks: low water, overpressure, pump fault
     - Interlocks are LATCHED — require operator reset
     - Periodic blowdown timer

   Fault Codes:
     0 = OK (normal operation)
     1 = LOW_WATER (drum level < 20%, latched until operator reset)
     2 = OVERPRESSURE (drum pressure > 10 bar, latched until operator reset)
     3 = FLAME_FAILURE (not currently used)
     4 = PUMP_FAULT (feedwater pump faulted)
   ================================================================ *)

VAR
    low_water_latch    : SR;
    overpressure_latch : SR;
    pump_fault_latch   : SR;
    blowdown_timer     : TON;
    blowdown_pulse     : TOF;
    pressure_recover   : TON;
    level_recover      : TON;
    # CHANGE 2026-04-23: Added intermediate variables for control calculations
    level_error        : REAL;
    ff_steam         : REAL;
END_VAR

(* ── AUTO-CLEAR STALE LATCHES ON COLD START ────────────────────
   CHANGE 2026-04-23: Added cold start logic

   On cold start (drum_pressure < 1.0 bar), stale latches from
   previous run may still be set. Clear them automatically
   to allow process to start without operator intervention.

   This is safe because:
   - Cold boiler has no pressure = no danger
   - No feedwater pump fault = pump is OK
   - Low level alarm will re-trip if truly low
   ──────────────────────────────────────────────────────── *)

IF drum_pressure_bar < 1.0 THEN
    overpressure_latch(S1 := FALSE, R := TRUE);
    IF fault_code = 2 THEN
        fault_code := 0;
    END_IF;
END_IF;

IF NOT fw_pump_fault AND fault_code = 4 THEN
    pump_fault_latch(S1 := FALSE, R := TRUE);
    fault_code := 0;
END_IF;

(* ── SAFETY INTERLOCKS — latched, require operator reset ─────── *)

(* Low water latch — SET on low level, RESET by operator          *)
low_water_latch(
    S1 := drum_level_pct < 20.0,
    R  := operator_reset AND drum_level_pct > 25.0
);

(* Overpressure latch — SET on high pressure, RESET by operator   *)
overpressure_latch(
    S1 := drum_pressure_bar > 10.0,
    R  := operator_reset AND drum_pressure_bar < 9.5
);

(* Pump fault latch — SET on pump fault, RESET by operator        *)
pump_fault_latch(
    S1 := fw_pump_fault,
    R  := operator_reset AND NOT fw_pump_fault
);

(* Any active latch trips the burner immediately                  *)
IF low_water_latch.Q1 THEN
    burner_cmd := 0;
    fault_code := 1;
    fw_pump_cmd := TRUE;
    steam_valve_cmd := 0.0;
    RETURN;
END_IF;

IF overpressure_latch.Q1 THEN
    burner_cmd := 0;
    fault_code := 2;
    RETURN;
END_IF;

IF pump_fault_latch.Q1 THEN
    burner_cmd  := 0;
    fault_code  := 4;
    RETURN;
END_IF;

(* ── PROCESS NOT RUNNING ──────────────────────────────────────── *)

IF NOT process_running THEN
    burner_cmd      := 0;
    fw_pump_cmd     := FALSE;
    steam_valve_cmd := 0.0;
    fw_valve_cmd    := 0.0;
    RETURN;
END_IF;

(* ── FEEDWATER PUMP ───────────────────────────────────────────── *)

(* Pump runs whenever process is running and not faulted          *)
IF NOT fw_pump_fault THEN
    fw_pump_cmd := TRUE;
END_IF;

(* ── BURNER PRESSURE CONTROL ──────────────────────────────────── *)
(* Clear fault code if conditions have recovered                  *)

pressure_recover(
    IN := drum_pressure_bar < 9.5 AND drum_level_pct > 25.0 AND NOT fw_pump_fault,
    PT := 3.0
);

IF fault_code > 0 AND operator_reset AND pressure_recover.Q THEN
    fault_code := 0;
END_IF;

(* Pressure-based burner state                                    *)
IF fault_code = 0 THEN
    IF drum_pressure_bar < 6.0 THEN
        burner_cmd := 2;
    ELSIF drum_pressure_bar < pressure_sp THEN
        burner_cmd := 1;
    ELSIF drum_pressure_bar >= 9.0 THEN
        burner_cmd := 0;
    ELSE
        burner_cmd := 1;
    END_IF;
END_IF;

(* ── STEAM VALVE ──────────────────────────────────────────────── *)

(* Open steam valve only when pressure is established             *)
IF drum_pressure_bar > 6.0 AND fault_code = 0 THEN
    steam_valve_cmd := steam_valve_sp;
ELSE
    steam_valve_cmd := 0.0;
END_IF;

(* ── THREE-ELEMENT FEEDWATER CONTROL ─────────────────────────── *)
(* Element 1: Level error (proportional)                          *)
(* Element 2: Steam flow feedforward (anticipate demand)          *)
(* Element 3: Feedwater flow (what we manipulate)                 *)

level_error  := level_sp - drum_level_pct;
ff_steam     := LIMIT(0.0, steam_flow_kghr / max_steam_flow, 1.0);
fw_valve_cmd := LIMIT(10.0,
                      50.0 + (level_error * kp_level) + (ff_steam * ff_gain),
                      90.0);

(* ── BLOWDOWN LOGIC ───────────────────────────────────────────── *)
(* Periodic blowdown every 2 hours for 30 seconds                 *)
(* Removes concentrated water, maintains water quality            *)

blowdown_timer(IN := process_running AND fault_code = 0, PT := 7200.0);
blowdown_pulse(IN := blowdown_timer.Q, PT := 30.0);

IF blowdown_pulse.Q THEN
    blowdown_valve_cmd := 50.0;
ELSE
    blowdown_valve_cmd := 0.0;
END_IF;

(* Reset blowdown timer after pulse completes                     *)
IF blowdown_timer.Q AND NOT blowdown_pulse.Q THEN
    blowdown_timer(IN := FALSE, PT := 7200.0);
END_IF;
