"""
plc_view.py — MORBION SCADA PLC Programs View
MORBION SCADA v02 — NEW

ST program editor and runtime status for all four processes.
Operators and engineers can:
  - View current ST program source for any process
  - Upload new ST program (validated before applying)
  - Hot reload ST program from file on disk
  - View PLC runtime status (loaded, scan_count, last_error)
  - View variable map (inputs/outputs/parameters)
"""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QTextEdit, QComboBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui  import QFont, QColor

from views.base_view import BaseView
from theme import (C_ACCENT, C_TEXT2, C_MUTED, C_RED,
                   C_GREEN, C_YELLOW)


class PLCView(BaseView):

    PROCESSES = [
        ("pumping_station", "Pumping Station"),
        ("heat_exchanger",  "Heat Exchanger"),
        ("boiler",          "Boiler"),
        ("pipeline",        "Pipeline"),
    ]

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Process selector + controls ───────────────────────────────────────
        ctrl_bar = QHBoxLayout()

        lbl = QLabel("PROCESS:")
        lbl.setStyleSheet(
            f"color:{C_TEXT2};font-size:10px;letter-spacing:1px;")
        ctrl_bar.addWidget(lbl)

        self._proc_combo = QComboBox()
        for key, name in self.PROCESSES:
            self._proc_combo.addItem(name, key)
        self._proc_combo.currentIndexChanged.connect(
            self._on_process_changed)
        ctrl_bar.addWidget(self._proc_combo)
        ctrl_bar.addSpacing(16)

        self._load_btn = QPushButton("LOAD PROGRAM")
        self._load_btn.clicked.connect(self._on_load)
        ctrl_bar.addWidget(self._load_btn)

        self._reload_btn = QPushButton("HOT RELOAD")
        self._reload_btn.clicked.connect(self._on_reload)
        self._reload_btn.setToolTip(
            "Reload ST program from file on PLC machine disk")
        ctrl_bar.addWidget(self._reload_btn)

        self._upload_btn = QPushButton("UPLOAD PROGRAM")
        self._upload_btn.clicked.connect(self._on_upload)
        self._upload_btn.setToolTip(
            "Upload ST source from editor to PLC process")
        ctrl_bar.addWidget(self._upload_btn)

        ctrl_bar.addStretch()

        # Status indicator
        self._status_lbl = QLabel("●  NOT LOADED")
        self._status_lbl.setStyleSheet(
            f"color:{C_MUTED};font-size:10px;letter-spacing:1px;")
        ctrl_bar.addWidget(self._status_lbl)

        root.addLayout(ctrl_bar)

        # ── Feedback bar ──────────────────────────────────────────────────────
        self._feedback = QLabel("")
        self._feedback.setStyleSheet(
            f"color:{C_ACCENT};font-size:10px;padding:3px 8px;"
            f"background:#020a12;border:1px solid #0d2030;")
        self._feedback.hide()
        root.addWidget(self._feedback)

        # ── Main splitter ─────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: ST editor
        left_group = QGroupBox("ST PROGRAM SOURCE")
        left_layout = QVBoxLayout(left_group)

        self._editor = QTextEdit()
        self._editor.setFont(QFont("Courier New", 10))
        self._editor.setStyleSheet(
            "background-color: #010810;"
            "color: #00d4ff;"
            "border: 1px solid #0d2030;"
            "padding: 4px;")
        self._editor.setPlaceholderText(
            "Click LOAD PROGRAM to fetch ST source from process...")
        left_layout.addWidget(self._editor)
        splitter.addWidget(left_group)

        # Right: status + variables
        right_group = QGroupBox("RUNTIME STATUS & VARIABLES")
        right_layout = QVBoxLayout(right_group)

        # Status table
        status_lbl = QLabel("RUNTIME STATUS")
        status_lbl.setStyleSheet(
            f"color:{C_TEXT2};font-size:9px;letter-spacing:2px;")
        right_layout.addWidget(status_lbl)

        self._status_table = QTableWidget(0, 2)
        self._status_table.setHorizontalHeaderLabels(["KEY", "VALUE"])
        self._status_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._status_table.verticalHeader().setVisible(False)
        self._status_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._status_table.setMaximumHeight(140)
        right_layout.addWidget(self._status_table)

        # Variables table
        var_lbl = QLabel("VARIABLE MAP")
        var_lbl.setStyleSheet(
            f"color:{C_TEXT2};font-size:9px;letter-spacing:2px;"
            f"margin-top:8px;")
        right_layout.addWidget(var_lbl)

        self._var_table = QTableWidget(0, 3)
        self._var_table.setHorizontalHeaderLabels(
            ["TYPE", "ST VARIABLE", "STATE FIELD"])
        self._var_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._var_table.verticalHeader().setVisible(False)
        self._var_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self._var_table)

        splitter.addWidget(right_group)
        splitter.setSizes([700, 350])
        root.addWidget(splitter, 1)

    def _current_process(self) -> str:
        return self._proc_combo.currentData()

    def _on_process_changed(self):
        self._editor.clear()
        self._status_table.setRowCount(0)
        self._var_table.setRowCount(0)
        self._status_lbl.setText("●  NOT LOADED")
        self._status_lbl.setStyleSheet(
            f"color:{C_MUTED};font-size:10px;letter-spacing:1px;")

    def _on_load(self):
        proc = self._current_process()
        self._show_feedback(f"Loading {proc} program...", C_TEXT2)
        if self._rest:
            self._rest.plc_get_program(proc, self._on_program_loaded)
            self._rest.plc_get_variables(proc, self._on_variables_loaded)

    def _on_reload(self):
        proc = self._current_process()
        self._show_feedback(f"Hot reloading {proc}...", C_TEXT2)
        if self._rest:
            self._rest.plc_reload(proc, self._on_reload_result)

    def _on_upload(self):
        proc   = self._current_process()
        source = self._editor.toPlainText().strip()
        if not source:
            self._show_feedback("Editor is empty — nothing to upload",
                                C_RED)
            return
        self._show_feedback(
            f"Uploading {proc} program (validating syntax)...",
            C_TEXT2)
        if self._rest:
            self._rest.plc_upload(proc, source, self._on_upload_result)

    def _on_program_loaded(self, result: dict):
        if "error" in result:
            self._show_feedback(
                f"Load failed: {result['error']}", C_RED)
            return

        source = result.get("source", "")
        self._editor.setPlainText(source)

        status = result.get("status", {})
        self._update_status_table(status)

        loaded = status.get("loaded", False)
        error  = status.get("last_error", "")
        if loaded:
            scans = status.get("scan_count", 0)
            self._status_lbl.setText(f"●  LOADED  scans={scans}")
            self._status_lbl.setStyleSheet(
                f"color:{C_GREEN};font-size:10px;letter-spacing:1px;")
        else:
            self._status_lbl.setText(f"●  LOAD ERROR")
            self._status_lbl.setStyleSheet(
                f"color:{C_RED};font-size:10px;letter-spacing:1px;")

        self._show_feedback(
            f"Program loaded — "
            f"{len(source.splitlines())} lines", C_GREEN)

    def _on_variables_loaded(self, result: dict):
        if "error" in result:
            return

        variables = result.get("variables", {})
        rows = []

        for st_var, state_field in variables.get(
                "inputs", {}).items():
            rows.append(("INPUT", st_var, state_field))
        for st_var, state_field in variables.get(
                "outputs", {}).items():
            rows.append(("OUTPUT", st_var, state_field))
        for st_var, val in variables.get(
                "parameters", {}).items():
            rows.append(("PARAM", st_var, str(val)))

        self._var_table.setRowCount(len(rows))
        type_colors = {
            "INPUT":  C_ACCENT,
            "OUTPUT": C_GREEN,
            "PARAM":  C_YELLOW,
        }
        for row, (typ, st_var, field) in enumerate(rows):
            color = QColor(type_colors.get(typ, C_TEXT2))
            for col, text in enumerate([typ, st_var, field]):
                item = QTableWidgetItem(text)
                item.setForeground(color)
                self._var_table.setItem(row, col, item)

    def _on_reload_result(self, result: dict):
        if result.get("ok"):
            status = result.get("status", {})
            self._update_status_table(status)
            self._show_feedback("Program hot reloaded", C_GREEN)
            # Refresh source after reload
            self._on_load()
        else:
            self._show_feedback(
                f"Reload failed: {result.get('error', '?')}",
                C_RED)

    def _on_upload_result(self, result: dict):
        if result.get("ok"):
            status = result.get("status", {})
            self._update_status_table(status)
            self._show_feedback(
                "Program uploaded and loaded", C_GREEN)
        else:
            error = result.get("error", "Upload failed")
            self._show_feedback(f"Upload failed: {error}", C_RED)

    def _update_status_table(self, status: dict):
        items = [
            ("Loaded",       str(status.get("loaded", "?"))),
            ("Scan Count",   str(status.get("scan_count", 0))),
            ("Program File", status.get("program_file", "?")),
            ("Last Error",   status.get("last_error", "none")),
        ]
        self._status_table.setRowCount(len(items))
        for row, (key, val) in enumerate(items):
            k_item = QTableWidgetItem(key)
            k_item.setForeground(QColor(C_TEXT2))
            v_item = QTableWidgetItem(val)
            has_error = (key == "Last Error" and val not in ("none", ""))
            v_item.setForeground(
                QColor(C_RED if has_error else C_ACCENT))
            self._status_table.setItem(row, 0, k_item)
            self._status_table.setItem(row, 1, v_item)

    def _show_feedback(self, msg: str, color: str):
        self._feedback.setText(msg)
        self._feedback.setStyleSheet(
            f"color:{color};font-size:10px;padding:3px 8px;"
            f"background:#020a12;border:1px solid #0d2030;")
        self._feedback.show()

    def update_data(self, plant: dict):
        # PLCView does not update from WebSocket push
        # It uses explicit REST calls via the load/reload buttons
        pass
