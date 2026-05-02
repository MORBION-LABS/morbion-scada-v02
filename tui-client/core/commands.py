"""
core/commands.py — MORBION Scripting Language Command Definitions
MORBION SCADA v02

Single source of truth for:
  - TAG_MAP: process → tag → (register_index, scale_factor, unit, writable)
  - PROCESS_NAMES: valid process identifiers
  - FAULT_CODES: per-process fault code descriptions
  - COMMAND_HELP: help text for every verb
  - COMPLETIONS: tab completion data

Scale factor: raw_value = int(round(float(user_value) * scale))
Reverse:       eng_value = raw_value / scale
"""

from typing import Dict, Tuple, Optional

# ── Process names ──────────────────────────────────────────────────────────────

PROCESS_NAMES = [
    "pumping_station",
    "heat_exchanger",
    "boiler",
    "pipeline",
]

# ── TAG MAP ───────────────────────────────────────────────────────────────────
# Structure: process_name → tag_name → (register_index, scale_factor, unit, writable)
# writable: True = operator can write this register
# Scale factor: raw = int(round(float(eng_value) * scale))

TAG_MAP: Dict[str, Dict[str, Tuple[int, float, str, bool]]] = {
    "pumping_station": {
        "tank_level_pct":         (0,    10.0,  "%",      True),
        "tank_volume_m3":          (1,    10.0,  "m³",     False),
        "pump_speed_rpm":          (2,     1.0,  "RPM",    True),
        "pump_flow_m3hr":          (3,    10.0,  "m³/hr",  True),
        "discharge_pressure_bar":  (4,   100.0,  "bar",    True),
        "pump_current_A":          (5,    10.0,  "A",      False),
        "pump_power_kW":           (6,    10.0,  "kW",     False),
        "pump_running":            (7,     1.0,  "0/1",    True),
        "inlet_valve_pos_pct":     (8,    10.0,  "%",      True),
        "outlet_valve_pos_pct":    (9,    10.0,  "%",      True),
        "demand_flow_m3hr":        (10,   10.0,  "m³/hr",  False),
        "net_flow_m3hr":           (11,   10.0,  "m³/hr",  False),
        "pump_starts_today":       (12,    1.0,  "count",  False),
        "level_sensor_mm":         (13,    1.0,  "mm",     False),
        "fault_code":              (14,    1.0,  "code",   True),
    },
    "heat_exchanger": {
        "T_hot_in_C":              (0,    10.0,  "°C",     True),
        "T_hot_out_C":             (1,    10.0,  "°C",     True),
        "T_cold_in_C":             (2,    10.0,  "°C",     True),
        "T_cold_out_C":            (3,    10.0,  "°C",     True),
        "flow_hot_lpm":            (4,    10.0,  "L/min",  False),
        "flow_cold_lpm":           (5,    10.0,  "L/min",  False),
        "pressure_hot_in_bar":     (6,   100.0,  "bar",    False),
        "pressure_hot_out_bar":    (7,   100.0,  "bar",    False),
        "pressure_cold_in_bar":    (8,   100.0,  "bar",    False),
        "pressure_cold_out_bar":   (9,   100.0,  "bar",    False),
        "Q_duty_kW":               (10,    1.0,  "kW",     False),
        "efficiency_pct":          (11,   10.0,  "%",      False),
        "hot_pump_speed_rpm":      (12,    1.0,  "RPM",    True),
        "cold_pump_speed_rpm":     (13,    1.0,  "RPM",    True),
        "hot_valve_pos_pct":       (14,   10.0,  "%",      True),
        "cold_valve_pos_pct":      (15,   10.0,  "%",      True),
        "fault_code":              (16,    1.0,  "code",   True),
    },
    "boiler": {
        "drum_pressure_bar":       (0,   100.0,  "bar",    True),
        "drum_temp_C":             (1,    10.0,  "°C",     True),
        "drum_level_pct":          (2,    10.0,  "%",      True),
        "steam_flow_kghr":         (3,    10.0,  "kg/hr",  True),
        "feedwater_flow_kghr":     (4,    10.0,  "kg/hr",  False),
        "fuel_flow_kghr":          (5,    10.0,  "kg/hr",  False),
        "burner_state":            (6,     1.0,  "0/1/2",  True),
        "fw_pump_speed_rpm":       (7,     1.0,  "RPM",    True),
        "steam_valve_pos_pct":     (8,    10.0,  "%",      True),
        "fw_valve_pos_pct":        (9,    10.0,  "%",      True),
        "blowdown_valve_pos_pct":  (10,   10.0,  "%",      True),
        "flue_gas_temp_C":         (11,   10.0,  "°C",     False),
        "combustion_eff_pct":      (12,   10.0,  "%",      False),
        "Q_burner_kW":             (13,    1.0,  "kW",     False),
        "fault_code":              (14,    1.0,  "code",   True),
    },
    "pipeline": {
        "inlet_pressure_bar":      (0,   100.0,  "bar",    True),
        "outlet_pressure_bar":     (1,   100.0,  "bar",    True),
        "flow_rate_m3hr":          (2,    10.0,  "m³/hr",  True),
        "duty_pump_speed_rpm":     (3,     1.0,  "RPM",    True),
        "duty_pump_current_A":     (4,    10.0,  "A",      False),
        "duty_pump_running":       (5,     1.0,  "0/1",    True),
        "standby_pump_speed_rpm":  (6,     1.0,  "RPM",    True),
        "standby_pump_running":    (7,     1.0,  "0/1",    True),
        "inlet_valve_pos_pct":     (8,    10.0,  "%",      True),
        "outlet_valve_pos_pct":    (9,    10.0,  "%",      True),
        "pump_differential_bar":   (10,  100.0,  "bar",    False),
        "flow_velocity_ms":        (11,  100.0,  "m/s",    False),
        "duty_pump_power_kW":      (12,    1.0,  "kW",     False),
        "leak_flag":               (13,    1.0,  "0/1",    True),
        "fault_code":              (14,    1.0,  "code",   True),
    },
}

