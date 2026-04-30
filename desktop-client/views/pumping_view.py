from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer
import threading
import theme
from views.base_view          import BaseProcessView
from widgets.status_badge     import StatusBadge
from widgets.gauge_widget     import GaugeWidget
from widgets.tank_widget      import TankWidget
from widgets.valve_bar        import ValveBar
from widgets.value_label      import ValueLabel
from widgets.sparkline_widget import SparklineWidget
from widgets.control_panel    import RegisterWriteRow, FaultClearButton, ControlButton


class PumpingView(BaseProcessView):

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
        title = QLabel("PUMPING STATION")
        title.setStyleSheet(theme.STYLE_HEADER)
        row.addWidget(title)
        row.addStretch()
        self._badge = StatusBadge()
        row.addWidget(self._badge)
        layout.addLayout(row)

        loc = QLabel("Nairobi Water — Municipal Pumping Station  |  Port 502")
        loc.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(loc)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        tank_box = QGroupBox("STORAGE TANK")
        tank_layout = QVBoxLayout(tank_box)
        self._tank = TankWidget("TANK", hi_alarm=90, lo_alarm=10)
        self._tank.setMinimumHeight(200)
        tank_layout.addWidget(self._tank)
        self._vol_lbl = QLabel("Volume: — m³")
        self._vol_lbl.setStyleSheet(theme.STYLE_DIM)
        self._vol_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tank_layout.addWidget(self._vol_lbl)
        main_row.addWidget(tank_box)

        pump_box = QGroupBox("PUMP")
        pump_layout = QVBoxLayout(pump_box)
        self._pump_running = ValueLabel("Status",            "")
        self._pump_speed   = GaugeWidget("Speed",            "RPM",   0, 1500)
        self._pump_flow    = GaugeWidget("Flow",             "m³/hr", 0, 150)
        self._pump_press   = GaugeWidget("Discharge Pressure","bar",  0, 10, hi_alarm=8.0)
        self._pump_current = ValueLabel("Current",           "A")
        self._pump_power   = ValueLabel("Power",             "kW")
        self._pump_starts  = ValueLabel("Starts Today",      "")
        for w in [self._pump_running, self._pump_speed, self._pump_flow,
                  self._pump_press, self._pump_current, self._pump_power,
                  self._pump_starts]:
            pump_layout.addWidget(w)
        main_row.addWidget(pump_box)
        layout.addLayout(main_row)

        valve_box = QGroupBox("VALVES")
        valve_layout = QVBoxLayout(valve_box)
        self._inlet_valve  = ValveBar("Inlet Valve")
        self._outlet_valve = ValveBar("Outlet Valve")
        valve_layout.addWidget(self._inlet_valve)
        valve_layout.addWidget(self._outlet_valve)
        layout.addWidget(valve_box)

        flow_box = QGroupBox("FLOW BALANCE")
        flow_layout = QHBoxLayout(flow_box)
        self._demand_flow = ValueLabel("Demand Flow", "m³/hr")
        self._net_flow    = ValueLabel("Net Flow",    "m³/hr")
        flow_layout.addWidget(self._demand_flow)
        flow_layout.addWidget(self._net_flow)
        layout.addWidget(flow_box)

        spark_box = QGroupBox("TREND — TANK LEVEL")
        spark_layout = QVBoxLayout(spark_box)
        self._spark_level = SparklineWidget("Tank Level", "%", hi_alarm=90, lo_alarm=10)
        spark_layout.addWidget(self._spark_level)
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

        pump_box = QGroupBox("PUMP")
        pump_layout = QVBoxLayout(pump_box)
        start_btn = ControlButton("START PUMP", theme.GREEN)
        stop_btn  = ControlButton("STOP PUMP",  theme.RED)
        start_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("pumping_station", 7, 1),
            daemon=True).start())
        stop_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("pumping_station", 7, 0),
            daemon=True).start())
        pump_layout.addWidget(start_btn)
        pump_layout.addWidget(stop_btn)
        layout.addWidget(pump_box)

        writes_box = QGroupBox("REGISTER WRITES")
        writes_layout = QVBoxLayout(writes_box)
        writes_layout.addWidget(RegisterWriteRow(
            "Pump Speed (RPM)", self._rest, "pumping_station", 2, scale=1,   hint="0-1450"))
        writes_layout.addWidget(RegisterWriteRow(
            "Outlet Valve (%)", self._rest, "pumping_station", 9, scale=10,  hint="0-100"))
        writes_layout.addWidget(RegisterWriteRow(
            "Inject Level (%)", self._rest, "pumping_station", 0, scale=10,  hint="0-100"))
        layout.addWidget(writes_box)

        inlet_box = QGroupBox("INLET VALVE")
        inlet_layout = QHBoxLayout(inlet_box)
        open_btn  = ControlButton("OPEN",  theme.GREEN)
        close_btn = ControlButton("CLOSE", theme.AMBER)
        open_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("pumping_station", 8, 510),
            daemon=True).start())
        close_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("pumping_station", 8, 0),
            daemon=True).start())
        inlet_layout.addWidget(open_btn)
        inlet_layout.addWidget(close_btn)
        layout.addWidget(inlet_box)

        fault_box = QGroupBox("FAULT MANAGEMENT")
        fault_layout = QVBoxLayout(fault_box)
        fault_layout.addWidget(FaultClearButton(self._rest, "pumping_station"))
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

        self._tank.set_level(data.get("tank_level_pct", 0), data.get("tank_volume_m3", 0))
        self._vol_lbl.setText(f"Volume: {data.get('tank_volume_m3', 0):.1f} m³")

        running = data.get("pump_running", False)
        self._pump_running.set_value(
            "RUNNING" if running else "STOPPED",
            override_color=theme.GREEN if running else theme.TEXT_DIM)
        self._pump_speed.set_value(data.get("pump_speed_rpm",           0))
        self._pump_flow.set_value(data.get("pump_flow_m3hr",            0))
        self._pump_press.set_value(data.get("discharge_pressure_bar",   0))
        self._pump_current.set_value(data.get("pump_current_A",         0))
        self._pump_power.set_value(data.get("pump_power_kW",            0))
        self._pump_starts.set_value(data.get("pump_starts_today",       0))
        self._inlet_valve.set_position(data.get("inlet_valve_pos_pct",  0))
        self._outlet_valve.set_position(data.get("outlet_valve_pos_pct",0))
        self._demand_flow.set_value(data.get("demand_flow_m3hr",        0))
        self._net_flow.set_value(data.get("net_flow_m3hr",              0))
        self._spark_level.push(data.get("tank_level_pct",               0))
