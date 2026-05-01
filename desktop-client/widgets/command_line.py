"""
command_line.py — MORBION SCRIPTING ENGINE
Surgical Rebuild v08 — PRO GRADE TERMINAL
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
        
        self._do_print("MORBION SCRIPTING ENGINE v02 — INITIALIZED", theme.ACCENT)
        self._do_print("INPUT MODE: FULL INDUSTRIAL NOMENCLATURE", theme.TEXT_DIM)

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE}; border-top: 2px solid {theme.BORDER};")
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        
        # TITLE BAR
        title = QLabel(" MORBION SCRIPTING ENGINE")
        title.setFixedHeight(22)
        title.setStyleSheet(f"background: {theme.BG}; color: {theme.ACCENT}; font-weight: bold; font-size: 10px; letter-spacing: 1px; border-bottom: 1px solid {theme.BORDER};")
        layout.addWidget(title)

        # HORIZONTAL SPLITTER
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setHandleWidth(4)
        self._h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BORDER}; }}")
        
        # LEFT: WATCHLIST
        left_cont = QWidget(); left_lay = QVBoxLayout(left_cont); left_lay.setContentsMargins(4,4,4,4)
        left_lay.addWidget(QLabel("LIVE TAG WATCHLIST"))
        self._inspector = QTreeWidget()
        self._inspector.setHeaderLabels(["TAG", "VALUE"])
        self._inspector.setStyleSheet(f"background: {theme.BG}; border: 1px solid {theme.BORDER}; font-size: 11px;")
        self._inspector.setColumnWidth(0, 160)
        left_lay.addWidget(self._inspector)
        self._h_splitter.addWidget(left_cont)
        
        # RIGHT: TERMINAL
        right_cont = QWidget(); right_lay = QVBoxLayout(right_cont); right_lay.setContentsMargins(4,4,4,4)
        
        # Input at TOP
        inp_row = QHBoxLayout(); inp_row.setContentsMargins(0,0,0,2)
        prompt = QLabel("morbion › "); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit(); self._in.setPlaceholderText("Enter full command (e.g. read pumping_station)...")
        self._in.setStyleSheet(f"background: {theme.BG}; color: white; border: 1px solid {theme.BORDER}; padding: 4px;")
        self._in.returnPressed.connect(self._on_enter)
        inp_row.addWidget(prompt); inp_row.addWidget(self._in)
        right_lay.addLayout(inp_row)
        
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-family: 'Courier New'; font-size: 12px;")
        right_lay.addWidget(self._out)
        self._h_splitter.addWidget(right_cont)
        
        self._h_splitter.setSizes([300, 900])
        layout.addWidget(self._h_splitter)

    def update_inspector(self, data):
        """Update the watchlist. Efficiently updates existing items instead of clearing."""
        self._inspector.setUpdatesEnabled(False)
        procs = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]
        
        if self._inspector.topLevelItemCount() == 0:
            # First time: Build the tree
            for p in procs:
                p_data = data.get(p, {})
                root = QTreeWidgetItem(self._inspector, [p.upper().replace("_", " "), ""])
                root.setData(0, Qt.ItemDataRole.UserRole, p) # Store proc key
        
        for i in range(self._inspector.topLevelItemCount()):
            item = self._inspector.topLevelItem(i)
            p_key = item.data(0, Qt.ItemDataRole.UserRole)
            p_data = data.get(p_key, {})
            
            status = "ONLINE" if p_data.get("online") else "OFFLINE"
            item.setText(1, status)
            item.setForeground(1, QColor(theme.GREEN if p_data.get("online") else theme.RED))
            
            # Update children (variables)
            if p_data.get("online") and item.childCount() == 0:
                for k, v in p_data.items():
                    if isinstance(v, (int, float, bool)) and k not in ["online", "port"]:
                        QTreeWidgetItem(item, [k, str(v)])
            elif p_data.get("online"):
                for j in range(item.childCount()):
                    child = item.child(j)
                    tag_name = child.text(0)
                    child.setText(1, str(p_data.get(tag_name, "—")))
        
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
                self.print_signal.emit(" COMMAND SET:", theme.ACCENT)
                self.print_signal.emit("  read pumping_station | heat_exchanger | boiler | pipeline", theme.TEXT)
                self.print_signal.emit("  plc boiler status | source | reload", theme.TEXT)
                self.print_signal.emit("  cls", theme.TEXT)
            elif verb == "cls": QTimer.singleShot(0, self._out.clear)
            elif verb == "read" and len(parts) >= 2:
                p_name = parts[1].lower()
                res = self._get_plant().get(p_name)
                self.print_signal.emit(json.dumps(res, indent=2) if res else f"'{p_name}' NOT FOUND", theme.TEXT)
            elif verb == "plc" and len(parts) >= 3:
                p, sub = parts[1], parts[2]
                if sub == "status":
                    res = self._rest.plc_get_status(p)
                    self.print_signal.emit(json.dumps(res, indent=2) if res else "OFFLINE", theme.GREEN)
                elif sub == "source":
                    res = self._rest.plc_get_program(p)
                    self.print_signal.emit(res.get("source", "NO SOURCE") if res else "TIMEOUT", theme.WHITE)
            else:
                self.print_signal.emit(f"INVALID VERB: {verb}. USE FULL NAMES.", theme.RED)
        except Exception as e:
            self.print_signal.emit(f"ERROR: {e}", theme.RED)

    @pyqtSlot(str, str)
    def _do_print(self, m, c):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(c)); cur.setCharFormat(fmt); cur.insertText(m + "\n"); self._out.ensureCursorVisible()
