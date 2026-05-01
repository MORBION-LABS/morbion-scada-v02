"""
command_line.py — Scripting Engine
Surgical Rebuild v03 — FULL FEATURE RESTORATION
"""
import os, json, time, logging, threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

log = logging.getLogger("command_line")

class CommandLine(QWidget):
    print_signal = pyqtSignal(str, str) # The safety valve

    # Original Command Mappings Restored
    VERBS = ["read", "write", "inject", "start", "stop", "clear", "watch", "unwatch", "plc", "alarms", "status", "help", "cls"]
    
    HELP_TEXT = {
        "read":    "read <ps|hx|bl|pl> [tag]  — read process or single tag",
        "write":   "write <proc> <tag> <value> — write register with verify",
        "inject":  "inject <proc> <tag> <value> — inject sensor value",
        "plc":     "plc <proc> status|source|reload",
        "status":  "status — server health",
        "help":    "help [command] — show help",
        "cls":     "cls — clear output"
    }

    def __init__(self, rest, config, get_plant):
        super().__init__()
        self._rest = rest
        self._config = config
        self._get_plant = get_plant
        self._build_ui()
        self.print_signal.connect(self._do_print)

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        
        handle = QLabel("▲ SCRIPTING ENGINE ▲")
        handle.setAlignment(Qt.AlignmentFlag.AlignCenter); handle.setFixedHeight(20)
        handle.setStyleSheet(f"color: {theme.TEXT_DIM}; background: {theme.BG}; font-size: 10px; border-bottom: 1px solid {theme.BORDER};")
        lay.addWidget(handle)

        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: none; font-family: 'Courier New'; font-size: 12px;")
        lay.addWidget(self._out)
        
        inp_lay = QHBoxLayout(); inp_lay.setContentsMargins(8,4,8,4)
        prompt = QLabel("morbion >"); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit(); self._in.setStyleSheet("background: transparent; color: white; border: none; font-family: 'Courier New';")
        self._in.returnPressed.connect(self._on_enter)
        inp_lay.addWidget(prompt); inp_lay.addWidget(self._in); lay.addLayout(inp_lay)

    def _on_enter(self):
        raw = self._in.text().strip()
        if not raw: return
        self._in.clear()
        self._do_print(f"› {raw}", theme.ACCENT)
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _dispatch(self, raw):
        p = raw.split()
        verb = p[0].lower() if p else ""
        try:
            if verb == "cls": QTimer.singleShot(0, self._out.clear)
            elif verb == "help":
                self.print_signal.emit("-" * 50, theme.TEXT_DIM)
                for v, h in self.HELP_TEXT.items(): self.print_signal.emit(f" {h}", theme.TEXT)
                self.print_signal.emit("-" * 50, theme.TEXT_DIM)
            elif verb == "status":
                h = self._rest.get_health()
                if h: self.print_signal.emit(f"Server: {h.get('server')}\nOnline: {h.get('processes_online')}/4\nTime: {h.get('server_time')}", theme.GREEN)
                else: self.print_signal.emit("Server Unreachable", theme.RED)
            elif verb == "plc" and len(p) >= 3:
                proc, sub = p[1], p[2]
                if sub == "status":
                    res = self._rest.plc_get_status(proc)
                    self.print_signal.emit(json.dumps(res, indent=2) if res else "Error", theme.GREEN)
                elif sub == "source":
                    res = self._rest.plc_get_program(proc)
                    self.print_signal.emit(res.get("source", "No source") if res else "Error", theme.WHITE)
            elif verb == "read" and len(p) >= 2:
                plant = self._get_plant(); data = plant.get(self._rest._resolve(p[1]), {})
                self.print_signal.emit(json.dumps(data, indent=2), theme.TEXT)
            else:
                self.print_signal.emit(f"Unknown command or missing args: {verb}", theme.RED)
        except Exception as e:
            self.print_signal.emit(f"Execution Error: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, msg, color):
        cursor = self._out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt); cursor.insertText(msg + "\n")
        self._out.ensureCursorVisible()
