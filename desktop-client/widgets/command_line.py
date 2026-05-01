"""
command_line.py — Scripting Engine
Surgical Rebuild v02 — Crash-Proof Threading
"""
import threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

class CommandLine(QWidget):
    # This is the secret to not crashing:
    print_signal = pyqtSignal(str, str) 

    def __init__(self, rest, config, get_plant):
        super().__init__()
        self._rest = rest
        self._config = config
        self._get_plant = get_plant
        self._build_ui()
        self.print_signal.connect(self._do_print) # Connect the signal

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: none; font-family: 'Courier New';")
        lay.addWidget(self._out)
        
        inp_lay = QHBoxLayout(); inp_lay.setContentsMargins(8,4,8,4)
        prompt = QLabel("morbion >"); prompt.setStyleSheet(f"color: {theme.ACCENT};")
        self._in = QLineEdit(); self._in.setStyleSheet("background: transparent; color: white; border: none;")
        self._in.returnPressed.connect(self._on_enter)
        inp_lay.addWidget(prompt); inp_lay.addWidget(self._in); lay.addLayout(inp_lay)

    def _on_enter(self):
        cmd = self._in.text().strip()
        if not cmd: return
        self._in.clear()
        self._do_print(f"> {cmd}", theme.ACCENT)
        threading.Thread(target=self._execute, args=(cmd,), daemon=True).start()

    def _execute(self, raw):
        p = raw.split()
        verb = p[0].lower() if p else ""
        try:
            if verb == "plc" and len(p) >= 3:
                proc, sub = p[1], p[2]
                if sub == "status":
                    res = self._rest.plc_get_status(proc)
                    self.print_signal.emit(json.dumps(res, indent=2) if res else "Error", theme.GREEN)
                elif sub == "source":
                    res = self._rest.plc_get_program(proc)
                    # We emit the signal safely to the UI thread
                    self.print_signal.emit(res.get("source", "Empty") if res else "Error", theme.TEXT)
            elif verb == "status":
                h = self._rest.get_health()
                self.print_signal.emit(f"Online: {h.get('processes_online')}/4", theme.GREEN)
            else:
                self.print_signal.emit(f"Unknown command: {verb}", theme.RED)
        except Exception as e:
            self.print_signal.emit(f"Shell Error: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, msg, color):
        cursor = self._out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        self._out.ensureCursorVisible()
