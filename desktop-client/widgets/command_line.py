"""
command_line.py — Operator Command Line Terminal
MORBION SCADA v02

Terminal-style widget at bottom of main window.
Full command vocabulary. Tab completion. History navigation.
Emits command_entered signal with parsed command dict.
Main window executes the command and calls print_result().
"""
"""
command_line.py — MORBION SCADA Scripting Engine
MORBION SCADA v02

Full command language. Tab completion. Arrow key history.
Verify-after-write pattern on all control writes.
History persists to disk between sessions.
"""

import os
import json
import time
import logging
import threading
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QLabel, QPushButton,
)
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui     import QTextCursor, QKeyEvent, QColor, QFont

import theme

log = logging.getLogger("command_line")

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", ".cmd_history")

# ── Aliases ───────────────────────────────────────────────────────────────────

PROCESS_ALIASES = {
    "ps":  "pumping_station",
    "hx":  "heat_exchanger",
    "bl":  "boiler",
    "pl":  "pipeline",
    "pumping_station": "pumping_station",
    "heat_exchanger":  "heat_exchanger",
    "boiler":          "boiler",
    "pipeline":        "pipeline",
}

VALUE_ALIASES = {
    "on":    1, "off":   0,
    "true":  1, "false": 0,
    "start": 1, "stop":  0,
    "high":  2, "low":   1,
    "open":  1, "close": 0,
}

# TAG → (register, scale_factor, description)
TAG_MAP = {
    "pumping_station": {
        "tank_level_pct":        (0,  10,   "%"),
        "level":                 (0,  10,   "%"),
        "pump_speed_rpm":        (2,   1,   "RPM"),
        "speed":                 (2,   1,   "RPM"),
        "pump_flow_m3hr":        (3,  10,   "m³/hr"),
        "flow":                  (3,  10,   "m³/hr"),
        "discharge_pressure_bar":(4, 100,   "bar"),
        "pump_running":          (7,   1,   "0/1"),
        "pump":                  (7,   1,   "0/1"),
        "inlet_valve_pos_pct":   (8,  10,   "%"),
        "outlet_valve_pos_pct":  (9,  10,   "%"),
        "fault_code":            (14,  1,   "code"),
        "fault":                 (14,  1,   "code"),
    },
    "heat_exchanger": {
        "T_hot_in_C":            (0,  10,   "°C"),
        "T_hot_out_C":           (1,  10,   "°C"),
        "T_cold_in_C":           (2,  10,   "°C"),
        "T_cold_out_C":          (3,  10,   "°C"),
        "t_cold_out":            (3,  10,   "°C"),
        "hot_pump_speed_rpm":    (12,  1,   "RPM"),
        "cold_pump_speed_rpm":   (13,  1,   "RPM"),
        "hot_valve_pos_pct":     (14, 10,   "%"),
        "cold_valve_pos_pct":    (15, 10,   "%"),
        "fault_code":            (16,  1,   "code"),
        "fault":                 (16,  1,   "code"),
    },
    "boiler": {
        "drum_pressure_bar":     (0, 100,   "bar"),
        "pressure":              (0, 100,   "bar"),
        "drum_temp_C":           (1,  10,   "°C"),
        "drum_level_pct":        (2,  10,   "%"),
        "steam_flow_kghr":       (3,  10,   "kg/hr"),
        "burner_state":          (6,   1,   "0/1/2"),
        "burner":                (6,   1,   "0/1/2"),
        "fw_pump_speed_rpm":     (7,   1,   "RPM"),
        "steam_valve_pos_pct":   (8,  10,   "%"),
        "fw_valve_pos_pct":      (9,  10,   "%"),
        "blowdown_valve_pos_pct":(10, 10,   "%"),
        "fault_code":            (14,  1,   "code"),
        "fault":                 (14,  1,   "code"),
    },
    "pipeline": {
        "inlet_pressure_bar":    (0, 100,   "bar"),
        "outlet_pressure_bar":   (1, 100,   "bar"),
        "outlet":                (1, 100,   "bar"),
        "flow_rate_m3hr":        (2,  10,   "m³/hr"),
        "duty_pump_speed_rpm":   (3,   1,   "RPM"),
        "duty_pump_running":     (5,   1,   "0/1"),
        "duty":                  (5,   1,   "0/1"),
        "standby_pump_running":  (7,   1,   "0/1"),
        "inlet_valve_pos_pct":   (8,  10,   "%"),
        "outlet_valve_pos_pct":  (9,  10,   "%"),
        "leak_flag":             (13,  1,   "0/1"),
        "fault_code":            (14,  1,   "code"),
        "fault":                 (14,  1,   "code"),
    },
}

