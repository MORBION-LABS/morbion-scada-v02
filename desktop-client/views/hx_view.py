from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt
import threading
import theme
from views.base_view          import BaseProcessView
from widgets.status_badge     import StatusBadge
from widgets.gauge_widget     import GaugeWidget
from widgets.valve_bar        import ValveBar
from widgets.value_label      import ValueLabel
from widgets.sparkline_widget import SparklineWidget
from widgets.control_panel    import RegisterWriteRow, FaultClearButton, ControlButton


class HXView(BaseProcessView):

    def __init__(self, rest, config):
        self._rest   = rest
        self._config = config
        super().__init__()

    def _build_data_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        row = QHBoxLayout()
        title = QLabel("HEAT EXCHANGER")
        title.setStyleSheet(theme.STYLE_HEADER)
        row.addWidget(title)
        row.addStretch()
        self._badge = StatusBadge()
        row.addWidget(self._badge)
        layout.addLayout(row)

        loc = QLabel("KenGen Olkaria — Geothermal Heat Recovery  |  Port 506")
        loc.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(loc)

        temp_box = QGroupBox("TEMPERATURES")
        temp_layout = QHBoxLayout(temp_box)
        self._t_hot_in   = ValueLabel("T Hot In",   "°C", hi_alarm=200)
        self._t_hot_out  = ValueLabel("T Hot Out",  "°C", hi_alarm=165)
        self._t_cold_in  = ValueLabel("T Cold In",  "°C")
        self._t_cold_out = ValueLabel("T Cold Out", "°C", hi_alarm=95)
        for w in [self._t_hot_in, self._t_hot_out, self._t_cold_in, self._t_cold_out]:
            temp_layout.addWidget(w)
        layout.addWidget(temp_box)

        perf_box = QGroupBox("PERFORMANCE")
        perf_layout = QVBoxLayout(perf_box)
        self._efficiency = GaugeWidget("Efficiency", "%", 0, 100, lo_alarm=45)
        self._q_duty     = ValueLabel("Heat Duty", "kW")
        perf_layout.addWidget(self._efficiency)
        perf_layout.addWidget(self._q_duty)
        layout.addWidget(perf_box)

        flow_box = QGroupBox("FLOWS")
        flow_layout = QHBoxLayout(flow_box)
        self._flow_hot  = ValueLabel("Hot Flow",  "L/min")
        self._flow_cold = ValueLabel("Cold Flow", "L/min")
        flow_layout.addWidget(self._flow_hot)
        flow_layout.addWidget(self._flow_cold)
        layout.addWidget(flow_box)

        press_box = QGroupBox("PRESSURES")
        press_layout = QHBoxLayout(press_box)
        self._p_hot_in   = ValueLabel("Hot In",   "bar")
        self._p_hot_out  = ValueLabel("Hot Out",  "bar")
        self._p_cold_in  = ValueLabel("Cold In",  "bar")
        self._p_cold_out = ValueLabel("Cold Out", "bar")
        for w in [self._p_hot_in, self._p_hot_out, self._p_cold_in, self._p_cold_out]:
            press_layout.addWidget(w)
        layout.addWidget(press_box)

        pump_box = QGroupBox("PUMPS")
        pump_layout = QHBoxLayout(pump_box)
        self._hot_pump_speed  = ValueLabel("Hot Pump",  "RPM")
        self._cold_pump_speed = ValueLabel("Cold Pump", "RPM")
        pump_layout.addWidget(self._hot_pump_speed)
        pump_layout.addWidget(self._cold_pump_speed)
        layout.addWidget(pump_box)

        valve_box = QGroupBox("VALVES")
        valve_layout = QVBoxLayout(valve_box)
        self._hot_valve  = ValveBar("Hot Valve")
        self._cold_valve = ValveBar("Cold Valve")
        valve_layout.addWidget(self._hot_valve)
        valve_layout.addWidget(self._cold_valve)
        layout.addWidget(valve_box)

        spark_box = QGroupBox("TRENDS")
        spark_layout = QVBoxLayout(spark_box)
        self._spark_eff    = SparklineWidget("Efficiency",  "%",  lo_alarm=45)
        self._spark_t_cold = SparklineWidget("T Cold Out",  "°C", hi_alarm=95)
        spark_layout.addWidget(self._spark_eff)
        spark_layout.addWidget(self._spark_t_cold)
        layout.addWidget(spark_box)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("OPERATOR CONTROL")
        title.setStyleSheet(theme.STYLE_ACCENT)
        layout.addWidget(title)

        hot_box = QGroupBox("HOT PUMP")
        hot_layout = QVBoxLayout(hot_box)
        hot_layout.addWidget(RegisterWriteRow(
            "Speed (RPM)", self._rest, "heat_exchanger", 12, scale=1, hint="0-1450"))
        layout.addWidget(hot_box)

        cold_box = QGroupBox("COLD PUMP")
        cold_layout = QVBoxLayout(cold_box)
        cold_layout.addWidget(RegisterWriteRow(
            "Speed (RPM)", self._rest, "heat_exchanger", 13, scale=1, hint="0-1450"))
        layout.addWidget(cold_box)

        valve_box = QGroupBox("VALVE POSITIONS")
        valve_layout = QVBoxLayout(valve_box)
        valve_layout.addWidget(RegisterWriteRow(
            "Hot Valve (%)",  self._rest, "heat_exchanger", 14, scale=10, hint="0-100"))
        valve_layout.addWidget(RegisterWriteRow(
            "Cold Valve (%)", self._rest, "heat_exchanger", 15, scale=10, hint="0-100"))
        layout.addWidget(valve_box)

        inject_box = QGroupBox("INJECT / SIMULATE")
        inject_layout = QVBoxLayout(inject_box)
        inject_layout.addWidget(RegisterWriteRow(
            "T Hot In (°C)",    self._rest, "heat_exchanger", 0, scale=10, hint="0-300"))
        inject_layout.addWidget(RegisterWriteRow(
            "T Cold Out (°C)",  self._rest, "heat_exchanger", 3, scale=10, hint=">95=overtemp"))
        layout.addWidget(inject_box)

        fault_box = QGroupBox("FAULT MANAGEMENT")
        fault_layout = QVBoxLayout(fault_box)
        fault_layout.addWidget(FaultClearButton(self._rest, "heat_exchanger"))
        layout.addWidget(fault_box)

        layout.addStretch()
        return panel

    def update_data(self, data: dict):
        if not data:
            return
        online = data.get("online", False)
        fault  = data.get("fault_code", 0)
        if not online:    self._badge.set_offline()
        elif fault > 0:   self._badge.set_fault(fault, data.get("fault_text", ""))
        else:             self._badge.set_online()

        self._t_hot_in.set_value(data.get("T_hot_in_C",    0))
        self._t_hot_out.set_value(data.get("T_hot_out_C",  0))
        self._t_cold_in.set_value(data.get("T_cold_in_C",  0))
        self._t_cold_out.set_value(data.get("T_cold_out_C",0))
        self._efficiency.set_value(data.get("efficiency_pct", 0))
        self._q_duty.set_value(data.get("Q_duty_kW",          0))
        self._flow_hot.set_value(data.get("flow_hot_lpm",     0))
        self._flow_cold.set_value(data.get("flow_cold_lpm",   0))
        self._p_hot_in.set_value(data.get("pressure_hot_in_bar",   0))
        self._p_hot_out.set_value(data.get("pressure_hot_out_bar", 0))
        self._p_cold_in.set_value(data.get("pressure_cold_in_bar", 0))
        self._p_cold_out.set_value(data.get("pressure_cold_out_bar",0))
        self._hot_pump_speed.set_value(data.get("hot_pump_speed_rpm",  0))
        self._cold_pump_speed.set_value(data.get("cold_pump_speed_rpm",0))
        self._hot_valve.set_position(data.get("hot_valve_pos_pct",    0))
        self._cold_valve.set_position(data.get("cold_valve_pos_pct",  0))
        self._spark_eff.push(data.get("efficiency_pct", 0))
        self._spark_t_cold.push(data.get("T_cold_out_C",0))
