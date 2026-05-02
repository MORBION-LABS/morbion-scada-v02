"""
commands.py — MSL Vocabulary and Tag Definitions
MORBION SCADA v02

Source of Truth for process tag-to-register mapping.
Defines the syntax and help metadata for the Scripting Language.
"""

# ── TAG MAP ──────────────────────────────────────────────────────────────────
# Format: "tag_name": (register_index, scale_factor)
# Raw Modbus Value = int(round(Engineering_Value * scale_factor))

TAG_MAP = {
    "pumping_station": {
        "tank_level_pct":          (0,   10),
        "pump_speed_rpm":           (2,    1),
        "pump_flow_m3hr":           (3,   10),
        "discharge_pressure_bar":   (4,  100),
        "pump_running":             (7,    1),
        "inlet_valve_pos_pct":      (8,   10),
        "outlet_valve_pos_pct":     (9,   10),
        "fault_code":               (14,   1),
    },
    "heat_exchanger": {
        "T_hot_in_C":               (0,   10),
        "T_hot_out_C":              (1,   10),
        "T_cold_in_C":              (2,   10),
        "T_cold_out_C":             (3,   10),
        "hot_pump_speed_rpm":       (12,   1),
        "cold_pump_speed_rpm":      (13,   1),
        "hot_valve_pos_pct":        (14,  10),
        "cold_valve_pos_pct":       (15,  10),
        "fault_code":               (16,   1),
    },
    "boiler": {
        "drum_pressure_bar":        (0,  100),
        "drum_temp_C":              (1,   10),
        "drum_level_pct":           (2,   10),
        "steam_flow_kghr":          (3,   10),
        "burner_state":             (6,    1),
        "fw_pump_speed_rpm":        (7,    1),
        "steam_valve_pos_pct":      (8,   10),
        "fw_valve_pos_pct":         (9,   10),
        "blowdown_valve_pos_pct":   (10,  10),
        "fault_code":               (14,   1),
    },
    "pipeline": {
        "inlet_pressure_bar":       (0,  100),
        "outlet_pressure_bar":      (1,  100),
        "flow_rate_m3hr":           (2,   10),
        "duty_pump_speed_rpm":      (3,    1),
        "duty_pump_running":        (5,    1),
        "standby_pump_speed_rpm":   (6,    1),
        "standby_pump_running":     (7,    1),
        "inlet_valve_pos_pct":      (8,   10),
        "outlet_valve_pos_pct":     (9,   10),
        "leak_flag":                (13,   1),
        "fault_code":               (14,   1),
    },
}

# ── COMMAND METADATA ─────────────────────────────────────────────────────────

COMMAND_HELP = {
    "read": {
        "syntax": "read <process> [tag]",
        "desc": "Read all tags or a single tag from a process. Use 'read all' for a summary."
    },
    "write": {
        "syntax": "write <process> <tag> <value>",
        "desc": "Write engineering unit value to a specific process tag."
    },
    "inject": {
        "syntax": "inject <process> <tag> <value>",
        "desc": "Alias for 'write'. Used semantically for sensor manipulation."
    },
    "fault": {
        "syntax": "fault <clear|status|inject> <process> [code]",
        "desc": "Manage process faults. 'fault clear all' clears all station faults."
    },
    "watch": {
        "syntax": "watch <process> [tag] [--interval s]",
        "desc": "Start a live 1s monitor for a process or specific tag."
    },
    "unwatch": {
        "syntax": "unwatch",
        "desc": "Stop all active live monitors."
    },
    "alarms": {
        "syntax": "alarms <history|acknowledge|filter>",
        "desc": "Access alarm subsystem. Use 'alarms acknowledge <id>' to clear."
    },
    "plc": {
        "syntax": "plc <process> <status|source|reload|upload>",
        "desc": "Interact with the IEC 61131-3 runtime on the target process."
    },
    "modbus": {
        "syntax": "modbus <read|write|dump> <process> <reg> [count|value]",
        "desc": "Raw Modbus TCP access (FC03/FC06). Use with caution."
    },
    "status": {
        "syntax": "status [process]",
        "desc": "Check server and process connectivity status."
    },
    "connect": {
        "syntax": "connect <ip>:<port>",
        "desc": "Change target SCADA server without restarting client."
    },
    "batch": {
        "syntax": "batch <filepath>",
        "desc": "Execute a .morbion script file sequentially."
    },
    "history": {
        "syntax": "history [n]",
        "desc": "Show last n commands executed."
    },
    "help": {
        "syntax": "help [verb]",
        "desc": "Show help summary or details for a specific command."
    },
    "cls": {
        "syntax": "cls",
        "desc": "Clear terminal console."
    }
}
