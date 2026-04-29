"""
pipeline_view.py — Pipeline detailed view
MORBION SCADA v02
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt
import theme
from views.base_view       import BaseProcessView
from widgets.status_badge  import StatusBadge
from widgets.gauge_widget  import GaugeWidget
from widgets.valve_bar     import ValveBar
from widgets.value_label   import ValueLabel
from widgets.sparkline_widget import SparklineWidget
from widgets.control_panel import (
    RegisterWriteRow, FaultClearButton, ControlButton,
)
import threading


class PipelineView(BaseProcessView):

    def __init__(self, rest, config):
        self._rest   = rest
        self._config = config
        super().__init__()

    def _build_data_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        layout    = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        row = QHBoxLayout()
        title = QLabel("PIPELINE")
        title.setStyleSheet(theme.STYLE_HEADER)
        row.addWidget(title)
        row.addStretch()
        self._badge = StatusBadge()
        row.addWidget(self._badge)
        layout.addLayout(row)

        loc = QLabel(
            "Kenya Pipeline Co. — Petroleum Transfer  |  Port 508")
        loc.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(loc)

        # Pressures + flow
        press_box = QGroupBox("PRESSURES & FLOW")
        press_layout = QVBoxLayout(press_box)
        self._inlet_press  = GaugeWidget(
            "Inlet Pressure", "bar", 0, 10, lo_alarm=1.0)
        self._outlet_press = GaugeWidget(
            "Outlet Pressure", "bar", 0, 60, hi_alarm=55, lo_alarm=30)
        self._flow_rate    = GaugeWidget(
            "Flow Rate", "m³/hr", 0, 600, lo_alarm=200)
        self._flow_vel     = ValueLabel("Flow Velocity", "m/s")
        press_layout.addWidget(self._inlet_press)
        press_layout.addWidget(self._outlet_press)
        press_layout.addWidget(self._flow_rate)
        press_layout.addWidget(self._flow_vel)
        layout.addWidget(press_box)

        # Duty pump
        duty_box = QGroupBox("DUTY PUMP")
        duty_layout = QHBoxLayout(duty_box)
        self._duty_running = ValueLabel("Status", "")
        self._duty_speed   = ValueLabel("Speed", "RPM")
        self._duty_current = ValueLabel("Current", "A")
        self._duty_power   = ValueLabel("Power", "kW")
        self._duty_diff    = ValueLabel("Differential", "bar")
        duty_layout.addWidget(self._duty_running)
        duty_layout.addWidget(self._duty_speed)
        duty_layout.addWidget(self._duty_current)
        duty_layout.addWidget(self._duty_power)
        duty_layout.addWidget(self._duty_diff)
        layout.addWidget(duty_box)

        # Standby pump
        standby_box = QGroupBox("STANDBY PUMP")
        standby_layout = QHBoxLayout(standby_box)
        self._standby_running = ValueLabel("Status", "")
        self._standby_speed   = ValueLabel("Speed", "RPM")
        standby_layout.addWidget(self._standby_running)
        standby_layout.addWidget(self._standby_speed)
        layout.addWidget(standby_box)

        # Leak
        leak_box = QGroupBox("LEAK DETECTION")
        leak_layout = QHBoxLayout(leak_box)
        self._leak_flag = ValueLabel("Leak Flag", "")
        leak_layout.addWidget(self._leak_flag)
        layout.addWidget(leak_box)

        # Valves
        valve_box = QGroupBox("VALVES")
        valve_layout = QVBoxLayout(valve_box)
        self._inlet_valve  = ValveBar("Inlet Valve")
        self._outlet_valve = ValveBar("Outlet Valve")
        valve_layout.addWidget(self._inlet_valve)
        valve_layout.addWidget(self._outlet_valve)
        layout.addWidget(valve_box)

        # Sparklines
        spark_box = QGroupBox("TRENDS")
        spark_layout = QVBoxLayout(spark_box)
        self._spark_outlet = SparklineWidget(
            "Outlet Pressure", "bar", hi_alarm=55, lo_alarm=30)
        self._spark_flow   = SparklineWidget(
            "Flow Rate", "m³/hr", lo_alarm=200)
        spark_layout.addWidget(self._spark_outlet)
        spark_layout.addWidget(self._spark_flow)
        layout.addWidget(spark_box)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_control_panel(self) -> QWidget:
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("OPERATOR CONTROL")
        title.setStyleSheet(theme.STYLE_ACCENT)
        layout.addWidget(title)

        # Duty pump
        duty_box = QGroupBox("DUTY PUMP")
        duty_layout = QVBoxLayout(duty_box)
        start_btn = ControlButton("START DUTY",   theme.GREEN)
        stop_btn  = ControlButton("STOP DUTY",    theme.RED)

        def start_duty():
            threading.Thread(
                target=lambda: self._rest.write_register("pipeline", 5, 1),
                daemon=True
            ).start()

        def stop_duty():
            threading.Thread(
                target=lambda: self._rest.write_register("pipeline", 5, 0),
                daemon=True
            ).start()

        start_btn.clicked.connect(start_duty)
        stop_btn.clicked.connect(stop_duty)
        duty_layout.addWidget(start_btn)
        duty_layout.addWidget(stop_btn)
        duty_layout.addWidget(RegisterWriteRow(
            "Speed (RPM)", self._rest,
            "pipeline", 3, scale=1, hint="0-1480"))
        layout.addWidget(duty_box)

        # Standby pump
        standby_box = QGroupBox("STANDBY PUMP")
        standby_layout = QVBoxLayout(standby_box)
        sb_start = ControlButton("START STANDBY", theme.GREEN)
        sb_stop  = ControlButton("STOP STANDBY",  theme.RED)

        def start_standby():
            threading.Thread(
                target=lambda: self._rest.write_register("pipeline", 7, 1),
                daemon=True
            ).start()

        def stop_standby():
            threading.Thread(
                target=lambda: self._rest.write_register("pipeline", 7, 0),
                daemon=True
            ).start()

        sb_start.clicked.connect(start_standby)
        sb_stop.clicked.connect(stop_standby)
        standby_layout.addWidget(sb_start)
        standby_layout.addWidget(sb_stop)
        layout.addWidget(standby_box)

        # Valve + inject
        writes_box = QGroupBox("REGISTER WRITES")
        writes_layout = QVBoxLayout(writes_box)
        writes_layout.addWidget(RegisterWriteRow(
            "Outlet Valve (%)", self._rest,
            "pipeline", 9, scale=10, hint="0-100"))
        writes_layout.addWidget(RegisterWriteRow(
            "Inject Outlet P (bar)", self._rest,
            "pipeline", 1, scale=100, hint=">55 triggers overpressure"))
        writes_layout.addWidget(RegisterWriteRow(
            "Inject Leak Flag", self._rest,
            "pipeline", 13, scale=1, hint="1=inject leak"))
        layout.addWidget(writes_box)

        # Fault
        fault_box = QGroupBox("FAULT MANAGEMENT")
        fault_layout = QVBoxLayout(fault_box)
        fault_layout.addWidget(FaultClearButton(self._rest, "pipeline"))
        layout.addWidget(fault_box)

        layout.addStretch()
        return panel

    def update_data(self, data: dict):
        if not data:
            return

        online = data.get("online", False)
        fault  = data.get("fault_code", 0)

        if not online:
            self._badge.set_offline()
        elif fault > 0:
            self._badge.set_fault(fault, data.get("fault_text", ""))
        else:
            self._badge.set_online()

        self._inlet_press.set_value(data.get("inlet_pressure_bar", 0))
        self._outlet_press.set_value(data.get("outlet_pressure_bar", 0))
        self._flow_rate.set_value(data.get("flow_rate_m3hr", 0))
        self._flow_vel.set_value(data.get("flow_velocity_ms", 0))

        duty_run = data.get("duty_pump_running", False)
        self._duty_running.set_value(
            "RUNNING" if duty_run else "STOPPED",
            override_color=theme.GREEN if duty_run else theme.TEXT_DIM,
        )
        self._duty_speed.set_value(data.get("duty_pump_speed_rpm", 0))
        self._duty_current.set_value(data.get("duty_pump_current_A", 0))
        self._duty_power.set_value(data.get("duty_pump_power_kW", 0))
        self._duty_diff.set_value(data.get("pump_differential_bar", 0))

        standby_run = data.get("standby_pump_running", False)
        self._standby_running.set_value(
            "RUNNING" if standby_run else "STANDBY",
            override_color=theme.AMBER if standby_run else theme.TEXT_DIM,
        )
        self._standby_speed.set_value(data.get("standby_pump_speed_rpm", 0))

        leak = data.get("leak_flag", False)
        self._leak_flag.set_value(
            "⚠ LEAK SUSPECTED" if leak else "OK",
            override_color=theme.RED if leak else theme.GREEN,
        )

        self._inlet_valve.set_position(data.get("inlet_valve_pos_pct", 0))
        self._outlet_valve.set_position(data.get("outlet_valve_pos_pct", 0))

        self._spark_outlet.push(data.get("outlet_pressure_bar", 0))
        self._spark_flow.push(data.get("flow_rate_m3hr", 0))
