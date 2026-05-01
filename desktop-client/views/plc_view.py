"""
plc_view.py — PLC Monitor/Editor View
MORBION SCADA v02 — SURGICAL REBOOT (NON-BLOCKING)

Rewritten to prevent the "Black Screen" effect by using 
a safe background thread for all syncing.
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import threading, theme, re

class STHighlighter(QSyntaxHighlighter):
    """Syntax highlighting for IEC 61131-3 Structured Text."""
    def __init__(self, document):
        super().__init__(document); self._rules = []
        fmt = QTextCharFormat(); fmt.setForeground(QColor(theme.ACCENT))
        kw = ["IF","THEN","ELSIF","ELSE","END_IF","WHILE","DO","FOR","TO","RETURN","VAR","END_VAR","TRUE","FALSE"]
        for k in kw: self._rules.append((re.compile(rf'\b{k}\b', re.IGNORECASE), fmt))
    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text): self.setFormat(match.start(), match.end()-match.start(), fmt)

class PLCView(QWidget):
    # Aliases must match RestClient.MAP
    PROCESSES = [("ps", "Pumping Station"), ("hx", "Heat Exchanger"), ("bl", "Boiler"), ("pl", "Pipeline")]

    def __init__(self, rest):
        super().__init__()
        self._rest = rest; self._process = "bl" # Default to Boiler
        self._build_ui(); QTimer.singleShot(500, self._refresh)

    def _build_ui(self):
        lay = QHBoxLayout(self); splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Selector)
        left = QWidget(); left.setMinimumWidth(280); l_lay = QVBoxLayout(left)
        l_lay.addWidget(QLabel("PLC PROGRAMS"))
        p_box = QGroupBox("SELECT PROCESS"); p_lay = QVBoxLayout(p_box)
        for alias, name in self.PROCESSES:
            b = QPushButton(f"[{alias.upper()}] {name}")
            b.clicked.connect(lambda checked, a=alias: self._select(a)); p_lay.addWidget(b)
        l_lay.addWidget(p_box)
        
        # Runtime Status
        from widgets.status_badge import StatusBadge
        self._badge = StatusBadge(); self._scan = QLabel("Scan: —"); self._err = QLabel("Err: —")
        s_box = QGroupBox("RUNTIME STATUS"); s_lay = QVBoxLayout(s_box)
        for w in [self._badge, self._scan, self._err]: s_lay.addWidget(w)
        l_lay.addWidget(s_box)
        
        # Variables
        self._in_list = QListWidget(); self._out_list = QListWidget()
        v_box = QGroupBox("IO MAP"); v_lay = QVBoxLayout(v_box)
        v_lay.addWidget(QLabel("INPUTS")); v_lay.addWidget(self._in_list)
        v_lay.addWidget(QLabel("OUTPUTS")); v_lay.addWidget(self._out_list)
        l_lay.addWidget(v_box)
        
        self._fb = QLabel("Ready"); l_lay.addWidget(self._fb); l_lay.addStretch()
        splitter.addWidget(left)
        
        # Right Panel (Editor)
        right = QWidget(); r_lay = QVBoxLayout(right)
        self._title = QLabel("ST SOURCE EDITOR"); self._title.setStyleSheet(theme.STYLE_ACCENT)
        r_lay.addWidget(self._title)
        self._editor = QTextEdit(); self._editor.setFont(QFont("Courier New", 11))
        self._editor.setAcceptRichText(False); self._editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._highlighter = STHighlighter(self._editor.document())
        r_lay.addWidget(self._editor); splitter.addWidget(right)
        
        lay.addWidget(splitter)

    def _select(self, proc):
        self._process = proc; self._title.setText(f"{proc.upper()} — plc_program.st")
        self._refresh()

    def _refresh(self):
        self._fb.setText("Syncing..."); self._fb.setStyleSheet(f"color: {theme.ACCENT};")
        threading.Thread(target=self._sync_logic, daemon=True).start()

    def _sync_logic(self):
        """Background thread logic to keep the UI from hanging."""
        try:
            # 1. Fetch Program and Status
            res = self._rest.plc_get_program(self._process)
            if res:
                QTimer.singleShot(0, lambda: self._editor.setPlainText(res.get("source", "")))
                QTimer.singleShot(0, lambda: self._update_status(res.get("status", {})))
                
                # 2. Fetch Variable Map
                v = self._rest.plc_get_variables(self._process)
                if v: QTimer.singleShot(0, lambda: self._update_vars(v))
                QTimer.singleShot(0, lambda: self._fb.setText("Sync OK"))
            else:
                raise Exception("Server Timeout")
        except Exception as e:
            QTimer.singleShot(0, lambda: self._fb.setText(f"Sync Failed: {e}"))
            QTimer.singleShot(0, lambda: self._badge.set_offline())

    def _update_status(self, s):
        self._scan.setText(f"Scan Count: {s.get('scan_count', '—')}")
        err = s.get('last_error', 'None')
        self._err.setText(f"Last Error: {err[:30] if err else 'None'}")
        if s.get("loaded"): self._badge.set_online()
        else: self._badge.set_offline()

    def _update_vars(self, v):
        self._in_list.clear(); self._out_list.clear()
        vars = v.get("variables", {})
        for k in vars.get("inputs", {}): self._in_list.addItem(k)
        for k in vars.get("outputs", {}): self._out_list.addItem(k)
