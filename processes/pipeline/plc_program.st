(* ================================================================
   PIPELINE PLC PROGRAM
   Kenya Pipeline Company — Petroleum Transfer
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   Control Strategy:
     - Duty pump runs at rated speed
     - Standby pump starts automatically on duty fault
     - Outlet valve modulates to maintain target pressure
     - Leak detection via flow balance
     - Overpressure protection — latched interlock
     - Both-fault emergency shutdown
   ================================================================ *)

VAR
    duty_fault_latch      : SR;
    both_fault_latch      : SR;
    overpressure_latch    : SR;
    standby_start_timer   : TON;
    leak_confirm_timer    : TON;
    pressure_recover_tmr  : TON;
END_VAR

(* ── OVERPRESSURE INTERLOCK — latched ────────────────────────── *)

overpressure_latch(
    S1 := outlet_pressure_bar > 55.0,
    R  := operator_reset AND outlet_pressure_bar < 52.0
);

IF overpressure_latch.Q1 THEN
    duty_pump_cmd    := FALSE;
    standby_pump_cmd := FALSE;
    inlet_valve_cmd  := FALSE;
    outlet_valve_sp  := 0.0;
    fault_code       := 3;
    RETURN;
END_IF;

(* ── BOTH PUMPS FAULTED — emergency shutdown ─────────────────── *)

both_fault_latch(
    S1 := duty_pump_fault AND standby_pump_fault,
    R  := operator_reset AND NOT duty_pump_fault AND NOT standby_pump_fault
);

IF both_fault_latch.Q1 THEN
    duty_pump_cmd    := FALSE;
    standby_pump_cmd := FALSE;
    inlet_valve_cmd  := FALSE;
    outlet_valve_sp  := 20.0;
    fault_code       := 2;
    RETURN;
END_IF;

(* ── PROCESS NOT RUNNING ──────────────────────────────────────── *)

IF NOT process_running THEN
    duty_pump_cmd    := FALSE;
    standby_pump_cmd := FALSE;
    inlet_valve_cmd  := FALSE;
    outlet_valve_sp  := 0.0;
    RETURN;
END_IF;

(* ── DUTY-STANDBY LOGIC ───────────────────────────────────────── *)

(* Duty fault latch — standby takes over                          *)
duty_fault_latch(
    S1 := duty_pump_fault,
    R  := operator_reset AND NOT duty_pump_fault
);

IF duty_fault_latch.Q1 THEN
    duty_pump_cmd := FALSE;
    fault_code    := 1;

    (* Small delay before starting standby — avoid simultaneous   *)
    (* starts which would cause current surge on 6600V bus        *)
    standby_start_timer(IN := duty_pump_fault, PT := 2.0);

    IF standby_start_timer.Q THEN
        standby_pump_cmd := TRUE;
    END_IF;

ELSE
    (* Normal operation — duty pump running, standby at rest      *)
    duty_pump_cmd    := TRUE;
    standby_pump_cmd := FALSE;
    inlet_valve_cmd  := TRUE;

    (* Clear duty fault code when operator resets                 *)
    IF fault_code = 1 AND operator_reset THEN
        fault_code := 0;
    END_IF;
END_IF;

(* ── OUTLET VALVE PRESSURE CONTROL ───────────────────────────── *)
(* Proportional control — modulate valve to maintain target       *)

pressure_error  := outlet_pressure_nominal - outlet_pressure_bar;
outlet_valve_sp := LIMIT(20.0,
                         outlet_valve_setpoint + (pressure_error * 1.5),
                         95.0);

(* ── LEAK DETECTION ──────────────────────────────────────────── *)
(* Compare expected flow from pump curve vs measured flow         *)
(* Sustained discrepancy > threshold = leak suspected             *)

flow_discrepancy := ABS(expected_flow - flow_rate_m3hr);

leak_confirm_timer(
    IN := flow_discrepancy > leak_threshold AND duty_pump_running,
    PT := 10.0
);

IF leak_confirm_timer.Q THEN
    leak_flag_cmd     := TRUE;
    leak_alarm        := TRUE;
ELSE
    leak_flag_cmd     := FALSE;
    leak_alarm        := FALSE;
END_IF;

(* ── INLET LOW PRESSURE ALARM ─────────────────────────────────── *)

IF inlet_pressure_bar < 1.0 THEN
    inlet_low_alarm := TRUE;
ELSE
    inlet_low_alarm := FALSE;
END_IF;

(* ── OUTLET LOW PRESSURE ALARM ────────────────────────────────── *)

IF outlet_pressure_bar < 38.0 AND duty_pump_running THEN
    outlet_low_alarm := TRUE;
ELSE
    outlet_low_alarm := FALSE;
END_IF;