VERBS = [
    "read", "write", "inject", "start", "stop",
    "clear", "watch", "unwatch", "plc", "alarms",
    "status", "connect", "help", "history", "cls",
]

HELP_TEXT = {
    "read":    "read <ps|hx|bl|pl> [tag]  — read process or single tag",
    "write":   "write <proc> <tag> <value> — write register with verify",
    "inject":  "inject <proc> <tag> <value> — inject sensor value",
    "start":   "start <proc> <device>       — start equipment",
    "stop":    "stop <proc> <device>        — stop equipment",
    "clear":   "clear <proc|all> fault      — clear fault / operator reset",
    "watch":   "watch <proc> [tag] [--interval N] — live monitor",
    "unwatch": "unwatch                     — stop all watch timers",
    "plc":     "plc <proc> status|source|reload|upload <file>",
    "alarms":  "alarms [ack <id|all>] [history]",
    "status":  "status                      — server + process health",
    "connect": "connect <ip>:<port>         — reconnect to server",
    "help":    "help [command]              — show help",
    "history": "history                     — show command history",
    "cls":     "cls                         — clear output",
}


class CommandLine(QWidget):

    def __init__(self, rest, config: dict, get_plant: Callable):
        super().__init__()
        self._rest      = rest
        self._config    = config
        self._get_plant = get_plant
        self._history   = []
        self._hist_idx  = -1
        self._watch_timers: dict = {}

        self._load_history()
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(
            f"background-color: {theme.SURFACE}; "
            f"border-top: 2px solid {theme.BORDER};"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Drag handle label
        handle = QLabel("▲  SCRIPTING ENGINE  ▲")
        handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        handle.setFixedHeight(20)
        handle.setStyleSheet(
            f"color: {theme.TEXT_DIM}; background: {theme.BG}; "
            f"font-family: 'Courier New', monospace; font-size: 10px; "
            f"letter-spacing: 3px; border-bottom: 1px solid {theme.BORDER};"
        )
        root.addWidget(handle)

        # Output area
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            f"background-color: {theme.BG}; color: {theme.TEXT}; "
            f"border: none; font-family: 'Courier New', monospace; "
            f"font-size: 12px;"
        )
        self._output.setMinimumHeight(80)
        root.addWidget(self._output)

        # Input row
        input_row = QHBoxLayout()
        input_row.setContentsMargins(8, 4, 8, 4)
        input_row.setSpacing(8)

        prompt = QLabel("morbion ›")
        prompt.setStyleSheet(
            f"color: {theme.ACCENT}; font-family: 'Courier New', monospace; "
            f"font-size: 12px; background: transparent;"
        )
        input_row.addWidget(prompt)

        self._input = _HistoryLineEdit(self._history)
        self._input.setStyleSheet(
            f"background: transparent; color: {theme.TEXT}; "
            f"border: none; font-family: 'Courier New', monospace; "
            f"font-size: 12px;"
        )
        self._input.returnPressed.connect(self._on_enter)
        self._input.tab_pressed.connect(self._on_tab)
        input_row.addWidget(self._input)

        root.addLayout(input_row)

        # Welcome
        self._print_dim("MORBION SCADA v02 — Scripting Engine")
        self._print_dim("Type  help  for command reference.")

    # ── Output helpers ────────────────────────────────────────────────────────

    def _print(self, text: str, color: str = None):
        c = color or theme.TEXT
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(c))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _print_cyan(self, t):   self._print(t, theme.ACCENT)
    def _print_green(self, t):  self._print(t, theme.GREEN)
    def _print_red(self, t):    self._print(t, theme.RED)
    def _print_amber(self, t):  self._print(t, theme.AMBER)
    def _print_dim(self, t):    self._print(t, theme.TEXT_DIM)
    def _print_white(self, t):  self._print(t, theme.WHITE)

    # ── Entry point ───────────────────────────────────────────────────────────

    def _on_enter(self):
        raw = self._input.text().strip()
        self._input.clear()
        if not raw:
            return

        self._history.append(raw)
        self._hist_idx = -1
        self._save_history()

        self._print_cyan(f"› {raw}")
        threading.Thread(
            target=self._dispatch,
            args=(raw,),
            daemon=True,
        ).start()

    def _dispatch(self, raw: str):
        parts = raw.split()
        verb  = parts[0].lower() if parts else ""

        try:
            if verb == "cls":
                QTimer.singleShot(0, self._output.clear)

            elif verb == "help":
                self._cmd_help(parts[1:])

            elif verb == "history":
                self._cmd_history()

            elif verb == "status":
                self._cmd_status()

            elif verb == "read":
                self._cmd_read(parts[1:])

            elif verb == "write":
                self._cmd_write(parts[1:])

            elif verb == "inject":
                self._cmd_inject(parts[1:])

            elif verb == "start":
                self._cmd_start(parts[1:])

            elif verb == "stop":
                self._cmd_stop(parts[1:])

            elif verb == "clear":
                self._cmd_clear(parts[1:])

            elif verb == "watch":
                self._cmd_watch(parts[1:])

            elif verb == "unwatch":
                self._cmd_unwatch()

            elif verb == "alarms":
                self._cmd_alarms(parts[1:])

            elif verb == "plc":
                self._cmd_plc(parts[1:])

            elif verb == "connect":
                self._cmd_connect(parts[1:])

            else:
                self._print_red(f"Unknown command: {verb}  (type help)")

        except Exception as e:
            self._print_red(f"Error: {e}")
            log.exception("Command error")

    # ── Commands ──────────────────────────────────────────────────────────────

    def _cmd_help(self, args):
        if args:
            verb = args[0].lower()
            if verb in HELP_TEXT:
                self._print_white(HELP_TEXT[verb])
            else:
                self._print_red(f"No help for: {verb}")
        else:
            self._print_dim("─" * 56)
            for v, h in HELP_TEXT.items():
                self._print_white(f"  {h}")
            self._print_dim("─" * 56)
            self._print_dim("PROCESS ALIASES: ps hx bl pl")
            self._print_dim("VALUE ALIASES:   on off high low start stop")

    def _cmd_history(self):
        if not self._history:
            self._print_dim("No history.")
            return
        for i, cmd in enumerate(self._history[-20:], 1):
            self._print_dim(f"  {i:2d}  {cmd}")

    def _cmd_status(self):
        health = self._rest.get_health()
        if not health:
            self._print_red("Server unreachable")
            return
        self._print_green(f"Server:   {health.get('server', '')}")
        self._print_white(f"Online:   {health.get('processes_online', 0)}/4")
        self._print_white(f"Polls:    {health.get('poll_count', 0)}")
        self._print_white(f"Poll ms:  {health.get('poll_rate_ms', 0):.1f}")
        self._print_white(f"Time:     {health.get('server_time', '')}")

    def _cmd_read(self, args):
        if not args:
            self._print_red("Usage: read <ps|hx|bl|pl|all> [tag]")
            return

        proc_alias = args[0].lower()

        if proc_alias == "all":
            plant = self._get_plant()
            for key in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
                data = plant.get(key, {})
                online = data.get("online", False)
                color  = theme.GREEN if online else theme.RED
                self._print(f"  {key:<20} {'ONLINE' if online else 'OFFLINE'}", color)
            return

        proc = PROCESS_ALIASES.get(proc_alias)
        if not proc:
            self._print_red(f"Unknown process: {proc_alias}")
            return

        plant = self._get_plant()
        data  = plant.get(proc, {})

        if not data.get("online"):
            self._print_red(f"{proc} OFFLINE")
            return

        if len(args) > 1:
            tag = args[1].lower()
            val = data.get(tag) or data.get(args[1])
            if val is None:
                self._print_red(f"Tag not found: {tag}")
            else:
                self._print_white(f"  {tag} = {val}")
        else:
            self._print_green(f"── {proc} ──")
            for k, v in data.items():
                if k in ("online", "process", "label", "location",
                         "port", "fault_text", "burner_text"):
                    continue
                self._print_white(f"  {k:<35} {v}")

    def _cmd_write(self, args):
        if len(args) < 3:
            self._print_red("Usage: write <proc> <tag> <value>")
            return
        proc_alias = args[0].lower()
        tag        = args[1].lower()
        raw_val    = args[2].lower()

        proc = PROCESS_ALIASES.get(proc_alias)
        if not proc:
            self._print_red(f"Unknown process: {proc_alias}")
            return

        tag_info = TAG_MAP.get(proc, {}).get(tag)
        if not tag_info:
            self._print_red(f"Unknown tag '{tag}' for {proc}")
            return

        reg, scale, unit = tag_info

        # Resolve value alias
        if raw_val in VALUE_ALIASES:
            val_float = float(VALUE_ALIASES[raw_val])
        else:
            try:
                val_float = float(raw_val)
            except ValueError:
                self._print_red(f"Invalid value: {raw_val}")
                return

        # Special: inlet valve on pumping station reg 8
        if proc == "pumping_station" and reg == 8:
            raw_reg_val = 510 if val_float >= 1 else 0
        else:
            raw_reg_val = int(round(val_float * scale))

        raw_reg_val = max(0, min(65535, raw_reg_val))

        result = self._rest.write_register(proc, reg, raw_reg_val)
        if not result.get("ok"):
            self._print_red(f"Write failed: {result.get('error', '')}")
            return

        self._print_dim(f"  Written reg {reg} = {raw_reg_val} — verifying...")

        # Verify after write — wait 350ms for PLC scan
        time.sleep(0.35)
        readback = self._rest.read_register_value(proc, reg)

        if readback is None:
            self._print_amber(f"  UNVERIFIED — could not read back")
        elif readback == raw_reg_val:
            self._print_green(f"  CONFIRMED  {tag} = {val_float} {unit}")
        else:
            actual_val = readback / scale
            self._print_amber(
                f"  OVERRIDDEN — wrote {val_float} {unit}, "
                f"PLC holds {actual_val:.2f} {unit}"
            )
            self._print_amber(
                "  PLC may have overridden — check fault code"
            )

    def _cmd_inject(self, args):
        """inject <proc> <tag> <value> — same as write but for sensor injection."""
        if len(args) < 3:
            self._print_red("Usage: inject <proc> <tag> <value>")
            return
        # Injection uses same mechanism as write
        self._cmd_write(args)

    def _cmd_start(self, args):
        if len(args) < 2:
            self._print_red("Usage: start <proc> <device>")
            return
        proc_alias = args[0].lower()
        device     = args[1].lower()
        proc       = PROCESS_ALIASES.get(proc_alias)
        if not proc:
            self._print_red(f"Unknown process: {proc_alias}")
            return

        start_map = {
            "pumping_station": {"pump": (7, 1)},
            "boiler":          {"fw_pump": (7, 1450)},
            "pipeline":        {
                "duty":    (5, 1),
                "standby": (7, 1),
            },
            "heat_exchanger":  {
                "hot_pump":  (12, 1200),
                "cold_pump": (13, 1100),
            },
        }
        targets = start_map.get(proc, {})
        if device not in targets:
            self._print_red(f"Unknown device '{device}' for {proc}")
            return

        reg, val = targets[device]
        self._write_and_verify(proc, reg, val, device, "start")

    def _cmd_stop(self, args):
        if len(args) < 2:
            self._print_red("Usage: stop <proc> <device>")
            return
        proc_alias = args[0].lower()
        device     = args[1].lower()
        proc       = PROCESS_ALIASES.get(proc_alias)
        if not proc:
            self._print_red(f"Unknown process: {proc_alias}")
            return

        stop_map = {
            "pumping_station": {"pump": (7, 0)},
            "boiler":          {"fw_pump": (7, 0), "burner": (6, 0)},
            "pipeline":        {"duty": (5, 0), "standby": (7, 0)},
            "heat_exchanger":  {"hot_pump": (12, 0), "cold_pump": (13, 0)},
        }
        targets = stop_map.get(proc, {})
        if device not in targets:
            self._print_red(f"Unknown device '{device}' for {proc}")
            return

        reg, val = targets[device]
        self._write_and_verify(proc, reg, val, device, "stop")

    def _cmd_clear(self, args):
        if not args:
            self._print_red("Usage: clear <proc|all> fault")
            return

        target = args[0].lower()
        procs  = []

        if target == "all":
            procs = list(PROCESS_ALIASES.values())
            procs = list(dict.fromkeys(procs))  # deduplicate
        else:
            proc = PROCESS_ALIASES.get(target)
            if not proc:
                self._print_red(f"Unknown process: {target}")
                return
            procs = [proc]

        for proc in procs:
            result = self._rest.write_register(proc, 14, 0)
            if result.get("ok"):
                self._print_green(f"  {proc:<25} fault clear sent")
            else:
                self._print_red(f"  {proc:<25} clear failed: {result.get('error')}")

    def _cmd_watch(self, args):
        if not args:
            self._print_red("Usage: watch <proc|all> [tag] [--interval N]")
            return

        interval = 1.0
        if "--interval" in args:
            idx = args.index("--interval")
            try:
                interval = float(args[idx + 1])
                args = [a for i, a in enumerate(args)
                        if i != idx and i != idx + 1]
            except (IndexError, ValueError):
                pass

        proc_alias = args[0].lower()
        tag        = args[1].lower() if len(args) > 1 else None

        if proc_alias == "all":
            procs = list(dict.fromkeys(PROCESS_ALIASES.values()))
            for proc in procs:
                self._start_watch(proc, None, interval)
        else:
            proc = PROCESS_ALIASES.get(proc_alias)
            if not proc:
                self._print_red(f"Unknown process: {proc_alias}")
                return
            self._start_watch(proc, tag, interval)

    def _start_watch(self, proc: str, tag: Optional[str], interval: float):
        key = f"{proc}:{tag or '*'}"
        if key in self._watch_timers:
            self._watch_timers[key].stop()

        self._print_dim(f"  Watching {proc} {tag or 'all'} every {interval}s — unwatch to stop")

        timer = QTimer(self)
        timer.timeout.connect(lambda: self._watch_tick(proc, tag))
        timer.start(int(interval * 1000))
        self._watch_timers[key] = timer

    def _watch_tick(self, proc: str, tag: Optional[str]):
        plant = self._get_plant()
        data  = plant.get(proc, {})
        if not data.get("online"):
            self._print_red(f"  [{proc}] OFFLINE")
            return
        if tag:
            val = data.get(tag)
            if val is not None:
                self._print_white(f"  [{proc}] {tag} = {val}")
        else:
            online_str = "ONLINE" if data.get("online") else "OFFLINE"
            self._print_dim(f"  [{proc}] {online_str}")

    def _cmd_unwatch(self):
        for timer in self._watch_timers.values():
            timer.stop()
        self._watch_timers.clear()
        self._print_dim("  All watch timers stopped")

    def _cmd_alarms(self, args):
        if not args:
            alarms = self._rest.get_alarms()
            if not alarms:
                self._print_green("  No active alarms")
                return
            for a in alarms:
                sev   = a.get("sev", "")
                color = (theme.RED if sev == "CRIT" else
                         theme.AMBER if sev == "HIGH" else
                         theme.TEXT)
                acked = " [ACK]" if a.get("acked") else ""
                self._print(
                    f"  [{sev}] {a.get('id')} {a.get('desc')}{acked}",
                    color
                )
            return

        sub = args[0].lower()

        if sub == "ack":
            alarm_id = args[1] if len(args) > 1 else "all"
            result   = self._rest.ack_alarm(
                alarm_id,
                self._config.get("operator", "OPERATOR")
            )
            if result.get("ok"):
                self._print_green(f"  Acknowledged: {result.get('acked')}")
            else:
                self._print_red(f"  Ack failed: {result.get('error')}")

        elif sub == "history":
            history = self._rest.get_alarm_history()
            if not history:
                self._print_dim("  No alarm history")
                return
            for a in history[-20:]:
                self._print_dim(
                    f"  {a.get('ts','')}  [{a.get('sev','')}]  "
                    f"{a.get('id','')}  {a.get('desc','')[:50]}"
                )

    def _cmd_plc(self, args):
        if len(args) < 2:
            self._print_red("Usage: plc <proc> status|source|reload|upload <file>")
            return

        proc_alias = args[0].lower()
        sub        = args[1].lower()
        proc       = PROCESS_ALIASES.get(proc_alias)
        if not proc:
            self._print_red(f"Unknown process: {proc_alias}")
            return

        if sub == "status":
            result = self._rest.plc_get_status(proc)
            if not result:
                self._print_red("PLC status unavailable")
                return
            status = result.get("status", result)
            self._print_green(f"  Loaded:     {status.get('loaded')}")
            self._print_white(f"  Scan count: {status.get('scan_count')}")
            self._print_white(f"  Last error: {status.get('last_error') or '—'}")
            self._print_dim(f"  File:       {status.get('program_file', '')}")

        elif sub == "source":
            result = self._rest.plc_get_program(proc)
            if not result:
                self._print_red("Could not fetch PLC source")
                return
            source = result.get("source", "")
            for line in source.splitlines():
                self._print_dim(line)

        elif sub == "reload":
            result = self._rest.plc_reload(proc)
            if result.get("ok"):
                self._print_green(f"  {proc} PLC program reloaded from disk")
            else:
                self._print_red(f"  Reload failed: {result.get('error')}")

        elif sub == "upload":
            if len(args) < 3:
                self._print_red("Usage: plc <proc> upload <filepath>")
                return
            path = args[2]
            if not os.path.exists(path):
                self._print_red(f"File not found: {path}")
                return
            try:
                with open(path) as f:
                    source = f.read()
            except Exception as e:
                self._print_red(f"Read error: {e}")
                return
            result = self._rest.plc_upload_program(proc, source)
            if result.get("ok"):
                self._print_green(f"  {proc} PLC program uploaded and applied")
            else:
                self._print_red(
                    f"  Upload failed: {result.get('error', result)}"
                )
        else:
            self._print_red(f"Unknown plc sub-command: {sub}")

    def _cmd_connect(self, args):
        if not args:
            self._print_red("Usage: connect <ip>:<port>")
            return
        raw = args[0]
        if ":" in raw:
            parts = raw.rsplit(":", 1)
            host  = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                self._print_red("Invalid port")
                return
        else:
            host = raw
            port = self._config.get("server_port", 5000)

        self._config["server_host"] = host
        self._config["server_port"] = port
        self._rest._base = f"http://{host}:{port}"
        self._print_green(f"  REST base updated: http://{host}:{port}")
        self._print_dim("  Restart WS from main window to reconnect WebSocket")

    # ── Internal write + verify ───────────────────────────────────────────────

    def _write_and_verify(self, proc: str, reg: int, val: int,
                           label: str, action: str):
        result = self._rest.write_register(proc, reg, val)
        if not result.get("ok"):
            self._print_red(f"  {action} {label} failed: {result.get('error')}")
            return

        self._print_dim(f"  {action} {label} sent — verifying...")
        time.sleep(0.35)

        readback = self._rest.read_register_value(proc, reg)
        if readback is None:
            self._print_amber(f"  UNVERIFIED — could not read back {label}")
        elif readback == val:
            self._print_green(f"  CONFIRMED  {label} {action}")
        else:
            self._print_amber(
                f"  OVERRIDDEN — {label} not {action}ed "
                f"(PLC holds reg={readback})"
            )
            self._print_amber("  Check fault code — interlock may be active")

    # ── Tab completion ────────────────────────────────────────────────────────

    def _on_tab(self):
        text  = self._input.text()
        parts = text.split()
        if not parts:
            candidates = VERBS
        elif len(parts) == 1 and not text.endswith(" "):
            word       = parts[0].lower()
            candidates = [v for v in VERBS if v.startswith(word)]
        elif len(parts) == 1:
            candidates = list(PROCESS_ALIASES.keys())[:8]
        elif len(parts) == 2 and not text.endswith(" "):
            word       = parts[1].lower()
            candidates = [k for k in PROCESS_ALIASES if k.startswith(word)]
        else:
            candidates = []

        if len(candidates) == 1:
            new_parts    = parts[:-1] if not text.endswith(" ") else parts
            new_text     = " ".join(new_parts + [candidates[0]]) + " "
            self._input.setText(new_text)
        elif candidates:
            self._print_dim("  " + "  ".join(candidates))

    # ── History persistence ───────────────────────────────────────────────────

    def _load_history(self):
        try:
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH) as f:
                    self._history = json.load(f)
        except Exception:
            self._history = []

    def _save_history(self):
        try:
            with open(HISTORY_PATH, "w") as f:
                json.dump(self._history[-200:], f)
        except Exception:
            pass


class _HistoryLineEdit(QLineEdit):
    """QLineEdit with arrow-key history navigation and Tab signal."""

    tab_pressed = pyqtSignal()

    def __init__(self, history: list):
        super().__init__()
        self._history = history
        self._idx     = -1

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Up:
            if self._history:
                self._idx = min(self._idx + 1, len(self._history) - 1)
                self.setText(self._history[-(self._idx + 1)])
            return

        if key == Qt.Key.Key_Down:
            if self._idx > 0:
                self._idx -= 1
                self.setText(self._history[-(self._idx + 1)])
            elif self._idx == 0:
                self._idx = -1
                self.clear()
            return

        if key == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
            return

        self._idx = -1
        super().keyPressEvent(event)
