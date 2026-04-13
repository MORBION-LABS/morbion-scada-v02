"""
MORBION — Overview View
Plant-level summary. All 4 processes. Active alarms.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui  import QColor

from widgets.status_badge import StatusBadge, SeverityBadge
from views.base_view      import BaseView
from theme import C_ACCENT, C_TEXT2, C_MUTED, C_RED, C_GREEN, C_YELLOW, SEV_COLORS


class ProcessCard(QGroupBox):
    """Mini summary card for one process."""

    _METRICS = {
        "pumping_station": [
            ("Tank Level",   "tank_level_pct",       "%",   1),
            ("Pump Flow",    "pump_flow_m3hr",        "m³/hr", 1),
            ("Discharge P",  "discharge_pressure_bar","bar", 2),
        ],
        "heat_exchanger": [
            ("T Hot In",    "T_hot_in_C",    "°C", 1),
            ("T Cold Out",  "T_cold_out_C",  "°C", 1),
            ("Efficiency",  "efficiency_pct","%",  1),
        ],
        "boiler": [
            ("Drum Press",  "drum_pressure_bar", "bar", 2),
            ("Drum Level",  "drum_level_pct",    "%",   1),
            ("Steam Flow",  "steam_flow_kghr",   "kg/hr", 0),
        ],
        "pipeline": [
            ("Outlet P",    "outlet_pressure_bar","bar",  2),
            ("Flow Rate",   "flow_rate_m3hr",    "m³/hr", 1),
            ("Duty Pump",   "duty_pump_running", "",      0),
        ],
    }

    def __init__(self, process_key: str, label: str, location: str, parent=None):
        super().__init__(label)
        self._key      = process_key
        self._rows     = []
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._badge = StatusBadge()
        layout.addWidget(self._badge)

        self._loc = QLabel(location)
        self._loc.setStyleSheet(f"color:{C_MUTED};font-size:9px;")
        layout.addWidget(self._loc)

        for (display, key, unit, dec) in self._METRICS.get(process_key, []):
            row = QHBoxLayout()
            lbl = QLabel(display)
            lbl.setStyleSheet(f"color:{C_TEXT2};font-size:9px;")
            val = QLabel("—")
            val.setStyleSheet(f"color:{C_ACCENT};font-size:11px;font-weight:bold;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            u = QLabel(unit)
            u.setStyleSheet(f"color:{C_MUTED};font-size:9px;")
            u.setFixedWidth(36)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            row.addWidget(u)
            layout.addLayout(row)
            self._rows.append((key, val, dec))

        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def update_data(self, data: dict):
        self._badge.update_process(data)
        for (key, val_lbl, dec) in self._rows:
            v = data.get(key)
            if v is None:
                val_lbl.setText("—")
            elif isinstance(v, bool):
                val_lbl.setText("RUN" if v else "STOP")
                val_lbl.setStyleSheet(
                    f"color:{C_GREEN if v else C_MUTED};font-size:11px;font-weight:bold;")
            elif isinstance(v, float):
                val_lbl.setText(f"{v:.{dec}f}")
            else:
                val_lbl.setText(str(v))


class OverviewView(BaseView):

    _PROCS = [
        ("pumping_station", "PUMPING STATION",  "Nairobi Water — Municipal"),
        ("heat_exchanger",  "HEAT EXCHANGER",   "KenGen Olkaria — Geothermal"),
        ("boiler",          "BOILER",            "EABL/Bidco — Industrial Steam"),
        ("pipeline",        "PIPELINE",          "Kenya Pipeline Co. — Petroleum"),
    ]

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)
        self._cards = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Process cards grid
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (key, label, loc) in enumerate(self._PROCS):
            card = ProcessCard(key, label, loc)
            self._cards[key] = card
            grid.addWidget(card, 0, i)
        layout.addLayout(grid)

        # Alarms table
        alarm_group = QGroupBox("ACTIVE ALARMS — ALL PROCESSES")
        alarm_layout = QVBoxLayout(alarm_group)
        self._alarm_table = QTableWidget(0, 5)
        self._alarm_table.setHorizontalHeaderLabels(["SEV", "PROCESS", "TAG", "DESCRIPTION", "TIME"])
        self._alarm_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._alarm_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._alarm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._alarm_table.verticalHeader().setVisible(False)
        self._alarm_table.setAlternatingRowColors(False)
        self._alarm_table.setColumnWidth(0, 60)
        self._alarm_table.setColumnWidth(1, 140)
        self._alarm_table.setColumnWidth(2, 130)
        self._alarm_table.setColumnWidth(4, 70)
        alarm_layout.addWidget(self._alarm_table)
        layout.addWidget(alarm_group, 1)

    def update_data(self, plant: dict):
        for key, card in self._cards.items():
            card.update_data(plant.get(key, {"online": False}))
        self._update_alarms(plant.get("alarms", []))

    def _update_alarms(self, alarms: list):
        self._alarm_table.setRowCount(len(alarms))
        for row, a in enumerate(alarms):
            sev   = a.get("sev", "LOW")
            color = QColor(SEV_COLORS.get(sev, C_MUTED))

            items = [
                sev,
                a.get("process", "—").replace("_", " ").upper(),
                a.get("tag", "—"),
                a.get("desc", "—"),
                a.get("ts", "—"),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(color)
                self._alarm_table.setItem(row, col, item)