# ── Fault code tables ─────────────────────────────────────────────────────────

FAULT_CODES = {
    "pumping_station": {
        0: "OK",
        1: "HIGH_LEVEL — tank above 90%",
        2: "LOW_LEVEL  — tank below 10% (latched, requires reset + recovery)",
        3: "PUMP_FAULT",
        4: "DRY_RUN   — no flow while running (latched, requires reset + recovery)",
    },
    "heat_exchanger": {
        0: "OK",
        1: "PUMP_FAULT",
        2: "SENSOR_FAULT",
        3: "OVERTEMP  — auto-clears when temps recover for 10s (no reset needed)",
    },
    "boiler": {
        0: "OK",
        1: "LOW_WATER      — drum level < 20% (latched, requires reset + recovery)",
        2: "OVERPRESSURE   — drum > 10 bar  (latched, requires reset + recovery)",
        3: "FLAME_FAILURE",
        4: "PUMP_FAULT     — FW pump faulted (latched, requires reset + recovery)",
    },
    "pipeline": {
        0: "OK",
        1: "DUTY_FAULT    — duty pump faulted (latched, requires reset + recovery)",
        2: "BOTH_FAULT    — both pumps faulted (latched, requires reset + recovery)",
        3: "OVERPRESSURE  — outlet > 55 bar   (latched, requires reset + recovery)",
    },
}

# ── Operator reset note ───────────────────────────────────────────────────────

RESET_NOTE = (
    "Operator reset: write fault_code = 0 (register 14).\n"
    "Latched faults only clear when BOTH conditions are met:\n"
    "  1. operator_reset pulse received (write 0 to reg 14)\n"
    "  2. physical condition has recovered (e.g. pressure < 9.5 bar)\n"
    "If condition is still active, reset has no effect."
)

# ── Special register behaviours ───────────────────────────────────────────────

