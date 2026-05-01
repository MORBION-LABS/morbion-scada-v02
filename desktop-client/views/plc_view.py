"""
views/plc_view.py — PLC Program Editor and Monitor
MORBION SCADA v02 — REWRITTEN FOR DEFENSIVE DATA FETCHING
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QTextEdit, QGroupBox, QFileDialog,
    QMessageBox, QListWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import (
    QSyntaxHighlighter, QTextCharFormat, QColor,
    QFont, QTextDocument,
)
import re
import threading
import theme
from widgets.control_panel import ControlButton
from widgets.status_badge  import StatusBadge

class STHighlighter(QSyntaxHighlighter):
    KEYWORDS = ["IF","THEN","ELSIF","ELSE","END_IF","WHILE","DO","END_WHILE","FOR","TO","BY","END_FOR","RETURN","AND","OR","NOT","XOR","VAR","END_VAR","TRUE","FALSE"]
    FB_TYPES = ["TON","TOF","CTU","SR","RS","LIMIT","ABS","MAX","MIN"]

    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._rules = []
        fmt_k, fmt_f, fmt_n, fmt_c = QTextCharFormat(), QTextCharFormat(), QTextCharFormat(), QTextCharFormat()
        fmt_k.setForeground(QColor(theme.ACCENT)); fmt_k.setFontWeight(QFont.Weight.Bold)
        fmt_f.setForeground(QColor(theme.AMBER))
        fmt_n.setForeground(QColor(theme.WHITE))
        fmt_c.setForeground(QColor(theme.TEXT_DIM)); fmt_c.setFontItalic(True)
        for kw in self.KEYWORDS: self._rules.append((re.compile(rf'\b{kw}\b', re.IGNORECASE), fmt_k))
        for fb in self.FB_TYPES: self._rules.append((re.compile(rf'\b{fb}\b', re.IGNORECASE), fmt_f))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), fmt_n))
        self._rules.append((re.compile(r'\(\*.*?\*\)', re.DOTALL), fmt_c))
        self._rules.append((re.compile(r'//[^\n]*'), fmt_c))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

class PLCView(QWidget):
    PROCESSES = [("ps", "pumping_station", "Pumping Station"), ("hx", "heat_exchanger",  "Heat Exchanger"), ("bl", "boiler", "Boiler"), ("pl", "pipeline", "Pipeline")]

    def __init__(self, rest):
        super().__init__()
        self._rest    = rest
        self._process = "pumping_station"
        self._build_ui()
        QTimer.singleShot(500, self._refresh)

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal); splitter.setHandleWidth(2)
        left = QWidget(); left.setMinimumWidth(240); left.setStyleSheet(f"background: {theme.SURFACE}; border-right: 1px solid {theme.BORDER};")
        l_lay = QVBoxLayout(left); l_lay.setContentsMargins(12, 12, 12, 12); l_lay.setSpacing(8)
        l_lay.addWidget(QLabel("PLC PROGRAMS"))
        proc_box = QGroupBox("PROCESS"); p_lay = QVBoxLayout(proc_box)
        for alias, proc, label in self.PROCESSES:
            btn = ControlButton(f"[{alias.upper()}] {label}")
            btn.clicked.connect(lambda checked, p=proc: self._select_process(p))
            p_lay.addWidget(btn)
        l_lay.addWidget(proc_box)
        stat_box = QGroupBox("STATUS"); s_lay = QVBoxLayout(stat_box)
        self._status_badge = StatusBadge(); self._scan_lbl = QLabel("Scan: —"); self._err_lbl = QLabel("Error: —")
        for w in [self._status_badge, self._scan_lbl, self._err_lbl]:
            w.setStyleSheet(theme.STYLE_DIM); s_lay.addWidget(w)
        l_lay.addWidget(stat_box)
        v_box = QGroupBox("VARIABLES"); v_lay = QVBoxLayout(v_box)
        self._in_list = QListWidget(); self._out_list = QListWidget()
        for l in [self._in_list, self._out_list]:
            l.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT_DIM}; border: none; font-size: 10px; max-height: 120px;")
        v_lay.addWidget(QLabel("INPUTS")); v_lay.addWidget(self._in_list)
        v_lay.addWidget(QLabel("OUTPUTS")); v_lay.addWidget(self._out_list)
        l_lay.addWidget(v_box)
        rel_btn = ControlButton("RELOAD FROM DISK", theme.AMBER); rel_btn.clicked.connect(self._reload); l_lay.addWidget(rel_btn)
        l_lay.addStretch(); self._fb = QLabel(""); self._fb.setWordWrap(True); l_lay.addWidget(self._fb); splitter.addWidget(left)
        right = QWidget(); r_lay = QVBoxLayout(right); r_lay.setContentsMargins(0, 0, 0, 0); r_lay.setSpacing(0)
        toolbar = QWidget(); toolbar.setFixedHeight(40); toolbar.setStyleSheet(f"background: {theme.SURFACE}; border-bottom: 1px solid {theme.BORDER};")
        t_lay = QHBoxLayout(toolbar); self._proc_label = QLabel("SELECT PROCESS"); self._proc_label.setStyleSheet(theme.STYLE_ACCENT); t_lay.addWidget(self._proc_label); t_lay.addStretch()
        val_btn = ControlButton("VALIDATE", theme.TEXT_DIM); up_btn = ControlButton("UPLOAD", theme.GREEN); dn_btn = ControlButton("DOWNLOAD", theme.ACCENT)
        val_btn.clicked.connect(self._validate); up_btn.clicked.connect(self._upload); dn_btn.clicked.connect(self._download)
        for b in [val_btn, up_btn, dn_btn]: t_lay.addWidget(b)
        r_lay.addWidget(toolbar)
        self._editor = QTextEdit(); self._editor.setFont(QFont("Courier New", 12)); self._editor.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: none;")
        self._highlighter = STHighlighter(self._editor.document()); r_lay.addWidget(self._editor); splitter.addWidget(right)
        splitter.setSizes([280, 800]); root.addWidget(splitter)

    def _select_process(self, proc: str):
        self._process = proc
        lbl = next((l for _, p, l in self.PROCESSES if p == proc), proc)
        self._proc_label.setText(f"{lbl.upper()} — plc_program.st")
        self._refresh()

    def _refresh(self):
        self._fb.setText("Fetching...")
        threading.Thread(target=self._fetch_all, daemon=True).start()

    def _fetch_all(self):
        p = self._process
        prog = self._rest.plc_get_program(p)
        if prog:
            QTimer.singleShot(0, lambda: self._editor.setPlainText(prog.get("source", "")))
            QTimer.singleShot(0, lambda: self._update_status(prog.get("status", {})))
            vars_res = self._rest.plc_get_variables(p)
            if vars_res: QTimer.singleShot(0, lambda: self._update_vars(vars_res))
            QTimer.singleShot(0, lambda: self._set_fb("Ready", theme.TEXT_DIM))
        else:
            QTimer.singleShot(0, lambda: self._update_status(None))
            QTimer.singleShot(0, lambda: self._editor.setPlainText("(* FAILED TO FETCH SOURCE FROM SERVER *)"))
            QTimer.singleShot(0, lambda: self._set_fb("Communication Error", theme.RED))

    def _update_status(self, stat):
        if not stat:
            self._status_badge.set_offline(); self._scan_lbl.setText("Scan: —"); self._err_lbl.setText("Error: Connection Failed")
            return
        if stat.get("loaded"): self._status_badge.set_custom("● LOADED", theme.GREEN)
        else: self._status_badge.set_custom("✗ ERROR", theme.RED)
        self._scan_lbl.setText(f"Scan count: {stat.get('scan_count','—')}")
        self._err_lbl.setText(f"Last error: {stat.get('last_error','None')[:40]}")

    def _update_vars(self, res):
        self._in_list.clear(); self._out_list.clear()
        v = res.get("variables", {})
        for k in v.get("inputs", {}): self._in_list.addItem(k)
        for k in v.get("outputs", {}): self._out_list.addItem(k)

    def _validate(self):
        self._set_fb("Validating...", theme.TEXT_DIM)
        threading.Thread(target=self._do_val, args=(self._editor.toPlainText(),), daemon=True).start()

    def _do_val(self, src):
        res = self._rest.plc_upload_program(self._process, src)
        color = theme.GREEN if res.get("ok") else theme.RED
        msg = "VALID" if res.get("ok") else f"ERROR: {res.get('error')}"
        QTimer.singleShot(0, lambda: self._set_fb(msg, color))

    def _upload(self):
        if QMessageBox.question(self, "Upload", f"Apply to {self._process}?") == QMessageBox.StandardButton.Yes:
            self._set_fb("Uploading...", theme.TEXT_DIM)
            threading.Thread(target=self._do_up, args=(self._editor.toPlainText(),), daemon=True).start()

    def _do_up(self, src):
        res = self._rest.plc_upload_program(self._process, src)
        if res.get("ok"): QTimer.singleShot(0, lambda: self._set_fb("UPLOADED", theme.GREEN)); QTimer.singleShot(1000, self._refresh)
        else: QTimer.singleShot(0, lambda: self._set_fb(f"FAILED: {res.get('error')}", theme.RED))

    def _reload(self):
        threading.Thread(target=lambda: self._rest.plc_reload(self._process) and self._refresh(), daemon=True).start()

    def _download(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save ST", f"{self._process}.st", "ST (*.st)")
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self._editor.toPlainText())
            self._set_fb("Saved to Disk", theme.GREEN)

    def _set_fb(self, txt, col):
        self._fb.setText(txt); self._fb.setStyleSheet(f"color: {col}; font-family: 'Courier New'; font-size: 11px;")
