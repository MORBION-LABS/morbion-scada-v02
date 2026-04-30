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

    KEYWORDS = [
        "IF","THEN","ELSIF","ELSE","END_IF",
        "WHILE","DO","END_WHILE","FOR","TO",
        "BY","END_FOR","RETURN","AND","OR",
        "NOT","XOR","VAR","END_VAR","TRUE","FALSE",
    ]
    FB_TYPES = ["TON","TOF","CTU","SR","RS","LIMIT","ABS","MAX","MIN"]

    def __init__(self, document: QTextDocument):
        super().__init__(document)

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(theme.ACCENT))
        kw_fmt.setFontWeight(QFont.Weight.Bold)

        fb_fmt = QTextCharFormat()
        fb_fmt.setForeground(QColor(theme.AMBER))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(theme.WHITE))

        cmt_fmt = QTextCharFormat()
        cmt_fmt.setForeground(QColor(theme.TEXT_DIM))
        cmt_fmt.setFontItalic(True)

        self._rules = []
        for kw in self.KEYWORDS:
            self._rules.append((re.compile(rf'\b{kw}\b', re.IGNORECASE), kw_fmt))
        for fb in self.FB_TYPES:
            self._rules.append((re.compile(rf'\b{fb}\b', re.IGNORECASE), fb_fmt))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), num_fmt))
        self._rules.append((re.compile(r'\(\*.*?\*\)', re.DOTALL), cmt_fmt))
        self._rules.append((re.compile(r'//[^\n]*'), cmt_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class PLCView(QWidget):

    PROCESSES = [
        ("ps", "pumping_station", "Pumping Station"),
        ("hx", "heat_exchanger",  "Heat Exchanger"),
        ("bl", "boiler",          "Boiler"),
        ("pl", "pipeline",        "Pipeline"),
    ]

    def __init__(self, rest):
        super().__init__()
        self._rest    = rest
        self._process = "boiler"
        self._build_ui()
        QTimer.singleShot(500, self._refresh)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Left panel
        left = QWidget()
        left.setFixedWidth(280)
        left.setStyleSheet(
            f"background: {theme.SURFACE}; border-right: 1px solid {theme.BORDER};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel("PLC PROGRAMS"))

        proc_box = QGroupBox("PROCESS")
        proc_layout = QVBoxLayout(proc_box)
        for alias, proc, label in self.PROCESSES:
            btn = ControlButton(f"[{alias.upper()}] {label}")
            btn.clicked.connect(
                lambda checked, p=proc: self._select_process(p))
            proc_layout.addWidget(btn)
        left_layout.addWidget(proc_box)

        status_box = QGroupBox("STATUS")
        status_layout = QVBoxLayout(status_box)
        self._status_badge   = StatusBadge()
        self._scan_count_lbl = QLabel("Scan count: —")
        self._scan_count_lbl.setStyleSheet(theme.STYLE_DIM)
        self._last_error_lbl = QLabel("Last error: —")
        self._last_error_lbl.setStyleSheet(theme.STYLE_DIM)
        self._last_error_lbl.setWordWrap(True)
        status_layout.addWidget(self._status_badge)
        status_layout.addWidget(self._scan_count_lbl)
        status_layout.addWidget(self._last_error_lbl)
        left_layout.addWidget(status_box)

        vars_box = QGroupBox("VARIABLES")
        vars_layout = QVBoxLayout(vars_box)
        inputs_lbl = QLabel("INPUTS")
        inputs_lbl.setStyleSheet(theme.STYLE_DIM)
        self._inputs_list = QListWidget()
        self._inputs_list.setMaximumHeight(80)
        self._inputs_list.setStyleSheet(
            f"background: {theme.BG}; color: {theme.TEXT_DIM}; "
            f"border: none; font-family: 'Courier New', monospace; font-size: 10px;")
        outputs_lbl = QLabel("OUTPUTS")
        outputs_lbl.setStyleSheet(theme.STYLE_DIM)
        self._outputs_list = QListWidget()
        self._outputs_list.setMaximumHeight(80)
        self._outputs_list.setStyleSheet(
            f"background: {theme.BG}; color: {theme.TEXT_DIM}; "
            f"border: none; font-family: 'Courier New', monospace; font-size: 10px;")
        vars_layout.addWidget(inputs_lbl)
        vars_layout.addWidget(self._inputs_list)
        vars_layout.addWidget(outputs_lbl)
        vars_layout.addWidget(self._outputs_list)
        left_layout.addWidget(vars_box)

        reload_btn = ControlButton("RELOAD FROM DISK", theme.AMBER)
        reload_btn.clicked.connect(self._reload)
        left_layout.addWidget(reload_btn)

        left_layout.addStretch()
        self._fb = QLabel("")
        self._fb.setStyleSheet(theme.STYLE_DIM)
        self._fb.setWordWrap(True)
        left_layout.addWidget(self._fb)

        splitter.addWidget(left)

        # Right panel — editor
        right = QWidget()
        right.setStyleSheet(f"background: {theme.BG};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(
            f"background: {theme.SURFACE}; border-bottom: 1px solid {theme.BORDER};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 0, 8, 0)
        tb_layout.setSpacing(8)
        self._proc_label = QLabel("BOILER — plc_program.st")
        self._proc_label.setStyleSheet(theme.STYLE_ACCENT)
        tb_layout.addWidget(self._proc_label)
        tb_layout.addStretch()
        validate_btn = ControlButton("VALIDATE", theme.TEXT_DIM)
        upload_btn   = ControlButton("UPLOAD",   theme.GREEN)
        download_btn = ControlButton("DOWNLOAD", theme.ACCENT)
        validate_btn.clicked.connect(self._validate)
        upload_btn.clicked.connect(self._upload)
        download_btn.clicked.connect(self._download)
        tb_layout.addWidget(validate_btn)
        tb_layout.addWidget(upload_btn)
        tb_layout.addWidget(download_btn)
        right_layout.addWidget(toolbar)

        self._editor = QTextEdit()
        self._editor.setFont(QFont("Courier New", 12))
        self._editor.setStyleSheet(
            f"background: {theme.BG}; color: {theme.TEXT}; "
            f"border: none; font-family: 'Courier New', monospace; font-size: 12px;")
        self._highlighter = STHighlighter(self._editor.document())
        right_layout.addWidget(self._editor)

        splitter.addWidget(right)
        splitter.setSizes([280, 800])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        root.addWidget(splitter)

    def _select_process(self, proc: str):
        self._process = proc
        label = next((l for _, p, l in self.PROCESSES if p == proc), proc)
        self._proc_label.setText(f"{label.upper()} — plc_program.st")
        self._refresh()

    def _refresh(self):
        threading.Thread(target=self._fetch_all, daemon=True).start()

    def _fetch_all(self):
        result = self._rest.plc_get_status(self._process)
        QTimer.singleShot(0, lambda: self._update_status(result))
        prog = self._rest.plc_get_program(self._process)
        if prog:
            source = prog.get("source", "")
            QTimer.singleShot(0, lambda: self._editor.setPlainText(source))
        var_result = self._rest.plc_get_variables(self._process)
        QTimer.singleShot(0, lambda: self._update_vars(var_result))

    def _update_status(self, result):
        if not result:
            self._status_badge.set_offline()
            self._scan_count_lbl.setText("Scan count: —")
            self._last_error_lbl.setText("Unreachable")
            return
        status = result.get("status", result)
        if status.get("loaded", False):
            self._status_badge.set_custom("● LOADED", theme.GREEN)
        else:
            self._status_badge.set_custom("✗ NOT LOADED", theme.RED)
        self._scan_count_lbl.setText(f"Scan count: {status.get('scan_count','—')}")
        err = status.get("last_error","") or "—"
        self._last_error_lbl.setText(f"Last error: {err[:60]}")

    def _update_vars(self, result):
        if not result:
            return
        variables = result.get("variables", {})
        self._inputs_list.clear()
        for k in variables.get("inputs", {}):
            self._inputs_list.addItem(k)
        self._outputs_list.clear()
        for k in variables.get("outputs", {}):
            self._outputs_list.addItem(k)

    def _validate(self):
        source = self._editor.toPlainText()
        if not source.strip():
            self._set_fb("Editor is empty", theme.AMBER)
            return
        self._set_fb("Validating...", theme.TEXT_DIM)
        threading.Thread(target=self._do_validate, args=(source,), daemon=True).start()

    def _do_validate(self, source: str):
        result = self._rest.plc_upload_program(self._process, source)
        if result.get("ok"):
            QTimer.singleShot(0, lambda: self._set_fb("VALID — accepted", theme.GREEN))
        else:
            err = result.get("error","Unknown")
            QTimer.singleShot(0, lambda: self._set_fb(f"PARSE ERROR: {err}", theme.RED))

    def _upload(self):
        source = self._editor.toPlainText()
        if not source.strip():
            self._set_fb("Editor is empty", theme.AMBER)
            return
        reply = QMessageBox.question(
            self, "Upload PLC Program",
            f"Upload and apply new ST program to {self._process}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._set_fb("Uploading...", theme.TEXT_DIM)
        threading.Thread(target=self._do_upload, args=(source,), daemon=True).start()

    def _do_upload(self, source: str):
        result = self._rest.plc_upload_program(self._process, source)
        if result.get("ok"):
            QTimer.singleShot(0, lambda: self._set_fb("UPLOADED — program live", theme.GREEN))
            QTimer.singleShot(1000, self._refresh)
        else:
            err = result.get("error","Unknown")
            QTimer.singleShot(0, lambda: self._set_fb(f"UPLOAD FAILED: {err}", theme.RED))

    def _reload(self):
        self._set_fb("Reloading from disk...", theme.TEXT_DIM)
        threading.Thread(target=self._do_reload, daemon=True).start()

    def _do_reload(self):
        result = self._rest.plc_reload(self._process)
        if result.get("ok"):
            QTimer.singleShot(0, lambda: self._set_fb("RELOADED from disk", theme.GREEN))
            QTimer.singleShot(500, self._refresh)
        else:
            QTimer.singleShot(0, lambda: self._set_fb(
                f"RELOAD FAILED: {result.get('error')}", theme.RED))

    def _download(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ST Program",
            f"{self._process}_plc_program.st",
            "Structured Text (*.st);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write(self._editor.toPlainText())
            self._set_fb(f"Saved: {path}", theme.GREEN)
        except Exception as e:
            self._set_fb(f"Save failed: {e}", theme.RED)

    def _set_fb(self, text: str, color: str):
        self._fb.setText(text)
        self._fb.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; background: transparent;")