SPECIAL_NOTES = {
    ("pumping_station", "inlet_valve_pos_pct"): (
        "Special: raw value > 500 opens valve, <= 500 closes it.\n"
        "Write any value > 50.0 to open, any value <= 50.0 to close.\n"
        "Example: write pumping_station inlet_valve_pos_pct 100  → opens valve\n"
        "         write pumping_station inlet_valve_pos_pct 0    → closes valve"
    ),
    ("boiler", "burner_state"): (
        "Valid values: 0 = OFF, 1 = LOW, 2 = HIGH\n"
        "PLC will override if safety interlocks are active."
    ),
    ("boiler", "drum_pressure_bar"): (
        "Inject only. Write > 10.0 to trigger overpressure interlock.\n"
        "Example: inject boiler drum_pressure_bar 11.0"
    ),
    ("boiler", "drum_level_pct"): (
        "Inject only. Write < 20.0 to trigger low water interlock.\n"
        "Example: inject boiler drum_level_pct 15.0"
    ),
    ("pipeline", "outlet_pressure_bar"): (
        "Inject only. Write > 55.0 to trigger overpressure interlock.\n"
        "Example: inject pipeline outlet_pressure_bar 58.0"
    ),
    ("heat_exchanger", "T_cold_out_C"): (
        "Inject only. Write > 95.0 to trigger overtemp interlock.\n"
        "Example: inject heat_exchanger T_cold_out_C 96.0"
    ),
}

# ── Command help text ─────────────────────────────────────────────────────────

