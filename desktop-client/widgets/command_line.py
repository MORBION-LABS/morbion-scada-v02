"""
command_line.py — Modern Grade Scripting Engine
Surgical Overhaul v06 — Left/Right Split & Input at Top
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
        self._build_ui()
        self.print_signal.connect(self._do_print)

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0,0,0,0); main_lay.setSpacing(0)
        
        # Side-by-Side Splitter
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ── LEFT PANEL: Live Variable Inspector ──
        left_panel = QWidget(); left_lay = QVBoxLayout(left_panel)
        left_lay.addWidget(QLabel("LIVE VARIABLE INSPECTOR"))
        self._inspector = QTreeWidget()
        self._inspector.setHeaderLabels(["PROCESS / TAG", "VALUE"])
        self._inspector.setStyleSheet(f"background: {theme.BG}; border: 1px solid {theme.BORDER}; font-size: 11px;")
        self._inspector.setColumnWidth(0, 180)
        left_lay.addWidget(self._inspector)
        self._h_splitter.addWidget(left_panel)
        
        # ── RIGHT PANEL: Modern Terminal ──
        right_panel = QWidget(); right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(5,5,5,5)
        
        # Input Box at the TOP
        inp_container = QWidget(); inp_lay = QHBoxLayout(inp_container)
        inp_lay.setContentsMargins(0,0,0,5)
        prompt = QLabel("morbion command › "); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit()
        self._in.setPlaceholderText("Enter full command (e.g., read pumping_station)...")
        self._in.setStyleSheet(f"background: {theme.BG}; color: white; border: 1px solid {theme.BORDER}; padding: 5px; font-family: 'Courier New';")
        self._in.returnPressed.connect(self._on_enter)
        inp_lay.addWidget(prompt); inp_lay.addWidget(self._in)
        right_lay.addWidget(inp_container)
        
        # Console Output below
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-family: 'Courier New'; font-size: 12px;")
        right_lay.addWidget(self._out)
        
        self._h_splitter.addWidget(right_panel)
        self._h_splitter.setSizes([400, 800])
        main_lay.addWidget(self._h_splitter)

    def update_inspector(self, data):
        """Live updates the left-side tree with full process data."""
        self._inspector.setUpdatesEnabled(False)
        self._inspector.clear()
        for proc in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
            p_data = data.get(proc, {})
            root = QTreeWidgetItem(self._inspector, [proc.upper().replace("_", " "), "ONLINE" if p_data.get("online") else "OFFLINE"])
            for k, v in p_data.items():
                if isinstance(v, (int, float, bool)):
                    QTreeWidgetItem(root, [k, str(v)])
        self._inspector.setUpdatesEnabled(True)

    def _on_enter(self):
        raw = self._in.text().strip()
        if not raw: return
        self._in.clear()
        self._do_print(f"COMMAND: {raw}", theme.ACCENT)
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _dispatch(self, raw):
        p = raw.split(); verb = p[0].lower() if p else ""
        # NO MORE ABBREVIATIONS ALLOWED
        try:
            if verb == "help":
                self.print_signal.emit("FULL COMMAND REFERENCE:", theme.ACCENT)
                self.print_signal.emit(" read <pumping_station | heat_exchanger | boiler | pipeline>", theme.TEXT)
                self.print_signal.emit(" write <process> <register> <value>", theme.TEXT)
                self.print_signal.emit(" plc <process> reload | status", theme.TEXT)
            elif verb == "read" and len(p) >= 2:
                proc = p[1].lower()
                if len(proc) < 3: 
                    self.print_signal.emit("ERROR: Full process name required (e.g., pumping_station)", theme.RED)
                    return
                res = self._get_plant().get(proc)
                self.print_signal.emit(json.dumps(res, indent=2) if res else "Not Found", theme.TEXT)
            elif verb == "cls": QTimer.singleShot(0, self._out.clear)
            else: self.print_signal.emit(f"Unknown Verb: {verb}. Type 'help' for full words.", theme.RED)
        except Exception as e: self.print_signal.emit(f"Shell Error: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, m, c):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(c)); cur.setCharFormat(fmt); cur.insertText(m + "\n"); self._out.ensureCursorVisible()
