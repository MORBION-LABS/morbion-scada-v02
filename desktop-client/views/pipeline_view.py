"""
MORBION — Pipeline View
Kenya Pipeline Company — Petroleum Transfer — Port 508
"""

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QGroupBox, QSplitter
from PyQt6.QtCore    import Qt

from views.base_view           import BaseView
from widgets.value_label       import ValueLabel
from widgets.sparkline_widget  import SparklineWidget
from widgets.valve_bar         import ValveBar
from widgets.status_badge      import StatusBadge
from widgets.control_panel     import ControlPanel
from theme import C_RED, C_GREEN


_CONTROL_SPEC = {
    "process": "pipeline",
    "faults": [
        {"name": "Inject DUTY FAULT",              "register": 14, "value": 1,    "danger": True},
        {"name": "Inject OVERPRESSURE (56 bar)",   "register": 1,  "value": 5600, "danger": True},
        {"name": "Inject FLOW DROP (50 m³/hr)",    "register": 2,  "value": 500,  "danger": True},
        {"name": "Clear Fault Code",               "register": 14, "value": 0,    "danger": False},
    ],
    "writes": [
        {"label": "Outlet Pressure (raw ×100)", "register": 1,  "min": 0, "max": 9999, "default": 4000},
        {"label": "Flow Rate (raw ×10)",        "register": 2,  "min": 0, "max": 9999, "default": 4500},
        {"label": "Duty Pump Running (0/1)",    "register": 5,  "min": 0, "max": 1,    "default": 1},
        {"label": "Outlet Valve (raw ×10)",     "register": 9,  "min": 0, "max": 1000, "default": 850},
        {"label": "Fault Code (0=clear)",       "register": 14, "min": 0, "max": 3,    "default": 0},
    ],
}


class PipelineView(BaseView):

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

        # Pressures & flow
        pf_group = QGroupBox("PRESSURES & FLOW")
        pf_layout = QVBoxLayout(pf_group)
        self._v_inlet    = ValueLabel("Inlet Pressure",  "bar", warn_threshold=None, crit_threshold=None, high_is_bad=False)
        self._v_outlet   = ValueLabel("Outlet Pressure", "bar", warn_threshold=50,   crit_threshold=55)
        self._v_diff     = ValueLabel("Differential",    "bar")
        self._v_flow     = ValueLabel("Flow Rate",       "m³/hr", warn_threshold=None, crit_threshold=None, high_is_bad=False)
        self._v_velocity = ValueLabel("Flow Velocity",   "m/s")
        self._spark_out  = SparklineWidget(color="#00ff88")
        self._spark_flow = SparklineWidget(color="#ffcc00")
        for w in (self._v_inlet, self._v_outlet, self._v_diff,
                  self._spark_out, self._v_flow, self._v_velocity, self._spark_flow):
            pf_layout.addWidget(w)
        left.addWidget(pf_group)

        # Duty pump
        dp_group = QGroupBox("DUTY PUMP")
        dp_layout = QVBoxLayout(dp_group)
        self._duty_badge   = StatusBadge()
        self._v_duty_speed = ValueLabel("Speed",   "RPM")
        self._v_duty_curr  = ValueLabel("Current", "A")
        self._v_duty_power = ValueLabel("Power",   "kW")
        for w in (self._duty_badge, self._v_duty_speed, self._v_duty_curr, self._v_duty_power):
            dp_layout.addWidget(w)
        left.addWidget(dp_group)

        # Standby pump + valves + leak
        sv_group = QGroupBox("STANDBY PUMP & VALVES")
        sv_layout = QVBoxLayout(sv_group)
        self._standby_badge   = StatusBadge()
        self._v_standby_speed = ValueLabel("Standby Speed", "RPM")
        self._vb_inlet        = ValveBar("Inlet Valve")
        self._vb_outlet       = ValveBar("Outlet Valve")
        self._v_leak          = ValueLabel("Leak Flag",  "")
        self._v_fault         = ValueLabel("Fault",      "")
        for w in (self._standby_badge, self._v_standby_speed,
                  self._vb_inlet, self._vb_outlet, self._v_leak, self._v_fault):
            sv_layout.addWidget(w)
        left.addWidget(sv_group)
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
            self._duty_badge.set_offline()
            self._standby_badge.set_offline()
            return

        self._badge.update_process(data)

        self._v_inlet.set_value(data.get("inlet_pressure_bar"), 2)
        self._v_outlet.set_value(data.get("outlet_pressure_bar"), 2)
        self._v_diff.set_value(data.get("pump_differential_bar"), 2)
        self._v_flow.set_value(data.get("flow_rate_m3hr"), 1)
        self._v_velocity.set_value(data.get("flow_velocity_ms"), 2)
        self._spark_out.push(data.get("outlet_pressure_bar", 0))
        self._spark_flow.push(data.get("flow_rate_m3hr", 0))

        if data.get("duty_pump_running"):
            self._duty_badge.set_running()
        else:
            self._duty_badge.set_stopped()
        self._v_duty_speed.set_value(data.get("duty_pump_speed_rpm"), 0)
        self._v_duty_curr.set_value(data.get("duty_pump_current_A"), 1)
        self._v_duty_power.set_value(data.get("duty_pump_power_kW"), 0)

        if data.get("standby_pump_running"):
            self._standby_badge.set_running()
        else:
            self._standby_badge.set_standby()
        self._v_standby_speed.set_value(data.get("standby_pump_speed_rpm"), 0)

        self._vb_inlet.set_value(data.get("inlet_valve_pos_pct", 0))
        self._vb_outlet.set_value(data.get("outlet_valve_pos_pct", 0))

        leak = data.get("leak_flag", False)
        self._v_leak.set_value("⚠ SUSPECTED" if leak else "● CLEAR")

        self._v_fault.set_value(f"{data.get('fault_code',0)} — {data.get('fault_text','OK')}")