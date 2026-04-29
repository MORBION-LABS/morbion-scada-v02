"""
MORBION — Pumping Station View
Nairobi Water — Municipal Pumping Station — Port 502
"""

from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt

from views.base_view      import BaseProcessView
from widgets.value_label  import ValueLabel
from widgets.tank_widget  import TankWidget
from widgets.sparkline_widget import SparklineWidget
from widgets.valve_bar    import ValveBar
from widgets.status_badge import StatusBadge
from widgets.control_panel import ControlPanel
from theme import C_ACCENT


_CONTROL_SPEC = {
    "process": "pumping_station",
    "label":   "PUMPING STATION — NAIROBI WATER",
    "faults": [
        {"name": "Inject HIGH LEVEL (92%)",  "register": 0,  "value": 920, "danger": True},
        {"name": "Inject LOW LEVEL (8%)",    "register": 0,  "value": 80,  "danger": True},
        {"name": "Stop Pump (force)",         "register": 7,  "value": 0,   "danger": True},
        {"name": "Clear Fault Code",          "register": 14, "value": 0,   "danger": False},
    ],
    "writes": [
        {"label": "Tank Level (raw ×10)",     "register": 0,  "min": 0, "max": 1000, "default": 500},
        {"label": "Pump Running (0/1)",        "register": 7,  "min": 0, "max": 1,    "default": 1},
        {"label": "Outlet Valve (raw ×10)",    "register": 9,  "min": 0, "max": 1000, "default": 850},
        {"label": "Fault Code (0=clear)",      "register": 14, "min": 0, "max": 4,    "default": 0},
    ],
}


class PumpingView(BaseView):

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(splitter)

        # ── LEFT: process display ─────────────────────────────────────────────
        left = QSplitter(Qt.Orientation.Vertical)

        # Tank + pump status row
        top_row_w = QGroupBox()
        top_row_w.setTitle("STORAGE TANK & PUMP")
        top_layout = QHBoxLayout(top_row_w)

        self._tank = TankWidget(0, 100, warn_pct=80, crit_pct=90)
        self._tank.setFixedWidth(80)
        top_layout.addWidget(self._tank)

        tank_vals = QVBoxLayout()
        self._badge       = StatusBadge()
        self._pump_badge  = StatusBadge()
        self._v_level     = ValueLabel("Tank Level",   "%",   warn_threshold=80, crit_threshold=90)
        self._v_volume    = ValueLabel("Tank Volume",  "m³")
        self._v_speed     = ValueLabel("Pump Speed",   "RPM")
        self._v_flow      = ValueLabel("Pump Flow",    "m³/hr")
        self._v_current   = ValueLabel("Pump Current", "A",   warn_threshold=12, crit_threshold=15)
        self._v_power     = ValueLabel("Pump Power",   "kW")
        self._v_starts    = ValueLabel("Starts Today", "")
        self._spark_flow  = SparklineWidget(color="#00ff88")

        for w in (self._badge, self._pump_badge, self._v_level, self._v_volume,
                  self._v_speed, self._v_flow, self._v_current,
                  self._v_power, self._v_starts, self._spark_flow):
            tank_vals.addWidget(w)
        tank_vals.addStretch()
        top_layout.addLayout(tank_vals)
        left.addWidget(top_row_w)

        # Pressures + valves
        pv_group = QGroupBox("PRESSURES & VALVES")
        pv_layout = QVBoxLayout(pv_group)
        self._v_pressure  = ValueLabel("Discharge P",  "bar",  warn_threshold=7, crit_threshold=8)
        self._spark_press = SparklineWidget(color="#ffcc00")
        self._vb_inlet    = ValveBar("Inlet Valve")
        self._vb_outlet   = ValveBar("Outlet Valve")
        self._v_demand    = ValueLabel("Demand Flow",  "m³/hr")
        self._v_net       = ValueLabel("Net Flow",     "m³/hr")
        self._v_fault     = ValueLabel("Fault Code",   "")
        for w in (self._v_pressure, self._spark_press,
                  self._vb_inlet, self._vb_outlet,
                  self._v_demand, self._v_net, self._v_fault):
            pv_layout.addWidget(w)
        pv_layout.addStretch()
        left.addWidget(pv_group)
        splitter.addWidget(left)

        # ── RIGHT: control panel ──────────────────────────────────────────────
        ctrl_group = QGroupBox("OPERATOR CONTROL")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.addWidget(ControlPanel(_CONTROL_SPEC, rest_client))
        splitter.addWidget(ctrl_group)

        splitter.setSizes([700, 300])

    def update_data(self, data: dict):
        if not data.get("online"):
            self._badge.set_offline()
            self._pump_badge.set_offline()
            return

        self._badge.update_process(data)

        running = data.get("pump_running", False)
        if running:
            self._pump_badge.set_running()
        else:
            self._pump_badge.set_stopped()

        lvl = data.get("tank_level_pct", 0)
        self._tank.set_value(lvl, f"{lvl:.1f}%")

        self._v_level.set_value(data.get("tank_level_pct"), 1)
        self._v_volume.set_value(data.get("tank_volume_m3"), 1)
        self._v_speed.set_value(data.get("pump_speed_rpm"), 0)
        self._v_flow.set_value(data.get("pump_flow_m3hr"), 1)
        self._v_current.set_value(data.get("pump_current_A"), 1)
        self._v_power.set_value(data.get("pump_power_kW"), 1)
        self._v_starts.set_value(data.get("pump_starts_today"), 0)
        self._v_pressure.set_value(data.get("discharge_pressure_bar"), 2)
        self._v_demand.set_value(data.get("demand_flow_m3hr"), 1)
        self._v_net.set_value(data.get("net_flow_m3hr"), 1)
        self._v_fault.set_value(
            f"{data.get('fault_code',0)} — {data.get('fault_text','OK')}")

        self._spark_flow.push(data.get("pump_flow_m3hr", 0))
        self._spark_press.push(data.get("discharge_pressure_bar", 0))

        self._vb_inlet.set_value(data.get("inlet_valve_pos_pct", 0))
        self._vb_outlet.set_value(data.get("outlet_valve_pos_pct", 0))
