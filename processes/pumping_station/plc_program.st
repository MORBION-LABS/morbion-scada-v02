(* ================================================================
   PUMPING STATION PLC PROGRAM
   Nairobi Water Municipal Pumping Station
   MORBION SCADA v02 — IEC 61131-3 Structured Text

   REVISION HISTORY:
     2026-04-XX  v02    Initial MORBION SCADA v02 version
     2026-04-23  v02a   [CHANGE 1] Complete rewrite
                          - Added fault recovery logic with operator_reset
                          - Added process_running check for cold start
                          - Changed dry_run_timer from 10s to 30s PT
                          - Added outlet_valve_sp = 0.0 in fault_code > 1 block
                          - Added process_running block to stop all outputs when stopped

   Control Strategy:
     - Level-based pump start/stop with latching
     - Dry run protection with TON timer (accumulates across scans)
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
    dry_run_timer      : TON;          (* Accumulator for dry run detection *)
    conservation_tmr : TON;          (* Accumulator for conservation check *)
    conservation_error: REAL;         (* Flow balance error magnitude *)
END_VAR

(* ── FAULT RECOVERY ───────────────────────────────────────────────
   CHANGE 2026-04-23: Added fault recovery logic
   operator_reset is a one-shot pulse set by operator control writes.
   When operator writes register 14 with value 0, operator_reset becomes TRUE.
   This pulse clears latched faults when conditions are safe.

   Recovery conditions:
   - fault_code = 2 (LOW_LEVEL): clear when level > 8%
   - fault_code = 3 (PUMP_FAULT): clear when pressure < 7.5 bar
   - fault_code = 4 (DRY_RUN): clear on operator reset

   NOTE: This only clears the fault_code AFTER safety checks pass.
         If conditions still unsafe, fault will re-trip on next scan.
   ──────────────────────────────────────────────────────── *)

IF operator_reset AND fault_code = 2 AND level_sensor_pct > 8.0 THEN
    fault_code := 0;
END_IF;

IF operator_reset AND fault_code = 3 AND discharge_pressure_bar < 7.5 THEN
    fault_code := 0;
END_IF;

IF operator_reset AND fault_code = 4 THEN
    fault_code := 0;
END_IF;

(* ── SAFETY INTERLOCKS ─────────────────────────────────────────
   CHECKED EVERY SCAN before anything else.
   These are hard interlocks — not operator overridable.

   1. LOW_LEVEL: < 5% tank level
      → Hard stop pump and inlet valve
      → Close outlet valve to prevent drain
      → Set fault_code = 2 (dry run imminent)

   2. HIGH_PRESSURE: > 8.0 bar discharge
      → Hard stop pump and inlet valve
      → Set fault_code = 3 (pump/pipe protection)

   3. ACTIVE FAULT: fault_code > 1
      → Hold pump stopped until operator clears
      → (fault_code = 1 is HIGH_LEVEL, allow clearing)

   CHANGE 2026-04-23: Added outlet_valve_sp = 0.0 in fault_code > 1
   ─────────────────────────────────────────────────���────── *)

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
    outlet_valve_sp := 0.0;     (* CHANGE 2026-04-23: Close outlet on fault *)
    RETURN;
END_IF;

(* ── PROCESS NOT RUNNING ─────────────────────────────────────
   CHANGE 2026-04-23: Added process_running check
   When process is stopped (e.g., on shutdown), stop all outputs.
   This prevents pump running in uncontrolled state.
   ──────────────────────────────────────────────────────── *)

IF NOT process_running THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    outlet_valve_sp := 0.0;
    RETURN;
END_IF;

(* ── LEVEL CONTROL ─────────────────────────────────────────
   LATCHED start/stop based on tank level.

   Start: level < level_start (default 20%) AND no faults
   Stop:  level > level_stop (default 80%)

   Uses latching — once started, pump stays running
   until level reaches stop threshold regardless of fluctuations.
   This prevents short-cycling on wave action.

   Parameters defined in plc_variables.yaml:
     level_start: 20.0  (percentage)
     level_stop:  80.0  (percentage)
   ──────────────────────────────────────────────────────── *)

IF level_sensor_pct < level_start AND fault_code = 0 THEN
    pump_run_cmd    := TRUE;
    inlet_valve_cmd := TRUE;
END_IF;

IF level_sensor_pct > level_stop THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
END_IF;

(* ── OUTLET VALVE CONTROL ─────────────────────────────────
   Modulates outlet valve position based on tank level:

   > 88%: Fault mode — restrict outlet to 20%
          Set fault_code = 1 (HIGH_LEVEL)
   < 8%:  Minimum — outlet at 0%
   Normal: 85% setpoint

   Auto-clear: If fault_code = 1 AND level drops below 82%,
             clear the fault.
   ──────────────────────────────────────────────────────── *)

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

(* ── DRY RUN PROTECTION ─────────────────────────────────
   CHANGE 2026-04-23: Increased PT from 10.0 to 30.0 seconds

   TON timer accumulates elapsed time across scans.
   Timer resets when condition (IN) becomes FALSE.

   Condition: pump_running AND flow < 5.0 m³/hr
   Timer:     30 seconds PT (changed from 10s)

   If pump runs with inadequate flow for 30 continuous seconds,
   assumpt dry run condition — stop pump to protect impeller.

   NOTE: flow < 5.0 allows for minimal flow during startup.
         Actual dry run is flow = 0 or very low sustained.
   ──────────────────────────────────────────────────────── *)

dry_run_timer(IN := pump_running AND flow_m3hr < 5.0, PT := 30.0);

IF dry_run_timer.Q THEN
    pump_run_cmd    := FALSE;
    inlet_valve_cmd := FALSE;
    fault_code      := 4;
END_IF;

(* ── CONSERVATION LAW CHECK ────────────────────────────────
   Conservation of mass: Q_in = Q_out + dV/dt

   For steady state: Q_pump = Q_demand + Q_net

   Error = |flow - demand - net|
   If error > 15.0 m³/hr sustained for 5 seconds →
   conservation_alarm = TRUE

   This flags:
   - Sensor manipulation
   - Real leak in pipeline
   - Pump degradation

   Alarm only active when pump is running.
   ──────────────────────────────────────────────────────── *)

conservation_error := ABS(flow_m3hr - demand_flow_m3hr - net_flow_m3hr);

conservation_tmr(IN := conservation_error > 15.0 AND pump_running, PT := 5.0);

IF conservation_tmr.Q THEN
    conservation_alarm := TRUE;
ELSE
    conservation_alarm := FALSE;
END_IF;