"""
overview_view.py — 4-process overview dashboard
MORBION SCADA v02
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt
import theme
from widgets.status_badge  import StatusBadge
from widgets.gauge_widget  import GaugeWidget
from widgets.value_label   import ValueLabel


class _ProcessCard(QGroupBox):

    def __init__(self, title: str, location: str):
        super().__init__(title)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 12, 8, 8)
        self._layout.setSpacing(6)

        self._badge = StatusBadge()
        loc = QLabel(location)
        loc.setStyleSheet(theme.STYLE_DIM)
        self._layout.addWidget(self._badge)
        self._layout.addWidget(loc)
        self._layout.addSpacing(4)

    def add_gauge(self, gauge: GaugeWidget):
        self._layout.addWidget(gauge)

    def add_value(self, val: ValueLabel):
        self._layout.addWidget(val)

    def set_online(self, online: bool, fault: int = 0, fault_text: str = ""):
        if not online:
            self._badge.set_offline()
        elif fault > 0:
            self._badge.set_fault(fault, fault_text)
        else:
            self._badge.set_online()


class OverviewView(QWidget):

    def __init__(self, rest):
        super().__init__()
        self._rest = rest
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Title
        title = QLabel("PLANT OVERVIEW")
        title.setStyleSheet(theme.STYLE_HEADER)
        root.addWidget(title)

        sub = QLabel("MORBION SCADA v02  —  Intelligence. Precision. Vigilance.")
        sub.setStyleSheet(theme.STYLE_DIM)
        root.addWidget(sub)

        # 2x2 grid of process cards
        grid = QGridLayout()
        grid.setSpacing(12)

        # ── Pumping Station ───────────────────────────────────────
        self._ps_card = _ProcessCard(
            "PUMPING STATION", "Nairobi Water — Municipal")
        self._ps_level = GaugeWidget(
            "Tank Level", "%", 0, 100, hi_alarm=90, lo_alarm=10)
        self._ps_flow  = GaugeWidget(
            "Pump Flow", "m³/hr", 0, 150)
        self._ps_press = ValueLabel(
            "Discharge Pressure", "bar", hi_alarm=8.0)
        self._ps_card.add_gauge(self._ps_level)
        self._ps_card.add_gauge(self._ps_flow)
        self._ps_card.add_value(self._ps_press)
        grid.addWidget(self._ps_card, 0, 0)

        # ── Heat Exchanger ────────────────────────────────────────
        self._hx_card = _ProcessCard(
            "HEAT EXCHANGER", "KenGen Olkaria — Geothermal")
        self._hx_eff   = GaugeWidget(
            "Efficiency", "%", 0, 100, lo_alarm=45)
        self._hx_t_hot = ValueLabel(
            "T Hot In", "°C", hi_alarm=200)
        self._hx_t_cold= ValueLabel(
            "T Cold Out", "°C", hi_alarm=95)
        self._hx_card.add_gauge(self._hx_eff)
        self._hx_card.add_value(self._hx_t_hot)
        self._hx_card.add_value(self._hx_t_cold)
        grid.addWidget(self._hx_card, 0, 1)

        # ── Boiler ────────────────────────────────────────────────
        self._bl_card  = _ProcessCard(
            "BOILER", "EABL/Bidco — Industrial Steam")
        self._bl_press = GaugeWidget(
            "Drum Pressure", "bar", 0, 12, hi_alarm=10, lo_alarm=6)
        self._bl_level = GaugeWidget(
            "Drum Level", "%", 0, 100, hi_alarm=80, lo_alarm=20)
        self._bl_steam = ValueLabel(
            "Steam Flow", "kg/hr")
        self._bl_card.add_gauge(self._bl_press)
        self._bl_card.add_gauge(self._bl_level)
        self._bl_card.add_value(self._bl_steam)
        grid.addWidget(self._bl_card, 1, 0)

        # ── Pipeline ──────────────────────────────────────────────
        self._pl_card  = _ProcessCard(
            "PIPELINE", "Kenya Pipeline Co. — Petroleum")
        self._pl_out   = GaugeWidget(
            "Outlet Pressure", "bar", 0, 60, hi_alarm=55, lo_alarm=30)
        self._pl_flow  = GaugeWidget(
            "Flow Rate", "m³/hr", 0, 600)
        self._pl_leak  = ValueLabel("Leak Flag", "")
        self._pl_card.add_gauge(self._pl_out)
        self._pl_card.add_gauge(self._pl_flow)
        self._pl_card.add_value(self._pl_leak)
        grid.addWidget(self._pl_card, 1, 1)

        root.addLayout(grid)
        root.addStretch()

    def update_data(self, data: dict):
        ps = data.get("pumping_station", {})
        hx = data.get("heat_exchanger",  {})
        bl = data.get("boiler",          {})
        pl = data.get("pipeline",        {})

        # Pumping station
        self._ps_card.set_online(
            ps.get("online", False),
            ps.get("fault_code", 0),
            ps.get("fault_text", ""),
        )
        self._ps_level.set_value(ps.get("tank_level_pct", 0))
        self._ps_flow.set_value(ps.get("pump_flow_m3hr", 0))
        self._ps_press.set_value(ps.get("discharge_pressure_bar", 0))

        # Heat exchanger
        self._hx_card.set_online(
            hx.get("online", False),
            hx.get("fault_code", 0),
            hx.get("fault_text", ""),
        )
        self._hx_eff.set_value(hx.get("efficiency_pct", 0))
        self._hx_t_hot.set_value(hx.get("T_hot_in_C", 0))
        self._hx_t_cold.set_value(hx.get("T_cold_out_C", 0))

        # Boiler
        self._bl_card.set_online(
            bl.get("online", False),
            bl.get("fault_code", 0),
            bl.get("fault_text", ""),
        )
        self._bl_press.set_value(bl.get("drum_pressure_bar", 0))
        self._bl_level.set_value(bl.get("drum_level_pct", 0))
        self._bl_steam.set_value(bl.get("steam_flow_kghr", 0))

        # Pipeline
        self._pl_card.set_online(
            pl.get("online", False),
            pl.get("fault_code", 0),
            pl.get("fault_text", ""),
        )
        self._pl_out.set_value(pl.get("outlet_pressure_bar", 0))
        self._pl_flow.set_value(pl.get("flow_rate_m3hr", 0))
        leak = pl.get("leak_flag", False)
        self._pl_leak.set_value(
            "LEAK SUSPECTED" if leak else "OK",
            override_color=theme.RED if leak else theme.GREEN,
        )
