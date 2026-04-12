(* ================================================================
   PUMPING STATION PLC PROGRAM
   Nairobi Water Municipal Pumping Station
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   Control Strategy:
     - Level-based pump start/stop
     - Dry run protection with TON timer
     - Outlet valve modulation on alarms
     - Conservation law monitoring
     - All safety interlocks checked first
   ================================================================ *)

(* ── SAFETY INTERLOCKS — checked every scan before anything else ── *)

(* Critical low level — dry run imminent *)
IF level_sensor_pct < 5.0 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    outlet_valve_sp := 0.0;
    fault_code      := 2;
    RETURN;
END_IF;

(* High discharge pressure — protect pump and pipework *)
IF discharge_pressure_bar > 8.0 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    fault_code      := 3;
    RETURN;
END_IF;

(* Active fault other than HIGH_LEVEL — hold until operator clears *)
IF fault_code > 1 THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    RETURN;
END_IF;

(* ── LEVEL CONTROL ────────────────────────────────────────────── *)

(* Start pump when level falls below start threshold *)
IF level_sensor_pct < level_start AND fault_code = 0 THEN
    pump_run_cmd    := TRUE;
    inlet_valve_cmd := TRUE;
END_IF;

(* Stop pump when level reaches stop threshold *)
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
(* TON timer: pump running with no flow for 10s trips the pump    *)

dry_run_active := TON(
    pump_running AND flow_m3hr < 5.0,
    10.0
);

IF dry_run_active THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    fault_code      := 4;
END_IF;

(* ── CONSERVATION LAW CHECK ───────────────────────────────────── *)
(* Q_pump * dt = delta_V + Q_demand * dt                          *)
(* Violation flags sensor manipulation or real leak               *)

conservation_error := ABS(flow_m3hr - demand_flow_m3hr - net_flow_m3hr);

IF conservation_error > 15.0 AND pump_running THEN
    conservation_alarm := TRUE;
ELSE
    conservation_alarm := FALSE;
END_IF;