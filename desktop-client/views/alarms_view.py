from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QColor
import threading
import theme
from widgets.control_panel import ControlButton


class AlarmsView(QWidget):

    def __init__(self, rest, config):
        super().__init__()
        self._rest   = rest
        self._config = config
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        row = QHBoxLayout()
        title = QLabel("ALARM MANAGEMENT")
        title.setStyleSheet(theme.STYLE_HEADER)
        row.addWidget(title)
        row.addStretch()
        ack_all_btn = ControlButton("ACK ALL",      theme.AMBER)
        hist_btn    = ControlButton("LOAD HISTORY", theme.ACCENT)
        ack_all_btn.clicked.connect(self._ack_all)
        hist_btn.clicked.connect(self._load_history)
        row.addWidget(ack_all_btn)
        row.addWidget(hist_btn)
        root.addLayout(row)

        active_box = QGroupBox("ACTIVE ALARMS")
        active_layout = QVBoxLayout(active_box)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["TIME", "ID", "SEVERITY", "PROCESS", "TAG", "DESCRIPTION"])
        self._table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        active_layout.addWidget(self._table)
        ack_sel_btn = ControlButton("ACK SELECTED", theme.AMBER)
        ack_sel_btn.clicked.connect(self._ack_selected)
        active_layout.addWidget(ack_sel_btn)
        root.addWidget(active_box)

        hist_box = QGroupBox("ALARM HISTORY  (last 20)")
        hist_layout = QVBoxLayout(hist_box)
        self._hist_table = QTableWidget(0, 5)
        self._hist_table.setHorizontalHeaderLabels(
            ["TIME", "ID", "SEVERITY", "PROCESS", "DESCRIPTION"])
        self._hist_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch)
        self._hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_table.verticalHeader().setVisible(False)
        hist_layout.addWidget(self._hist_table)
        root.addWidget(hist_box)

        self._fb = QLabel("")
        self._fb.setStyleSheet(theme.STYLE_DIM)
        root.addWidget(self._fb)

    def update_data(self, alarms: list):
        self._table.setRowCount(0)
        for alarm in alarms:
            row = self._table.rowCount()
            self._table.insertRow(row)
            sev   = alarm.get("sev", "")
            acked = alarm.get("acked", False)
            color = (QColor(theme.RED)   if sev == "CRIT" else
                     QColor(theme.AMBER) if sev == "HIGH" else
                     QColor(theme.TEXT))
            cells = [alarm.get("ts",""), alarm.get("id",""), sev,
                     alarm.get("process",""), alarm.get("tag",""), alarm.get("desc","")]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setForeground(QColor(theme.TEXT_DIM) if acked else color)
                self._table.setItem(row, col, item)

    def _ack_all(self):
        threading.Thread(
            target=self._do_ack,
            args=("all", self._config.get("operator","OPERATOR")),
            daemon=True).start()

    def _ack_selected(self):
        row = self._table.currentRow()
        if row < 0:
            return
        id_item = self._table.item(row, 1)
        if not id_item:
            return
        threading.Thread(
            target=self._do_ack,
            args=(id_item.text(), self._config.get("operator","OPERATOR")),
            daemon=True).start()

    def _do_ack(self, alarm_id: str, operator: str):
        result = self._rest.ack_alarm(alarm_id, operator)
        if result.get("ok"):
            QTimer.singleShot(0, lambda: self._set_fb(
                f"Acknowledged: {result.get('acked')}", theme.GREEN))
        else:
            QTimer.singleShot(0, lambda: self._set_fb(
                f"Ack failed: {result.get('error')}", theme.RED))

    def _load_history(self):
        threading.Thread(target=self._fetch_history, daemon=True).start()

    def _fetch_history(self):
        history = self._rest.get_alarm_history()
        if not history:
            QTimer.singleShot(0, lambda: self._set_fb("No history", theme.TEXT_DIM))
            return
        QTimer.singleShot(0, lambda: self._populate_history(history[-20:]))

    def _populate_history(self, history: list):
        self._hist_table.setRowCount(0)
        for alarm in reversed(history):
            row = self._hist_table.rowCount()
            self._hist_table.insertRow(row)
            sev   = alarm.get("sev", "")
            color = (QColor(theme.RED)   if sev == "CRIT" else
                     QColor(theme.AMBER) if sev == "HIGH" else
                     QColor(theme.TEXT))
            cells = [alarm.get("ts",""), alarm.get("id",""), sev,
                     alarm.get("process",""), alarm.get("desc","")]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setForeground(color)
                self._hist_table.setItem(row, col, item)

    def _set_fb(self, text: str, color: str):
        self._fb.setText(text)
        self._fb.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; background: transparent;")
        QTimer.singleShot(4000, lambda: self._fb.setText(""))