COMMAND_HELP = {
    "read": (
        "read <process>              — all tags for process\n"
        "read <process> <tag>        — single tag value\n"
        "read all                    — all 4 processes compact\n\n"
        "Examples:\n"
        "  read boiler\n"
        "  read boiler drum_pressure_bar\n"
        "  read all"
    ),
    "write": (
        "write <process> <tag> <value>  — write engineering-unit value\n\n"
        "The engine scales your value to raw uint16 before sending.\n"
        "After 300ms the value is read back:\n"
        "  CONFIRMED  — PLC accepted command\n"
        "  OVERRIDDEN — PLC changed value (interlock active)\n\n"
        "Examples:\n"
        "  write pumping_station pump_running 1\n"
        "  write boiler burner_state 2\n"
        "  write pipeline duty_pump_running 1\n"
        "  write heat_exchanger hot_pump_speed_rpm 800"
    ),
    "inject": (
        "inject <process> <tag> <value>  — force a sensor value for testing\n\n"
        "Semantically identical to write. Use 'inject' to signal intent:\n"
        "you are overriding a sensor for fault scenario training.\n\n"
        "Examples:\n"
        "  inject boiler drum_pressure_bar 11.0\n"
        "  inject boiler drum_level_pct 15.0\n"
        "  inject pumping_station tank_level_pct 3.0\n"
        "  inject pipeline outlet_pressure_bar 58.0\n"
        "  inject heat_exchanger T_cold_out_C 96.0\n"
        "  inject pipeline leak_flag 1"
    ),
    "fault": (
        "fault clear <process>           — write 0 to fault register (reg 14)\n"
        "fault clear all                 — clear all 4 processes\n"
        "fault status <process>          — read fault_code + description\n"
        "fault inject <process> <code>   — force fault code (advanced)\n\n"
        "Note: Latched faults only clear when physical condition has recovered.\n"
        "Writing 0 when condition is still active does nothing.\n\n"
        "Examples:\n"
        "  fault clear boiler\n"
        "  fault clear all\n"
        "  fault status pipeline"
    ),
    "watch": (
        "watch <process> <tag>                     — live 1s monitor\n"
        "watch <process> <tag> --interval <sec>    — custom interval\n"
        "watch <process>                           — key tags for process\n"
        "watch all                                 — all 4 processes compact\n\n"
        "Ctrl+C to stop. Or type 'unwatch' in another session.\n\n"
        "Examples:\n"
        "  watch boiler drum_pressure_bar\n"
        "  watch boiler drum_pressure_bar --interval 0.5\n"
        "  watch pumping_station\n"
        "  watch all"
    ),
    "unwatch": (
        "unwatch  — stop all active watch monitors"
    ),
    "alarms": (
        "alarms                              — show active alarms\n"
        "alarms history                      — last 20 alarm events\n"
        "alarms acknowledge <alarm_id>       — acknowledge one alarm\n"
        "alarms acknowledge all              — acknowledge all active\n"
        "alarms filter <CRIT|HIGH|MED|LOW>   — filter by severity\n"
        "alarms filter <process>             — filter by process\n\n"
        "Alarm IDs: PS-001..PS-006, HX-001..HX-004,\n"
        "           BL-001..BL-005, PL-001..PL-006\n\n"
        "Examples:\n"
        "  alarms\n"
        "  alarms history\n"
        "  alarms acknowledge BL-002\n"
        "  alarms filter CRIT"
    ),
    "plc": (
        "plc <process> status                — runtime status, scan count\n"
        "plc <process> source                — print ST source to terminal\n"
        "plc <process> reload                — hot reload from file on disk\n"
        "plc <process> upload <filepath>     — upload .st file\n"
        "plc <process> validate <filepath>   — validate without uploading\n"
        "plc <process> download <filepath>   — save current source to file\n"
        "plc <process> diff <filepath>       — diff running vs file on disk\n"
        "plc <process> variables             — show input/output/param map\n\n"
        "Examples:\n"
        "  plc boiler status\n"
        "  plc boiler source\n"
        "  plc boiler reload\n"
        "  plc boiler upload /home/user/boiler_v2.st\n"
        "  plc boiler validate /home/user/test.st\n"
        "  plc boiler download /tmp/boiler_backup.st\n"
        "  plc boiler diff /home/user/boiler_local.st"
    ),
    "modbus": (
        "modbus read <process> <start> <count>   — FC03 raw registers\n"
        "modbus write <process> <reg> <value>    — FC06 raw uint16\n"
        "modbus dump <process>                   — all registers decoded\n\n"
        "Shows raw uint16 AND decoded engineering values side by side.\n"
        "Use when you suspect the server is misinterpreting a register.\n\n"
        "Examples:\n"
        "  modbus dump boiler\n"
        "  modbus read pipeline 0 5\n"
        "  modbus write boiler 6 2"
    ),
    "snapshot": (
        "snapshot                        — print full plant state to terminal\n"
        "snapshot --file <filepath>      — save full plant JSON to file\n\n"
        "Examples:\n"
        "  snapshot\n"
        "  snapshot --file /tmp/plant_state.json"
    ),
    "diff": (
        "diff <process>                  — compare running ST vs file on disk\n\n"
        "Fetches the ST source currently loaded in the PLC interpreter via\n"
        "the server API and diffs it against the .st file on disk.\n"
        "Shows line-level differences. Useful after uploads.\n\n"
        "Example:\n"
        "  diff boiler"
    ),
    "batch": (
        "batch <filepath>               — run a .morbion script file\n\n"
        "Script format: one MSL command per line. # for comments.\n"
        "Commands execute sequentially. Stops on first error.\n\n"
        "Example script content:\n"
        "  # fault scenario — boiler overpressure\n"
        "  inject boiler drum_pressure_bar 11.0\n"
        "  watch boiler fault_code --interval 0.5\n"
        "  fault clear boiler\n\n"
        "Example:\n"
        "  batch /home/user/scenarios/boiler_overpressure.morbion"
    ),
    "status": (
        "status                   — server health + all processes online count\n"
        "status <process>         — one process all tags compact\n\n"
        "Examples:\n"
        "  status\n"
        "  status boiler"
    ),
    "connect": (
        "connect <ip>:<port>      — reconnect to a different server\n\n"
        "Saves the new address to config.json.\n\n"
        "Example:\n"
        "  connect 192.168.100.30:5000"
    ),
    "history": (
        "history                  — last 50 commands\n"
        "history <n>              — last N commands\n"
        "history search <term>    — search history\n\n"
        "Up/Down arrow keys navigate history in the input line."
    ),
    "help": (
        "help                     — full command list\n"
        "help <verb>              — detailed help for one verb\n"
        "help register <process>  — full register map for process\n"
        "help faults <process>    — fault code table for process\n"
        "help physics <process>   — physics and interlock summary\n\n"
        "Examples:\n"
        "  help write\n"
        "  help register boiler\n"
        "  help faults pipeline"
    ),
    "cls": (
        "cls   — clear terminal output"
    ),
    "exit": (
        "exit  — return to main menu"
    ),
    "tui": (
        "tui   — launch TUI dashboard (exits CLI, starts TUI)"
    ),
}

# ── All verbs ─────────────────────────────────────────────────────────────────

ALL_VERBS = sorted(COMMAND_HELP.keys())

