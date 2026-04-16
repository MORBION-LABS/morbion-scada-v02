"""
trends_view.py — MORBION SCADA Trends View
MORBION SCADA v02 — NEW

Real-time trend display for key process variables.
Uses SparklineWidget for live trends.
Organized by process. Updates every WebSocket push.
No pyqtgraph dependency — uses existing SparklineWidget.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QScrollArea, QWidget, QLabel
)
from PyQt6.QtCore import Qt

from views.base_view          import BaseView
from widgets.sparkline_widget import SparklineWidget
from widgets.value_label      import ValueLabel
from theme import C_TEXT2, C_ACCENT, C_MUTED


# ── Trend definitions per process ─────────────────────────────────────────────
# (display_label, data_key, unit, color, warn, crit)

_PUMP_TRENDS = [
    ("Tank Level",          "tank_level_pct",       "%",     "#00d4ff", 80,   90),
    ("Pump Flow",           "pump_flow_m3hr",        "m³/hr", "#00ff88", None, None),
    ("Discharge Pressure",  "discharge_pressure_bar","bar",   "#ffcc00", 7,    8),
    ("Pump Current",        "pump_current_A",        "A",     "#ff8800", 12,   15),
]

_HX_TRENDS = [
    ("T Hot In",            "T_hot_in_C",            "°C",    "#ff3333", 175, 185),
    ("T Hot Out",           "T_hot_out_C",           "°C",    "#ff8800", 155, 165),
    ("T Cold In",           "T_cold_in_C",           "°C",    "#00d4ff", None, None),
    ("T Cold Out",          "T_cold_out_C",           "°C",   "#00ff88", 85,   95),
    ("Efficiency",          "efficiency_pct",         "%",    "#ffcc00", None, None),
    ("Q Duty",              "Q_duty_kW",              "kW",   "#aa44ff", None, None),
]

_BOILER_TRENDS = [
    ("Drum Pressure",       "drum_pressure_bar",     "bar",   "#ff8800", 9,   10),
    ("Drum Level",          "drum_level_pct",        "%",     "#00d4ff", None, None),
    ("Steam Flow",          "steam_flow_kghr",       "kg/hr", "#00ff88", None, None),
    ("Flue Gas Temp",       "flue_gas_temp_C",       "°C",    "#ff3333", None, None),
    ("Q Burner",            "Q_burner_kW",           "kW",    "#ffcc00", None, None),
]

_PIPELINE_TRENDS = [
    ("Outlet Pressure",     "outlet_pressure_bar",   "bar",   "#ff8800", 50,   55),
    ("Inlet Pressure",      "inlet_pressure_bar",    "bar",   "#00d4ff", None, None),
    ("Flow Rate",           "flow_rate_m3hr",        "m³/hr", "#00ff88", None, None),
    ("Flow Velocity",       "flow_velocity_ms",      "m/s",   "#ffcc00", None, None),
    ("Pump Differential",   "pump_differential_bar", "bar",   "#aa44ff", None, None),
]


class _TrendRow(QWidget):
    """One trend row: label + current value + sparkline."""

    def __init__(self, label: str, unit: str,
                 color: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color:{C_TEXT2};font-size:9px;"
            f"letter-spacing:1px;")
        lbl.setFixedWidth(150)
        layout.addWidget(lbl)

        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color:{C_ACCENT};font-size:11px;"
            f"font-weight:bold;")
        self._val.setFixedWidth(70)
        self._val.setAlignment(
            Qt.AlignmentFlag.AlignRight |
            Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._val)

        u = QLabel(unit)
        u.setStyleSheet(
            f"color:{C_MUTED};font-size:9px;")
        u.setFixedWidth(40)
        layout.addWidget(u)

        self._spark = SparklineWidget(
            max_points=120, color=color)
        layout.addWidget(self._spark, 1)

    def push(self, value):
        if value is None:
            return
        self._val.setText(f"{float(value):.1f}")
        self._spark.push(float(value))


class _ProcessTrendGroup(QGroupBox):
    """Trend group for one process."""

    def __init__(self, title: str,
                 trend_defs: list, parent=None):
        super().__init__(title)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 12, 8, 8)

        self._rows = {}
        for label, key, unit, color, warn, crit in trend_defs:
            row = _TrendRow(label, unit, color)
            self._rows[key] = row
            layout.addWidget(row)

    def update_data(self, data: dict):
        if not data.get("online"):
            return
        for key, row in self._rows.items():
            val = data.get(key)
            if val is not None:
                row.push(val)


class TrendsView(BaseView):

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Scroll area — all trends may exceed window height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Header
        header = QLabel(
            "REAL-TIME TRENDS  ·  120 second rolling window  ·  "
            "1 second resolution")
        header.setStyleSheet(
            f"color:{C_MUTED};font-size:9px;letter-spacing:1px;")
        content_layout.addWidget(header)

        # Process groups
        self._pump_group = _ProcessTrendGroup(
            "PUMPING STATION — NAIROBI WATER",
            _PUMP_TRENDS)
        self._hx_group = _ProcessTrendGroup(
            "HEAT EXCHANGER — KENGEN OLKARIA",
            _HX_TRENDS)
        self._boiler_group = _ProcessTrendGroup(
            "BOILER — EABL/BIDCO",
            _BOILER_TRENDS)
        self._pipeline_group = _ProcessTrendGroup(
            "PIPELINE — KENYA PIPELINE CO.",
            _PIPELINE_TRENDS)

        content_layout.addWidget(self._pump_group)
        content_layout.addWidget(self._hx_group)
        content_layout.addWidget(self._boiler_group)
        content_layout.addWidget(self._pipeline_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    def update_data(self, plant: dict):
        """Called every WebSocket push — updates all sparklines."""
        self._pump_group.update_data(
            plant.get("pumping_station", {}))
        self._hx_group.update_data(
            plant.get("heat_exchanger",  {}))
        self._boiler_group.update_data(
            plant.get("boiler",          {}))
        self._pipeline_group.update_data(
            plant.get("pipeline",        {}))
