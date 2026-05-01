"""
plc_view.py — PLC Monitor and Editor
Surgical Rebuild v05 — THE FINAL FIX
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme, re, threading

class STHighlighter(QSyntaxHighlighter):
    def __init__(self, d):
        super().__init__(d); self._rules = []
        fmt_k = QTextCharFormat(); fmt_k.setForeground(QColor(theme.ACCENT)); fmt_k.setFontWeight(QFont.Weight.Bold)
        fmt_f = QTextCharFormat(); fmt_f.setForeground(QColor(theme.AMBER))
        fmt_c = QTextCharFormat(); fmt_c.setForeground(QColor(theme.TEXT_DIM)); fmt_c.setFontItalic(True)
        kw = ["IF","THEN","ELSIF","ELSE","END_IF","WHILE","DO","END_WHILE","FOR","TO","BY","END_FOR","RETURN","AND","OR","NOT","XOR","VAR","END_VAR","TRUE","FALSE"]
        fb = ["TON","TOF","CTU","SR","RS","LIMIT","ABS","MAX","MIN"]
        for k in kw: self._rules.append((re.compile(rf'\b{k}\b', re.IGNORECASE), fmt_k))
        for f in fb: self._rules.append((re.compile(rf'\b{f}\b', re.IGNORECASE), fmt_f))
        self._rules.append((re.compile(r'\(\*.*?\*\)', re.DOTALL), fmt_c))
    def highlightBlock(self, t):
        for p, f in self._rules:
            for m in p.finditer(t): self.setFormat(m.start(), m.end()-m.start(), f)

class PLCWorker(QThread):
    finished = pyqtSignal(dict); feedback = pyqtSignal(str, str)
    def __init__(self, rest, action, process, source=None):
        super().__init__(); self.rest, self.action, self.process, self.source = rest, action, process, source
    def run(self):
        try:
            if self.action == "sync":
                res = self.rest.plc_get_program(self.process) # Super-Proxy call
                if res: self.finished.emit(res)
                else: self.feedback.emit("Sync Failed", theme.RED)
            elif self.action == "upload":
                res = self.rest.plc_upload(self.process, self.source)
                self.feedback.emit("UPLOAD OK" if res and res.get("ok") else "UPLOAD FAILED", theme.GREEN if res and res.get("ok") else theme.RED)
            elif self.action == "reload":
                res = self.rest.plc_reload(self.process)
                self.feedback.emit("RELOADED" if res and res.get("ok") else "FAILED", theme.GREEN if res and res.get("ok") else theme.RED)
        except Exception as e: self.feedback.emit(f"Error: {e}", theme.RED)

class PLCView(QWidget):
    PROCESSES = [("ps", "Pumping Station"), ("hx", "Heat Exchanger"), ("bl", "Boiler"), ("pl", "Pipeline")]

    def __init__(self, rest):
        super().__init__()
        self._rest = rest; self._process = "bl"; self._build_ui(); self._refresh()

    def _build_ui(self):
        lay = QHBoxLayout(self); splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); left.setMinimumWidth(280); l_lay = QVBoxLayout(left)
        l_lay.addWidget(QLabel("PLC PROGRAMS"))
        p_box = QGroupBox("PROCESS"); p_lay = QVBoxLayout(p_box)
        for alias, name in self.PROCESSES:
            b = QPushButton(f"[{alias.upper()}] {name}")
            b.clicked.connect(lambda checked, a=alias: self._select(a)); p_lay.addWidget(b)
        l_lay.addWidget(p_box)
        from widgets.status_badge import StatusBadge
        self._badge = StatusBadge(); self._scan = QLabel("Scan: —"); self._err = QLabel("Err: —")
        s_box = QGroupBox("STATUS"); s_lay = QVBoxLayout(s_box)
        for w in [self._badge, self._scan, self._err]: s_lay.addWidget(w)
        l_lay.addWidget(s_box)
        self._in_list = QListWidget(); self._out_list = QListWidget()
        v_box = QGroupBox("VARIABLE MAP"); v_lay = QVBoxLayout(v_box)
        for l in [self._in_list, self._out_list]: l.setStyleSheet(f"background:{theme.BG}; font-size:10px; max-height:100px;")
        v_lay.addWidget(QLabel("INPUTS")); v_lay.addWidget(self._in_list); v_lay.addWidget(QLabel("OUTPUTS")); v_lay.addWidget(self._out_list)
        l_lay.addWidget(v_box)
        rel_btn = QPushButton("RELOAD FROM DISK"); rel_btn.clicked.connect(self._on_reload); l_lay.addWidget(rel_btn)
        self._fb = QLabel("Ready"); l_lay.addWidget(self._fb); l_lay.addStretch(); splitter.addWidget(left)
        
        right = QWidget(); r_lay = QVBoxLayout(right); r_lay.setContentsMargins(0,0,0,0); r_lay.setSpacing(0)
        toolbar = QWidget(); toolbar.setFixedHeight(40); toolbar.setStyleSheet(f"background:{theme.SURFACE}; border-bottom:1px solid {theme.BORDER};")
        t_lay = QHBoxLayout(toolbar); self._title = QLabel("PLC — plc_program.st"); self._title.setStyleSheet(theme.STYLE_ACCENT); t_lay.addWidget(self._title); t_lay.addStretch()
        val_btn = QPushButton("VALIDATE"); up_btn = QPushButton("UPLOAD"); dn_btn = QPushButton("DOWNLOAD")
        val_btn.clicked.connect(self._refresh); up_btn.clicked.connect(self._on_upload); dn_btn.clicked.connect(self._on_download)
        for b in [val_btn, up_btn, dn_btn]: t_lay.addWidget(b)
        r_lay.addWidget(toolbar)
        self._editor = QTextEdit(); self._editor.setFont(QFont("Courier New", 11)); self._editor.setStyleSheet(f"background:{theme.BG}; color:{theme.TEXT}; border:none;")
        self._highlighter = STHighlighter(self._editor.document()); r_lay.addWidget(self._editor); splitter.addWidget(right)
        splitter.setSizes([300, 900]); lay.addWidget(splitter)

    def _select(self, p): self._process = p; self._title.setText(f"{p.upper()} — plc_program.st"); self._refresh()
    def _refresh(self):
        self._fb.setText("Syncing..."); self._worker = PLCWorker(self._rest, "sync", self._process)
        self._worker.finished.connect(self._on_sync_done); self._worker.feedback.connect(self._set_fb); self._worker.start()

    def _on_sync_done(self, data):
        self._editor.setPlainText(data.get("source", "(* No Source *)"))
        s = data.get("status", {})
        self._scan.setText(f"Scan: {s.get('scan_count','—')}"); self._err.setText(f"Err: {s.get('last_error','None')[:20]}")
        if s.get("loaded"): self._badge.set_online()
        else: self._badge.set_offline()
        self._in_list.clear(); self._out_list.clear()
        # DRILL INTO THE NESTED JSON RETURNED BY THE SUPER-PROXY
        v_obj = data.get("variables", {})
        v_inner = v_obj.get("variables", v_obj) # Handle double-nesting if present
        for k in v_inner.get("inputs", {}): self._in_list.addItem(k)
        for k in v_inner.get("outputs", {}): self._out_list.addItem(k)
        self._fb.setText("Synchronized")

    def _on_upload(self):
        if QMessageBox.question(self, "Upload", f"Overwrite {self._process}?") == QMessageBox.StandardButton.Yes:
            self._fb.setText("Uploading..."); self._worker = PLCWorker(self._rest, "upload", self._process, self._editor.toPlainText())
            self._worker.feedback.connect(self._set_fb); self._worker.start()

    def _on_reload(self):
        self._fb.setText("Reloading..."); self._worker = PLCWorker(self._rest, "reload", self._process)
        self._worker.feedback.connect(self._set_fb); self._worker.start()

    def _on_download(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save ST", f"{self._process}.st", "ST (*.st)")
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self._editor.toPlainText())
            self._fb.setText("Saved Local Backup")

    def _set_fb(self, txt, col): self._fb.setText(txt); self._fb.setStyleSheet(f"color: {col}; font-weight: bold;")