# ── Tab completion data ───────────────────────────────────────────────────────

def get_completions(tokens: list) -> list:
    """
    Return list of possible completions given current token list.
    tokens: list of already-typed words (last may be partial)
    """
    if not tokens:
        return ALL_VERBS

    verb = tokens[0].lower()

    if len(tokens) == 1:
        # Complete the verb
        return [v for v in ALL_VERBS if v.startswith(verb)]

    if len(tokens) == 2:
        # Second token depends on verb
        partial = tokens[1].lower()
        if verb in ("read", "write", "inject", "watch", "status", "diff"):
            options = PROCESS_NAMES + (["all"] if verb in ("read", "watch") else [])
            return [o for o in options if o.startswith(partial)]
        if verb == "fault":
            return [o for o in ("clear", "status", "inject") if o.startswith(partial)]
        if verb == "alarms":
            return [o for o in ("history", "acknowledge", "filter") if o.startswith(partial)]
        if verb == "plc":
            return [o for o in PROCESS_NAMES if o.startswith(partial)]
        if verb == "modbus":
            return [o for o in ("read", "write", "dump") if o.startswith(partial)]
        if verb == "help":
            opts = ALL_VERBS + ["register", "faults", "physics"]
            return [o for o in opts if o.startswith(partial)]

    if len(tokens) == 3:
        partial = tokens[2].lower()
        if verb in ("write", "inject") and tokens[1] in PROCESS_NAMES:
            tags = list(TAG_MAP.get(tokens[1], {}).keys())
            return [t for t in tags if t.lower().startswith(partial)]
        if verb == "watch" and tokens[1] in PROCESS_NAMES:
            tags = list(TAG_MAP.get(tokens[1], {}).keys())
            return [t for t in tags if t.lower().startswith(partial)]
        if verb == "read" and tokens[1] in PROCESS_NAMES:
            tags = list(TAG_MAP.get(tokens[1], {}).keys())
            return [t for t in tags if t.lower().startswith(partial)]
        if verb == "plc":
            subcmds = ["status", "source", "reload", "upload",
                       "validate", "download", "diff", "variables"]
            return [s for s in subcmds if s.startswith(partial)]
        if verb == "fault" and tokens[1] == "clear":
            return [p for p in (PROCESS_NAMES + ["all"]) if p.startswith(partial)]
        if verb == "fault" and tokens[1] in ("status", "inject"):
            return [p for p in PROCESS_NAMES if p.startswith(partial)]
        if verb in ("help",) and tokens[1] in ("register", "faults", "physics"):
            return [p for p in PROCESS_NAMES if p.startswith(partial)]

    return []


# ── Register map display ──────────────────────────────────────────────────────

def format_register_map(process: str) -> str:
    """Returns formatted register map string for a process."""
    if process not in TAG_MAP:
        return f"Unknown process: {process}"
    lines = [
        f"Register map — {process}",
        "─" * 70,
        f"{'REG':<4} {'TAG':<30} {'SCALE':<8} {'UNIT':<10} {'WRITE'}",
        "─" * 70,
    ]
    for tag, (reg, scale, unit, writable) in TAG_MAP[process].items():
        w = "YES" if writable else "no"
        lines.append(f"{reg:<4} {tag:<30} ×{scale:<7.0f} {unit:<10} {w}")
    lines.append("─" * 70)
    note = SPECIAL_NOTES.get(("pumping_station", "inlet_valve_pos_pct"), "") if process == "pumping_station" else ""
    if note:
        lines.append("")
        lines.append("Special — inlet_valve_pos_pct:")
        lines.append("  Raw > 500 → opens valve | Raw ≤ 500 → closes valve")
    return "\n".join(lines)


def format_fault_table(process: str) -> str:
    """Returns formatted fault code table for a process."""
    if process not in FAULT_CODES:
        return f"Unknown process: {process}"
    codes = FAULT_CODES[process]
    lines = [
        f"Fault codes — {process}",
        "─" * 60,
    ]
    for code, desc in codes.items():
        lines.append(f"  {code}  {desc}")
    lines.append("─" * 60)
    lines.append("")
    lines.append(RESET_NOTE)
    return "\n".join(lines)
