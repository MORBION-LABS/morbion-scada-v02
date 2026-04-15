"""
command_line.py — Operator Command Line Terminal
MORBION SCADA v02

Terminal-style widget at bottom of main window.
Full command vocabulary. Tab completion. History navigation.
Emits command_entered signal with parsed command dict.
Main window executes the command and calls print_result().
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui  import QFont, QKeyEvent, QTextCursor, QColor

from theme import C_ACCENT, C_TEXT2, C_RED, C_GREEN, C_YELLOW, C_MUTED

log = logging.getLogger(__name__)

# ── Command Parser ────────────────────────────────────────────────────────────

class CommandParser:
    """
    Parses command strings into action dicts.
    Returns: {type, process, register, value, message, ...}
    type: control | alarm_ack | plc | query | system | error
    """

    PROCESS_ALIASES = {
        "pump":  "pumping_station",
        "ps":    "pumping_station",
        "hx":    "heat_exchanger",
        "heat":  "heat_exchanger",
        "boiler":"boiler",
        "bl":    "boiler",
        "pipe":  "pipeline",
        "pl":    "pipeline",
        "pumping_station": "pumping_station",
        "heat_exchanger":  "heat_exchanger",
        "pipeline":        "pipeline",
    }

    FAULT_PRESETS = {
        ("pumping_station", "high_level"):   (0,  920),
        ("pumping_station", "low_water"):    (0,  80),
        ("pumping_station", "dry_run"):      (14, 4),
        ("boiler",          "low_water"):    (2,  150),
        ("boiler",          "overpressure"): (0,  1100),
        ("boiler",          "flame_failure"):(14, 3),
        ("heat_exchanger",  "overtemp"):     (3,  1000),
        ("heat_exchanger",  "pump_fault"):   (16, 1),
        ("pipeline",        "duty_fault"):   (14, 1),
        ("pipeline",        "overpressure"): (1,  5600),
        ("pipeline",        "flow_drop"):    (2,  500),
    }

    FAULT_CLEAR_REG = {
        "pumping_station": 14,
        "heat_exchanger":  16,
        "boiler":          14,
        "pipeline":        14,
    }

    def parse(self, command: str) -> dict:
        parts = command.strip().split()
        if not parts:
            return {"type": "error", "message": "Empty command"}

        cmd = parts[0].lower()

        try:
            if cmd == "pump":
                return self._parse_pump(parts)
            elif cmd == "valve":
                return self._parse_valve(parts)
            elif cmd == "burner":
                return self._parse_burner(parts)
            elif cmd == "level":
                return self._parse_sensor_inject(
                    parts, "pumping_station", 0, 10.0, "%")
            elif cmd == "pressure":
                return self._parse_sensor_inject(
                    parts, "pumping_station", 4, 100.0, "bar")
            elif cmd == "flow":
                return self._parse_sensor_inject(
                    parts, "pumping_station", 3, 10.0, "m3/hr")
            elif cmd == "fault":
                return self._parse_fault(parts)
            elif cmd == "alarm":
                return self._parse_alarm(parts)
            elif cmd == "plc":
                return self._parse_plc(parts)
            elif cmd == "status":
                return self._parse_status(parts)
            elif cmd in ("help", "?"):
                return self._parse_help(parts)
            elif cmd == "clear":
                return {"type": "system", "action": "clear"}
            elif cmd == "connect":
                if len(parts) < 2:
                    return {"type": "error",
                            "message": "Usage: connect <ip>"}
                return {"type": "system",
                        "action": "connect", "host": parts[1]}
            else:
                return {"type": "error",
                        "message": (f"Unknown command: {cmd}. "
                                    f"Type 'help' for reference.")}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    def _parse_pump(self, parts):
        if len(parts) < 2:
            return {"type": "error",
                    "message": "Usage: pump start|stop|speed <rpm>"}
        action = parts[1].lower()
        if action == "start":
            return {"type": "control",
                    "process": "pumping_station",
                    "register": 7, "value": 1,
                    "message": "Pump start command sent"}
        elif action == "stop":
            return {"type": "control",
                    "process": "pumping_station",
                    "register": 7, "value": 0,
                    "message": "Pump stop command sent"}
        elif action == "speed":
            if len(parts) < 3:
                return {"type": "error",
                        "message": "Usage: pump speed <rpm>"}
            rpm = int(float(parts[2]))
            return {"type": "control",
                    "process": "pumping_station",
                    "register": 2, "value": rpm,
                    "message": f"Pump speed → {rpm} RPM"}
        return {"type": "error",
                "message": f"Unknown pump action: {action}"}

    def _parse_valve(self, parts):
        if len(parts) < 3:
            return {"type": "error",
                    "message": "Usage: valve inlet|outlet open|close|set <pct>"}
        which  = parts[1].lower()
        action = parts[2].lower()
        reg_map = {"inlet": 8, "outlet": 9}
        if which not in reg_map:
            return {"type": "error",
                    "message": f"Unknown valve: {which}"}
        reg = reg_map[which]
        if action == "open":
            val = 1000
        elif action == "close":
            val = 0
        elif action == "set":
            if len(parts) < 4:
                return {"type": "error",
                        "message": "Usage: valve outlet set <pct>"}
            val = int(float(parts[3]) * 10)
        else:
            return {"type": "error",
                    "message": f"Unknown valve action: {action}"}
        return {"type": "control",
                "process": "pumping_station",
                "register": reg, "value": val,
                "message": f"{which} valve command sent"}

    def _parse_burner(self, parts):
        if len(parts) < 2:
            return {"type": "error",
                    "message": "Usage: burner off|low|high"}
        state_map = {"off": 0, "low": 1, "high": 2}
        action = parts[1].lower()
        if action not in state_map:
            return {"type": "error",
                    "message": f"Unknown burner state: {action}"}
        return {"type": "control",
                "process": "boiler",
                "register": 6,
                "value": state_map[action],
                "message": f"Burner → {action.upper()}"}

    def _parse_sensor_inject(self, parts, process,
                              reg, factor, unit):
        if len(parts) < 3 or parts[1].lower() != "set":
            return {"type": "error",
                    "message": f"Usage: {parts[0]} set <value>"}
        val = int(float(parts[2]) * factor)
        return {"type": "control",
                "process": process,
                "register": reg, "value": val,
                "message": f"{parts[0]} → {parts[2]} {unit}"}

    def _parse_fault(self, parts):
        if len(parts) < 2:
            return {"type": "error",
                    "message": ("Usage: fault clear <process> | "
                                "fault inject <process> <type>")}
        action = parts[1].lower()

        if action == "clear":
            if len(parts) < 3:
                return {"type": "error",
                        "message": "Usage: fault clear <process>"}
            proc = self.PROCESS_ALIASES.get(
                parts[2].lower(), parts[2].lower())
            if proc not in self.FAULT_CLEAR_REG:
                return {"type": "error",
                        "message": f"Unknown process: {proc}"}
            reg = self.FAULT_CLEAR_REG[proc]
            return {"type": "control",
                    "process": proc,
                    "register": reg, "value": 0,
                    "message": f"Fault cleared on {proc}"}

        elif action == "inject":
            if len(parts) < 4:
                return {"type": "error",
                        "message": ("Usage: fault inject "
                                    "<process> <type>")}
            proc       = self.PROCESS_ALIASES.get(
                parts[2].lower(), parts[2].lower())
            fault_type = parts[3].lower()
            key        = (proc, fault_type)
            if key not in self.FAULT_PRESETS:
                available = [f[1] for f in self.FAULT_PRESETS
                             if f[0] == proc]
                return {"type": "error",
                        "message": (f"Unknown fault '{fault_type}' "
                                    f"for {proc}. "
                                    f"Available: "
                                    f"{', '.join(available)}")}
            reg, val = self.FAULT_PRESETS[key]
            return {"type": "control",
                    "process": proc,
                    "register": reg, "value": val,
                    "message": (f"Fault injected: "
                                f"{proc} {fault_type}")}

        return {"type": "error",
                "message": f"Unknown fault action: {action}"}

    def _parse_alarm(self, parts):
        if len(parts) < 2:
            return {"type": "error",
                    "message": ("Usage: alarm ack <id>|all | "
                                "alarm list | alarm history")}
        action = parts[1].lower()
        if action == "ack":
            target = parts[2] if len(parts) > 2 else "all"
            return {"type": "alarm_ack", "target": target,
                    "message": f"Acknowledging: {target}"}
        elif action == "list":
            return {"type": "query", "field": "alarms"}
        elif action == "history":
            return {"type": "query", "field": "alarm_history"}
        return {"type": "error",
                "message": f"Unknown alarm action: {action}"}

    def _parse_plc(self, parts):
        if len(parts) < 3:
            return {"type": "error",
                    "message": ("Usage: plc "
                                "status|reload|vars <process>")}
        action = parts[1].lower()
        proc   = self.PROCESS_ALIASES.get(
            parts[2].lower(), parts[2].lower())
        return {"type": "plc", "action": action,
                "process": proc,
                "message": f"PLC {action} {proc}"}

    def _parse_status(self, parts):
        proc = parts[1].lower() if len(parts) > 1 else "all"
        return {"type": "query",
                "field": "status", "process": proc}

    def _parse_help(self, parts):
        topic = parts[1].lower() if len(parts) > 1 else "general"
        return {"type": "system",
                "action": "help", "topic": topic}


# ── Help text ─────────────────────────────────────────────────────────────────

HELP_TEXT = {
    "general": """\
