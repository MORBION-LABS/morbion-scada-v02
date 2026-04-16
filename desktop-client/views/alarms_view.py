"""
alarms_view.py — MORBION SCADA Alarms View
MORBION SCADA v02

KEY CHANGES FROM v01:
  - Alarm acknowledgment workflow
  - Three states: UNACK (bright), ACKED (dim), shows acked_at time
  - ACK button per row + ACK ALL button
  - Unacknowledged count shown in summary bar
  - Alarm history button opens history from server
"""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui  import QColor

from views.base_view import BaseView
from theme import SEV_COLORS, C_MUTED, C_TEXT2, C_ACCENT, C_RED, C_GREEN


class AlarmsView(BaseView):

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Summary bar ───────────────────────────────────────────────────────
        bar = QHBoxLayout()

        self._total_lbl = QLabel("ACTIVE ALARMS: 0")
        self._total_lbl.setStyleSheet(
            f"color:{C_ACCENT};font-size:12px;"
            f"letter-spacing:2px;font-weight:bold;")

        self._crit_lbl = QLabel("CRIT: 0")
        self._crit_lbl.setStyleSheet(
            f"color:#ff3333;font-size:11px;")

        self._high_lbl = QLabel("HIGH: 0")
        self._high_lbl.setStyleSheet(
            f"color:#ff8800;font-size:11px;")

        self._unacked_lbl = QLabel("UNACKED: 0")
        self._unacked_lbl.setStyleSheet(
            f"color:#ff3333;font-size:11px;font-weight:bold;")

        bar.addWidget(self._total_lbl)
        bar.addWidget(self._crit_lbl)
        bar.addWidget(self._high_lbl)
        bar.addWidget(self._unacked_lbl)
        bar.addStretch()

        # ACK ALL button
        self._ack_all_btn = QPushButton("ACK ALL")
        self._ack_all_btn.setFixedWidth(90)
        self._ack_all_btn.setStyleSheet(
            f"color:{C_GREEN};border:1px solid {C_GREEN};"
            f"padding:4px 8px;font-size:10px;")
        self._ack_all_btn.clicked.connect(self._on_ack_all)
        bar.addWidget(self._ack_all_btn)

        layout.addLayout(bar)

        # ── Alarm table ───────────────────────────────────────────────────────
        # Columns: SEV | PROCESS | TAG | DESCRIPTION | TIME | ACKED | ACK
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["SEV", "PROCESS", "TAG", "DESCRIPTION", "TIME", "ACKED AT", "ACK"])
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.setColumnWidth(0, 55)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 90)
        self._table.setColumnWidth(6, 50)
        layout.addWidget(self._table)

        # ── Empty message ─────────────────────────────────────────────────────
        self._empty = QLabel(
            "● ALL CLEAR — No active alarms across all processes")
        self._empty.setStyleSheet(
            f"color:{C_MUTED};font-size:12px;letter-spacing:1px;")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        # Store current alarms for ACK operations
        self._current_alarms = []

    def update_data(self, plant: dict):
        alarms = plant.get("alarms", [])
        if not isinstance(alarms, list):
            alarms = []

        self._current_alarms = alarms

        n_total  = len(alarms)
        n_crit   = sum(1 for a in alarms if a.get("sev") == "CRIT")
        n_high   = sum(1 for a in alarms if a.get("sev") == "HIGH")
        n_unacked= sum(1 for a in alarms if not a.get("acked", False))

        self._total_lbl.setText(f"ACTIVE ALARMS: {n_total}")
        self._crit_lbl.setText(f"CRIT: {n_crit}")
        self._high_lbl.setText(f"HIGH: {n_high}")

        unack_color = C_RED if n_unacked > 0 else C_MUTED
        self._unacked_lbl.setText(f"UNACKED: {n_unacked}")
        self._unacked_lbl.setStyleSheet(
            f"color:{unack_color};font-size:11px;font-weight:bold;")

        self._empty.setVisible(n_total == 0)
        self._table.setVisible(n_total > 0)

        self._table.setSortingEnabled(False)
        self._table.setRowCount(n_total)

        for row, a in enumerate(alarms):
            sev    = a.get("sev", "LOW")
            acked  = a.get("acked", False)
            ack_at = a.get("acked_at", "")

            # Acknowledged alarms shown dimmer
            if acked:
                color = QColor(C_MUTED)
            else:
                color = QColor(SEV_COLORS.get(sev, C_MUTED))

            vals = [
                sev,
                a.get("process", "—").replace("_", " ").upper(),
                a.get("tag",     "—"),
                a.get("desc",    "—"),
                a.get("ts",      "—"),
                ack_at if acked else "—",
            ]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(str(text))
                item.setForeground(color)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, col, item)

            # ACK button per row
            if not acked:
                btn = QPushButton("ACK")
                btn.setFixedSize(44, 22)
                btn.setStyleSheet(
                    f"color:{C_GREEN};border:1px solid {C_GREEN};"
                    f"font-size:9px;padding:1px;")
                alarm_id = a.get("id", "")
                btn.clicked.connect(
                    lambda checked, aid=alarm_id: self._on_ack(aid))
                self._table.setCellWidget(row, 6, btn)
            else:
                item = QTableWidgetItem("✓")
                item.setForeground(QColor(C_MUTED))
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, 6, item)

        self._table.setSortingEnabled(True)

    def _on_ack(self, alarm_id: str):
        """Acknowledge single alarm."""
        if self._rest is None:
            return
        self._rest.ack_alarm(
            alarm_id = alarm_id,
            callback = self._on_ack_result,
        )

    def _on_ack_all(self):
        """Acknowledge all active alarms."""
        if self._rest is None:
            return
        self._rest.ack_alarm(
            alarm_id = "all",
            callback = self._on_ack_result,
        )

    def _on_ack_result(self, result: dict):
        if result.get("ok"):
            acked = result.get("acked", [])
            count = len(acked)
            self._unacked_lbl.setText(f"✓ {count} acknowledged")
        else:
            self._unacked_lbl.setText(
                f"ACK failed: {result.get('error', '?')}")
