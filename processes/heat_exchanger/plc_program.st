(* ================================================================
   HEAT EXCHANGER PLC PROGRAM
   KenGen Olkaria Geothermal Heat Recovery
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   Control Strategy:
     - Start/stop both pumps based on process_running flag
     - Maintain valves at configured setpoints
     - Overtemp protection — close hot valve on high T_cold_out
     - Efficiency monitoring — alarm on low efficiency
     - Pump fault handling — trip on dual fault
   ================================================================ *)

(* ── SAFETY INTERLOCKS ────────────────────────────────────────── *)

(* Cold outlet overtemp — immediate hot valve closure *)
IF T_cold_out > 95.0 THEN
    hot_valve_cmd   := 0.0;
    fault_code      := 3;
    RETURN;
END_IF;

(* Hot outlet overtemp *)
IF T_hot_out > 165.0 THEN
    hot_valve_cmd   := 20.0;
    fault_code      := 3;
    RETURN;
END_IF;

(* Both pumps faulted — full shutdown *)
IF hot_pump_fault AND cold_pump_fault THEN
    hot_pump_cmd    := FALSE;
    cold_pump_cmd   := FALSE;
    hot_valve_cmd   := 0.0;
    cold_valve_cmd  := 0.0;
    fault_code      := 1;
    RETURN;
END_IF;

(* ── PROCESS NOT RUNNING ──────────────────────────────────────── *)

IF NOT process_running THEN
    hot_pump_cmd   := FALSE;
    cold_pump_cmd  := FALSE;
    hot_valve_cmd  := 0.0;
    cold_valve_cmd := 0.0;
    RETURN;
END_IF;

(* ── NORMAL OPERATION ─────────────────────────────────────────── *)

(* Start pumps if not faulted *)
IF NOT hot_pump_fault THEN
    hot_pump_cmd := TRUE;
END_IF;

IF NOT cold_pump_fault THEN
    cold_pump_cmd := TRUE;
END_IF;

(* Valve control — maintain configured setpoints *)
(* Modulate hot valve down if cold outlet approaching limit *)
IF T_cold_out > 85.0 THEN
    hot_valve_cmd := LIMIT(30.0, hot_valve_sp - ((T_cold_out - 85.0) * 5.0), hot_valve_sp);
ELSE
    hot_valve_cmd := hot_valve_sp;
END_IF;

cold_valve_cmd := cold_valve_sp;

(* ── FAULT RECOVERY ───────────────────────────────────────────── *)

(* Clear overtemp fault when temperatures recover *)
IF fault_code = 3 AND T_cold_out < 88.0 AND T_hot_out < 158.0 THEN
    fault_code := 0;
END_IF;

(* Clear pump fault when individual pump recovers *)
IF fault_code = 1 AND NOT hot_pump_fault AND NOT cold_pump_fault THEN
    fault_code := 0;
END_IF;

(* ── EFFICIENCY ALARM ─────────────────────────────────────────── *)

IF efficiency < 60.0 AND process_running THEN
    efficiency_alarm := TRUE;
ELSE
    efficiency_alarm := FALSE;
END_IF;