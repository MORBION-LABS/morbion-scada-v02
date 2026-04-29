"""
trends_view.py — MORBION SCADA Trends View
MORBION SCADA v02 — NEW

Real-time trend display for key process variables.
Uses SparklineWidget for live trends.
Organized by process. Updates every WebSocket push.
No pyqtgraph dependency — uses existing SparklineWidget.
"""

"""
trends_view.py — Multi-process trend sparklines
MORBION SCADA v02
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QGroupBox,
)
import theme
from widgets.sparkline_widget import SparklineWidget


class TrendsView(QWidget):

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        title = QLabel("PROCESS TRENDS")
        title.setStyleSheet(theme.STYLE_HEADER)
        root.addWidget(title)

        sub = QLabel("120-point rolling history  —  updates every poll cycle")
        sub.setStyleSheet(theme.STYLE_DIM)
        root.addWidget(sub)

        # ── Pumping Station ───────────────────────────────────────
        ps_box = QGroupBox("PUMPING STATION")
        ps_layout = QVBoxLayout(ps_box)
        self._ps_level = SparklineWidget(
            "Tank Level", "%", hi_alarm=90, lo_alarm=10)
        self._ps_flow  = SparklineWidget(
            "Pump Flow", "m³/hr")
        self._ps_press = SparklineWidget(
            "Discharge Pressure", "bar", hi_alarm=8.0)
        ps_layout.addWidget(self._ps_level)
        ps_layout.addWidget(self._ps_flow)
        ps_layout.addWidget(self._ps_press)
        root.addWidget(ps_box)

        # ── Heat Exchanger ────────────────────────────────────────
        hx_box = QGroupBox("HEAT EXCHANGER")
        hx_layout = QVBoxLayout(hx_box)
        self._hx_eff    = SparklineWidget(
            "Efficiency", "%", lo_alarm=45)
        self._hx_t_cold = SparklineWidget(
            "T Cold Out", "°C", hi_alarm=95)
        self._hx_q      = SparklineWidget(
            "Heat Duty", "kW")
        hx_layout.addWidget(self._hx_eff)
        hx_layout.addWidget(self._hx_t_cold)
        hx_layout.addWidget(self._hx_q)
        root.addWidget(hx_box)

        # ── Boiler ────────────────────────────────────────────────
        bl_box = QGroupBox("BOILER")
        bl_layout = QVBoxLayout(bl_box)
        self._bl_press = SparklineWidget(
            "Drum Pressure", "bar", hi_alarm=10, lo_alarm=6)
        self._bl_level = SparklineWidget(
            "Drum Level", "%", hi_alarm=80, lo_alarm=20)
        self._bl_steam = SparklineWidget(
            "Steam Flow", "kg/hr")
        bl_layout.addWidget(self._bl_press)
        bl_layout.addWidget(self._bl_level)
        bl_layout.addWidget(self._bl_steam)
        root.addWidget(bl_box)

        # ── Pipeline ──────────────────────────────────────────────
        pl_box = QGroupBox("PIPELINE")
        pl_layout = QVBoxLayout(pl_box)
        self._pl_outlet = SparklineWidget(
            "Outlet Pressure", "bar", hi_alarm=55, lo_alarm=30)
        self._pl_flow   = SparklineWidget(
            "Flow Rate", "m³/hr", lo_alarm=200)
        pl_layout.addWidget(self._pl_outlet)
        pl_layout.addWidget(self._pl_flow)
        root.addWidget(pl_box)

        root.addStretch()
        scroll.setWidget(container)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def update_data(self, data: dict):
        ps = data.get("pumping_station", {})
        hx = data.get("heat_exchanger",  {})
        bl = data.get("boiler",          {})
        pl = data.get("pipeline",        {})

        if ps.get("online"):
            self._ps_level.push(ps.get("tank_level_pct",        0))
            self._ps_flow.push(ps.get("pump_flow_m3hr",          0))
            self._ps_press.push(ps.get("discharge_pressure_bar", 0))

        if hx.get("online"):
            self._hx_eff.push(hx.get("efficiency_pct",   0))
            self._hx_t_cold.push(hx.get("T_cold_out_C",  0))
            self._hx_q.push(hx.get("Q_duty_kW",          0))

        if bl.get("online"):
            self._bl_press.push(bl.get("drum_pressure_bar", 0))
            self._bl_level.push(bl.get("drum_level_pct",    0))
            self._bl_steam.push(bl.get("steam_flow_kghr",   0))

        if pl.get("online"):
            self._pl_outlet.push(pl.get("outlet_pressure_bar", 0))
            self._pl_flow.push(pl.get("flow_rate_m3hr",        0))
