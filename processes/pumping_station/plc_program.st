(* ================================================================
   PUMPING STATION PLC PROGRAM
   Nairobi Water Municipal Pumping Station
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   Control Strategy:
     - Level-based pump start/stop with latching
     - Dry run protection with TON timer
     - Outlet valve modulation on high/low level alarms
     - Conservation law monitoring
     - Safety interlocks checked first every scan
     - Fault recovery via operator_reset one-shot pulse

   Fault Codes:
     0 = OK (normal operation)
     1 = HIGH_LEVEL (tank > 88%, outlet restricted)
     2 = LOW_LEVEL (tank < 5%, dry run imminent)
     3 = PUMP_FAULT (discharge pressure > 8 bar)
     4 = DRY_RUN (pump running with no flow > 30s)
   ================================================================ *)

VAR
    dry_run_timer      : TON;
    conservation_tmr   : TON;
    conservation_error : REAL;
END_VAR

(* ── FAULT RECOVERY ───────────────────────────────────────────── *)

IF operator_reset AND fault_code = 2 AND level_sensor_pct > 8.0 THEN
    fault_code := 0;
END_IF;

IF operator_reset AND fault_code = 3 AND discharge_pressure_bar < 7.5 THEN
    fault_code := 0;
END_IF;

IF operator_reset AND fault_code = 4 THEN
    fault_code := 0;
END_IF;

(* ── SAFETY INTERLOCKS ────────────────────────────────────────── *)

IF level_sensor_pct < 5.0 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    outlet_valve_sp := 0.0;
    fault_code      := 2;
    RETURN;
END_IF;

IF discharge_pressure_bar > 8.0 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    fault_code      := 3;
    RETURN;
END_IF;

IF fault_code > 1 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    outlet_valve_sp := 0.0;
    RETURN;
END_IF;

(* ── PROCESS NOT RUNNING ──────────────────────────────────────── *)

IF NOT process_running THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    outlet_valve_sp := 0.0;
    RETURN;
END_IF;

(* ── LEVEL CONTROL — latched start/stop ──────────────────────── *)

IF level_sensor_pct < level_start AND fault_code = 0 THEN
    pump_run_cmd    := TRUE;
    inlet_valve_cmd := TRUE;
END_IF;

IF level_sensor_pct > level_stop THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
END_IF;

(* ── OUTLET VALVE CONTROL ─────────────────────────────────────── *)

IF level_sensor_pct > 88.0 THEN
    outlet_valve_sp := 20.0;
    fault_code      := 1;
ELSIF level_sensor_pct < 8.0 THEN
    outlet_valve_sp := 0.0;
ELSE
    outlet_valve_sp := 85.0;
    IF fault_code = 1 AND level_sensor_pct < 82.0 THEN
        fault_code := 0;
    END_IF;
END_IF;

(* ── DRY RUN PROTECTION ───────────────────────────────────────── *)

dry_run_timer(IN := pump_running AND flow_m3hr < 5.0, PT := 30.0);

IF dry_run_timer.Q THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    fault_code      := 4;
END_IF;

(* ── CONSERVATION LAW CHECK ───────────────────────────────────── *)

conservation_error := ABS(flow_m3hr - demand_flow_m3hr - net_flow_m3hr);

conservation_tmr(IN := conservation_error > 15.0 AND pump_running, PT := 5.0);

IF conservation_tmr.Q THEN
    conservation_alarm := TRUE;
ELSE
    conservation_alarm := FALSE;
END_IF;
