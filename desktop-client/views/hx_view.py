"""
MORBION — Heat Exchanger View
KenGen Olkaria — Geothermal Heat Recovery — Port 506
"""

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QGroupBox, QSplitter
from PyQt6.QtCore import Qt

from views.base_view           import BaseView
from widgets.value_label       import ValueLabel
from widgets.sparkline_widget  import SparklineWidget
from widgets.valve_bar         import ValveBar
from widgets.status_badge      import StatusBadge
from widgets.control_panel     import ControlPanel


_CONTROL_SPEC = {
    "process": "heat_exchanger",
    "faults": [
        {"name": "Inject OVERTEMP (T_cold=100°C)", "register": 3,  "value": 1000, "danger": True},
        {"name": "Inject PUMP FAULT",               "register": 16, "value": 1,    "danger": True},
        {"name": "Close Cold Valve (0%)",            "register": 15, "value": 0,    "danger": True},
        {"name": "Clear Fault Code",                 "register": 16, "value": 0,    "danger": False},
    ],
    "writes": [
        {"label": "Hot Valve Pos (raw ×10)",  "register": 14, "min": 0, "max": 1000, "default": 800},
        {"label": "Cold Valve Pos (raw ×10)", "register": 15, "min": 0, "max": 1000, "default": 750},
        {"label": "Fault Code (0=clear)",     "register": 16, "min": 0, "max": 3,    "default": 0},
    ],
}


class HXView(BaseView):

    def __init__(self, rest_client, parent=None):
        super().__init__(rest_client, parent)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(splitter)

        left = QVBoxLayout()
        left_w = QGroupBox()
        left_w.setLayout(left)

        self._badge = StatusBadge()
        left.addWidget(self._badge)

        # Temperatures
        t_group = QGroupBox("TEMPERATURES")
        t_layout = QVBoxLayout(t_group)
        self._v_t_hot_in    = ValueLabel("T Hot In",    "°C", warn_threshold=175, crit_threshold=185)
        self._v_t_hot_out   = ValueLabel("T Hot Out",   "°C", warn_threshold=155, crit_threshold=165)
        self._v_t_cold_in   = ValueLabel("T Cold In",   "°C")
        self._v_t_cold_out  = ValueLabel("T Cold Out",  "°C", warn_threshold=85,  crit_threshold=95)
        self._spark_t_hot   = SparklineWidget(color="#ff3333")
        self._spark_t_cold  = SparklineWidget(color="#00d4ff")
        for w in (self._v_t_hot_in, self._v_t_hot_out,
                  self._spark_t_hot, self._v_t_cold_in,
                  self._v_t_cold_out, self._spark_t_cold):
            t_layout.addWidget(w)
        left.addWidget(t_group)

        # Performance
        p_group = QGroupBox("PERFORMANCE")
        p_layout = QVBoxLayout(p_group)
        self._v_eff      = ValueLabel("Efficiency",  "%",  warn_threshold=None, crit_threshold=None)
        self._v_duty     = ValueLabel("Q Duty",      "kW")
        self._spark_eff  = SparklineWidget(color="#00ff88")
        for w in (self._v_eff, self._v_duty, self._spark_eff):
            p_layout.addWidget(w)
        left.addWidget(p_group)

        # Flows & pumps
        f_group = QGroupBox("FLOWS & PUMPS")
        f_layout = QVBoxLayout(f_group)
        self._v_flow_hot  = ValueLabel("Hot Flow",    "L/min")
        self._v_flow_cold = ValueLabel("Cold Flow",   "L/min")
        self._v_pump_hot  = ValueLabel("Hot Pump",    "RPM")
        self._v_pump_cold = ValueLabel("Cold Pump",   "RPM")
        for w in (self._v_flow_hot, self._v_flow_cold, self._v_pump_hot, self._v_pump_cold):
            f_layout.addWidget(w)
        left.addWidget(f_group)

        # Pressures & valves
        pv_group = QGroupBox("PRESSURES & VALVES")
        pv_layout = QVBoxLayout(pv_group)
        self._v_p_hot_in   = ValueLabel("Hot P In",   "bar")
        self._v_p_hot_out  = ValueLabel("Hot P Out",  "bar")
        self._v_p_cold_in  = ValueLabel("Cold P In",  "bar")
        self._v_p_cold_out = ValueLabel("Cold P Out", "bar")
        self._vb_hot       = ValveBar("Hot Valve")
        self._vb_cold      = ValveBar("Cold Valve")
        self._v_fault      = ValueLabel("Fault",      "")
        for w in (self._v_p_hot_in, self._v_p_hot_out,
                  self._v_p_cold_in, self._v_p_cold_out,
                  self._vb_hot, self._vb_cold, self._v_fault):
            pv_layout.addWidget(w)
        left.addWidget(pv_group)
        left.addStretch()
        splitter.addWidget(left_w)

        ctrl_group = QGroupBox("OPERATOR CONTROL")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.addWidget(ControlPanel(_CONTROL_SPEC, rest_client))
        splitter.addWidget(ctrl_group)
        splitter.setSizes([700, 300])

    def update_data(self, data: dict):
        if not data.get("online"):
            self._badge.set_offline()
            return
        self._badge.update_process(data)
        self._v_t_hot_in.set_value(data.get("T_hot_in_C"), 1)
        self._v_t_hot_out.set_value(data.get("T_hot_out_C"), 1)
        self._v_t_cold_in.set_value(data.get("T_cold_in_C"), 1)
        self._v_t_cold_out.set_value(data.get("T_cold_out_C"), 1)
        self._spark_t_hot.push(data.get("T_hot_out_C", 0))
        self._spark_t_cold.push(data.get("T_cold_out_C", 0))
        self._v_eff.set_value(data.get("efficiency_pct"), 1)
        self._v_duty.set_value(data.get("Q_duty_kW"), 0)
        self._spark_eff.push(data.get("efficiency_pct", 0))
        self._v_flow_hot.set_value(data.get("flow_hot_lpm"), 1)
        self._v_flow_cold.set_value(data.get("flow_cold_lpm"), 1)
        self._v_pump_hot.set_value(data.get("hot_pump_speed_rpm"), 0)
        self._v_pump_cold.set_value(data.get("cold_pump_speed_rpm"), 0)
        self._v_p_hot_in.set_value(data.get("pressure_hot_in_bar"), 2)
        self._v_p_hot_out.set_value(data.get("pressure_hot_out_bar"), 2)
        self._v_p_cold_in.set_value(data.get("pressure_cold_in_bar"), 2)
        self._v_p_cold_out.set_value(data.get("pressure_cold_out_bar"), 2)
        self._vb_hot.set_value(data.get("hot_valve_pos_pct", 0))
        self._vb_cold.set_value(data.get("cold_valve_pos_pct", 0))
        self._v_fault.set_value(f"{data.get('fault_code',0)} — {data.get('fault_text','OK')}")