MORBION SCADA v02 — Command Reference

PUMP:    pump start | pump stop | pump speed <rpm>
VALVE:   valve inlet open | valve outlet set <pct>
BURNER:  burner off | burner low | burner high
INJECT:  level set <pct> | pressure set <bar> | flow set <m3hr>
FAULT:   fault inject <process> <type> | fault clear <process>
ALARM:   alarm ack <id> | alarm ack all | alarm list
PLC:     plc status <process> | plc reload <process>
SYSTEM:  status | status <process> | clear

Type 'help fault' for fault injection reference.
Type 'help plc' for PLC command reference.""",

    "fault": """\
Fault Injection Reference:

  fault inject pumping_station high_level
  fault inject pumping_station low_water
  fault inject pumping_station dry_run
  fault inject boiler low_water
  fault inject boiler overpressure
  fault inject boiler flame_failure
  fault inject heat_exchanger overtemp
  fault inject heat_exchanger pump_fault
  fault inject pipeline duty_fault
  fault inject pipeline overpressure
  fault inject pipeline flow_drop
  fault clear <process>  — write 0 to fault register""",

    "plc": """\
PLC Command Reference:

  plc status <process>   — show runtime status
  plc reload <process>   — hot reload program from file
  plc vars <process>     — show variable map

Process aliases: pump/ps, hx/heat, boiler/bl, pipe/pl""",
}


# ── CommandLine Widget ────────────────────────────────────────────────────────

class CommandLine(QWidget):
    """
    Operator command line terminal.
    Emits command_entered(dict) when operator submits.
    Main window executes and calls print_result().
    """

    command_entered = pyqtSignal(dict)
    HISTORY_MAX     = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parser   = CommandParser()
        self._history  = []
        self._hist_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        self.setMaximumHeight(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Output area
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumHeight(112)
        self._output.setFont(QFont("Courier New", 9))
        self._output.setStyleSheet(
            "background-color: #010810;"
            "color: #00d4ff;"
            "border: 1px solid #0d2030;"
            "border-bottom: none;"
            "padding: 4px;")
        layout.addWidget(self._output)

        # Input row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        prompt = QLabel("MORBION > ")
        prompt.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        prompt.setStyleSheet(
            f"color: {C_ACCENT};"
            "background-color: #010810;"
            "border: 1px solid #0d2030;"
            "padding: 4px 8px;")
        row.addWidget(prompt)

        self._input = QLineEdit()
        self._input.setFont(QFont("Courier New", 10))
        self._input.setStyleSheet(
            "background-color: #010810;"
            f"color: {C_ACCENT};"
            "border: 1px solid #0d2030;"
            "border-left: none;"
            "padding: 4px 8px;"
            "selection-background-color: #0d3040;")
        self._input.setPlaceholderText(
            "Type command... (help, ↑↓ history, Tab complete)")
        self._input.returnPressed.connect(self._on_enter)
        self._input.installEventFilter(self)
        row.addWidget(self._input, 1)
        layout.addLayout(row)

        self._print("MORBION SCADA v02 — Command Interface Ready",
                    C_ACCENT)
        self._print("Type 'help' for command reference.", C_TEXT2)

    def eventFilter(self, obj, event):
        if obj == self._input and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Up:
                self._hist_prev()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._hist_next()
                return True
            elif event.key() == Qt.Key.Key_Tab:
                self._tab_complete()
                return True
        return super().eventFilter(obj, event)

    def _on_enter(self):
        text = self._input.text().strip()
        if not text:
            return

        self._print(f"> {text}", C_TEXT2)
        self._history.insert(0, text)
        if len(self._history) > self.HISTORY_MAX:
            self._history.pop()
        self._hist_idx = -1
        self._input.clear()

        result = self._parser.parse(text)

        if result["type"] == "error":
            self._print(f"  ERROR: {result['message']}", C_RED)
            return

        if result["type"] == "system":
            if result.get("action") == "clear":
                self._output.clear()
                return
            if result.get("action") == "help":
                topic     = result.get("topic", "general")
                help_text = HELP_TEXT.get(
                    topic, HELP_TEXT["general"])
                self._print(help_text, C_TEXT2)
                return

        self.command_entered.emit(result)

        if "message" in result:
            self._print(f"  {result['message']}", C_GREEN)

    def print_result(self, result: dict):
        """Called by main window with execution result."""
        if result.get("ok") or result.get("confirmed"):
            msg = result.get("message", "OK")
            self._print(f"  ✓ {msg}", C_GREEN)
        elif "error" in result:
            self._print(f"  ✗ {result['error']}", C_RED)
        else:
            self._print(f"  ⚠ {result}", C_YELLOW)

    def print_query_result(self, data: dict):
        """Display query results."""
        for k, v in data.items():
            self._print(f"  {k}: {v}", C_ACCENT)

    def _print(self, text: str, color: str = None):
        color  = color or C_TEXT2
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._output.setTextCursor(cursor)
        self._output.setTextColor(QColor(color))
        self._output.insertPlainText(text + "\n")
        self._output.ensureCursorVisible()

    def _hist_prev(self):
        if not self._history:
            return
        self._hist_idx = min(
            self._hist_idx + 1, len(self._history) - 1)
        self._input.setText(self._history[self._hist_idx])

    def _hist_next(self):
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self._input.clear()
            return
        self._hist_idx -= 1
        self._input.setText(self._history[self._hist_idx])

    def _tab_complete(self):
        text = self._input.text()
        if " " in text:
            return
        completions = [
            "pump", "valve", "burner", "level", "pressure",
            "flow", "fault", "alarm", "plc", "status",
            "help", "clear",
        ]
        matches = [c for c in completions
                   if c.startswith(text.lower())]
        if len(matches) == 1:
            self._input.setText(matches[0] + " ")
        elif len(matches) > 1:
            self._print("  " + "  ".join(matches), C_TEXT2)
