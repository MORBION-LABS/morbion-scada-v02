"""
command_line.py — Modern Grade Scripting Engine
Surgical Overhaul v06 — FULL FILE
"""
import json, threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

class CommandLine(QWidget):
    print_signal = pyqtSignal(str, str)

    def __init__(self, rest, config, get_plant):
        super().__init__()
        self._rest, self._config, self._get_plant = rest, config, get_plant
        self._build_ui(); self.print_signal.connect(self._do_print)
        self._do_print("MORBION SCADA v02 — SCRIPTING ENGINE ACTIVE", theme.ACCENT)
        self._do_print("Type 'help' for full-word industrial command set.", theme.TEXT_DIM)

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0,0,0,0); main_lay.setSpacing(0)
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Inspector
        left_panel = QWidget(); left_lay = QVBoxLayout(left_panel)
        left_lay.addWidget(QLabel("LIVE VARIABLE INSPECTOR"))
        self._inspector = QTreeWidget()
        self._inspector.setHeaderLabels(["TAG / PARAMETER", "VALUE"])
        self._inspector.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT_DIM}; border: 1px solid {theme.BORDER};")
        self._inspector.setColumnWidth(0, 200)
        left_lay.addWidget(self._inspector); self._h_splitter.addWidget(left_panel)
        
        # Right: Terminal
        right_panel = QWidget(); right_lay = QVBoxLayout(right_panel); right_lay.setContentsMargins(5,5,5,5)
        inp_cont = QWidget(); inp_lay = QHBoxLayout(inp_cont); inp_lay.setContentsMargins(0,0,0,5)
        prompt = QLabel("morbion › "); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit(); self._in.setPlaceholderText("Enter full command (e.g. read pumping_station)...")
        self._in.setStyleSheet(f"background: {theme.BG}; color: white; border: 1px solid {theme.BORDER}; padding: 6px;")
        self._in.returnPressed.connect(self._on_enter)
        inp_lay.addWidget(prompt); inp_lay.addWidget(self._in); right_lay.addWidget(inp_cont)
        self._out = QTextEdit(); self._out.setReadOnly(True); self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-family: 'Courier New';")
        right_lay.addWidget(self._out); self._h_splitter.addWidget(right_panel)
        
        self._h_splitter.setSizes([350, 850]); main_lay.addWidget(self._h_splitter)

    def update_inspector(self, data):
        self._inspector.setUpdatesEnabled(False); self._inspector.clear()
        for p in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
            p_data = data.get(p, {})
            root = QTreeWidgetItem(self._inspector, [p.upper().replace("_", " "), "ONLINE" if p_data.get("online") else "OFFLINE"])
            for k, v in p_data.items():
                if isinstance(v, (int, float, bool)): QTreeWidgetItem(root, [k, str(v)])
        self._inspector.setUpdatesEnabled(True)

    def _on_enter(self):
        raw = self._in.text().strip()
        if not raw: return
        self._in.clear(); self._do_print(f"COMMAND: {raw}", theme.ACCENT)
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _dispatch(self, raw):
        parts = raw.split(); verb = parts[0].lower() if parts else ""
        try:
            if verb == "help":
                self.print_signal.emit("─"*50, theme.BORDER)
                for h in ["read <pumping_station | boiler | ...>", "write <process> <reg> <val>", "plc <process> status", "cls"]:
                    self.print_signal.emit(f" {h}", theme.TEXT)
                self.print_signal.emit("─"*50, theme.BORDER)
            elif verb == "read" and len(parts) >= 2:
                res = self._get_plant().get(parts[1].lower())
                self.print_signal.emit(json.dumps(res, indent=2) if res else "Process Not Found", theme.TEXT)
            elif verb == "cls": QTimer.singleShot(0, self._out.clear)
            else: self.print_signal.emit(f"Verb '{verb}' unknown. Use full words.", theme.RED)
        except Exception as e: self.print_signal.emit(f"Error: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, m, c):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(c)); cur.setCharFormat(fmt); cur.insertText(m + "\n"); self._out.ensureCursorVisible()
