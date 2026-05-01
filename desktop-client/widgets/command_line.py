"""
command_line.py — MORBION SCRIPTING ENGINE
Surgical Rebuild v07 — Final Layout & Branding
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
        
        self._do_print("MORBION SCADA v02 — CORE SCRIPTING INTERFACE", theme.ACCENT)
        self._do_print("SYSTEM STATUS: NOMINAL", theme.GREEN)

    def _build_ui(self):
        # Main Border and Title
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        main_v_lay = QVBoxLayout(self); main_v_lay.setContentsMargins(0,0,0,0); main_v_lay.setSpacing(0)
        
        # Section Header
        self._header = QLabel(" MORBION SCRIPTING ENGINE")
        self._header.setFixedHeight(24)
        self._header.setStyleSheet(f"""
            background: {theme.BG}; 
            color: {theme.ACCENT}; 
            font-family: 'Courier New'; 
            font-weight: bold; 
            font-size: 11px; 
            letter-spacing: 2px;
            border-bottom: 1px solid {theme.BORDER};
        """)
        main_v_lay.addWidget(self._header)

        # Horizontal Splitter (Watchlist | Terminal)
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setHandleWidth(4)
        self._h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BORDER}; }}")
        
        # ── LEFT: TAG WATCHLIST ──
        # This is for seeing variables live without typing 'read'
        left_widget = QWidget(); left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(5,5,5,5)
        watchlist_lbl = QLabel("VARIABLE WATCHLIST (LIVE)"); watchlist_lbl.setStyleSheet(theme.STYLE_DIM)
        self._inspector = QTreeWidget()
        self._inspector.setHeaderLabels(["PROCESS / TAG", "VALUE"])
        self._inspector.setIndentation(15)
        self._inspector.setColumnWidth(0, 180)
        self._inspector.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-size: 11px;")
        left_lay.addWidget(watchlist_lbl); left_lay.addWidget(self._inspector)
        self._h_splitter.addWidget(left_widget)
        
        # ── RIGHT: TERMINAL ──
        right_widget = QWidget(); right_lay = QVBoxLayout(right_widget)
        right_lay.setContentsMargins(5,5,5,5)
        
        # Input Box at the TOP (Modern Grade)
        inp_cont = QWidget(); inp_lay = QHBoxLayout(inp_cont); inp_lay.setContentsMargins(0,0,0,5)
        prompt = QLabel("morbion command › "); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit(); self._in.setPlaceholderText("Enter industrial command...")
        self._in.setStyleSheet(f"background: {theme.BG}; color: white; border: 1px solid {theme.BORDER}; padding: 6px; font-family: 'Courier New';")
        self._in.returnPressed.connect(self._on_enter)
        inp_lay.addWidget(prompt); inp_lay.addWidget(self._in)
        right_lay.addWidget(inp_cont)
        
        # Console Output
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-family: 'Courier New'; font-size: 12px;")
        right_lay.addWidget(self._out)
        
        self._h_splitter.addWidget(right_widget)
        self._h_splitter.setSizes([350, 850])
        main_v_lay.addWidget(self._h_splitter)

    def update_inspector(self, data):
        """Update the Tag Watchlist tree live from WebSocket."""
        # Use simple recursion to prevent UI lag
        self._inspector.setUpdatesEnabled(False)
        self._inspector.clear()
        procs = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]
        for p in procs:
            p_data = data.get(p, {})
            root = QTreeWidgetItem(self._inspector, [p.upper().replace("_", " "), "ONLINE" if p_data.get("online") else "OFFLINE"])
            if p_data.get("online"):
                root.setForeground(1, QColor(theme.GREEN))
                for k, v in p_data.items():
                    if isinstance(v, (int, float, bool)):
                        QTreeWidgetItem(root, [str(k), str(v)])
            else:
                root.setForeground(1, QColor(theme.RED))
        self._inspector.setUpdatesEnabled(True)

    def _on_enter(self):
        raw = self._in.text().strip()
        if not raw: return
        self._in.clear(); self._do_print(f"› {raw}", theme.ACCENT)
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _dispatch(self, raw):
        parts = raw.split(); verb = parts[0].lower() if parts else ""
        try:
            if verb == "help":
                self.print_signal.emit(" INDUSTRIAL VERB SET:", theme.ACCENT)
                self.print_signal.emit("  read <process_name>", theme.TEXT)
                self.print_signal.emit("  write <process_name> <register> <value>", theme.TEXT)
                self.print_signal.emit("  plc <process_name> status | source | reload", theme.TEXT)
                self.print_signal.emit("  cls (clear terminal)", theme.TEXT)
            elif verb == "cls": QTimer.singleShot(0, self._out.clear)
            elif verb == "read" and len(parts) >= 2:
                res = self._get_plant().get(parts[1].lower())
                self.print_signal.emit(json.dumps(res, indent=2) if res else "PROCESS NOT FOUND", theme.TEXT)
            elif verb == "plc" and len(parts) >= 3:
                p, sub = parts[1], parts[2]
                if sub == "status":
                    res = self._rest.plc_get_status(p)
                    self.print_signal.emit(json.dumps(res, indent=2) if res else "PLC UNREACHABLE", theme.GREEN)
                elif sub == "source":
                    res = self._rest.plc_get_program(p)
                    self.print_signal.emit(res.get("source", "NO SOURCE") if res else "ERROR", theme.WHITE)
            else:
                self.print_signal.emit(f"INVALID VERB: {verb}. Use full process names.", theme.RED)
        except Exception as e:
            self.print_signal.emit(f"EXECUTION ERROR: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, m, c):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(c)); cur.setCharFormat(fmt); cur.insertText(m + "\n"); self._out.ensureCursorVisible()
