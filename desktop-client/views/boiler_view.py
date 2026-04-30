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


class BoilerView(BaseProcessView):

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
        title = QLabel("BOILER")
        title.setStyleSheet(theme.STYLE_HEADER)
        row.addWidget(title)
        row.addStretch()
        self._badge = StatusBadge()
        row.addWidget(self._badge)
        layout.addLayout(row)

        loc = QLabel("EABL/Bidco — Industrial Steam Generation  |  Port 507")
        loc.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(loc)

        drum_box = QGroupBox("STEAM DRUM")
        drum_layout = QVBoxLayout(drum_box)
        self._drum_press = GaugeWidget("Drum Pressure", "bar", 0, 12, hi_alarm=10, lo_alarm=6)
        self._drum_temp  = ValueLabel("Drum Temp",      "°C")
        self._drum_level = GaugeWidget("Drum Level",    "%",  0, 100, hi_alarm=80, lo_alarm=20)
        drum_layout.addWidget(self._drum_press)
        drum_layout.addWidget(self._drum_temp)
        drum_layout.addWidget(self._drum_level)
        layout.addWidget(drum_box)

        burner_box = QGroupBox("BURNER")
        burner_layout = QHBoxLayout(burner_box)
        self._burner_state = ValueLabel("State",           "")
        self._fuel_flow    = ValueLabel("Fuel Flow",       "kg/hr")
        self._q_burner     = ValueLabel("Heat Release",    "kW")
        self._flue_temp    = ValueLabel("Flue Gas Temp",   "°C")
        self._comb_eff     = ValueLabel("Combustion Eff",  "%")
        for w in [self._burner_state, self._fuel_flow, self._q_burner,
                  self._flue_temp, self._comb_eff]:
            burner_layout.addWidget(w)
        layout.addWidget(burner_box)

        flow_box = QGroupBox("FLOWS")
        flow_layout = QHBoxLayout(flow_box)
        self._steam_flow = ValueLabel("Steam Flow",     "kg/hr")
        self._fw_flow    = ValueLabel("Feedwater Flow", "kg/hr")
        flow_layout.addWidget(self._steam_flow)
        flow_layout.addWidget(self._fw_flow)
        layout.addWidget(flow_box)

        valve_box = QGroupBox("VALVES")
        valve_layout = QVBoxLayout(valve_box)
        self._steam_valve    = ValveBar("Steam Valve")
        self._fw_valve       = ValveBar("Feedwater Valve")
        self._blowdown_valve = ValveBar("Blowdown Valve")
        valve_layout.addWidget(self._steam_valve)
        valve_layout.addWidget(self._fw_valve)
        valve_layout.addWidget(self._blowdown_valve)
        layout.addWidget(valve_box)

        spark_box = QGroupBox("TRENDS")
        spark_layout = QVBoxLayout(spark_box)
        self._spark_press = SparklineWidget("Drum Pressure", "bar", hi_alarm=10, lo_alarm=6)
        self._spark_level = SparklineWidget("Drum Level",    "%",   hi_alarm=80, lo_alarm=20)
        spark_layout.addWidget(self._spark_press)
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

        burner_box = QGroupBox("BURNER STATE")
        burner_layout = QVBoxLayout(burner_box)
        off_btn  = ControlButton("BURNER OFF",  theme.TEXT_DIM)
        low_btn  = ControlButton("BURNER LOW",  theme.AMBER)
        high_btn = ControlButton("BURNER HIGH", theme.RED)
        off_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("boiler", 6, 0), daemon=True).start())
        low_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("boiler", 6, 1), daemon=True).start())
        high_btn.clicked.connect(lambda: threading.Thread(
            target=lambda: self._rest.write_register("boiler", 6, 2), daemon=True).start())
        burner_layout.addWidget(off_btn)
        burner_layout.addWidget(low_btn)
        burner_layout.addWidget(high_btn)
        layout.addWidget(burner_box)

        writes_box = QGroupBox("REGISTER WRITES")
        writes_layout = QVBoxLayout(writes_box)
        writes_layout.addWidget(RegisterWriteRow(
            "FW Pump Speed (RPM)", self._rest, "boiler", 7,  scale=1,   hint="0-1450"))
        writes_layout.addWidget(RegisterWriteRow(
            "Steam Valve (%)",     self._rest, "boiler", 8,  scale=10,  hint="0-100"))
        writes_layout.addWidget(RegisterWriteRow(
            "FW Valve (%)",        self._rest, "boiler", 9,  scale=10,  hint="0-100"))
        writes_layout.addWidget(RegisterWriteRow(
            "Blowdown Valve (%)",  self._rest, "boiler", 10, scale=10,  hint="0-100"))
        layout.addWidget(writes_box)

        inject_box = QGroupBox("INJECT / SIMULATE")
        inject_layout = QVBoxLayout(inject_box)
        inject_layout.addWidget(RegisterWriteRow(
            "Drum Pressure (bar)", self._rest, "boiler", 0, scale=100, hint=">10=overpressure"))
        inject_layout.addWidget(RegisterWriteRow(
            "Drum Level (%)",      self._rest, "boiler", 2, scale=10,  hint="<20=low water"))
        layout.addWidget(inject_box)

        fault_box = QGroupBox("FAULT MANAGEMENT")
        fault_layout = QVBoxLayout(fault_box)
        fault_layout.addWidget(FaultClearButton(self._rest, "boiler"))
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

        self._drum_press.set_value(data.get("drum_pressure_bar", 0))
        self._drum_temp.set_value(data.get("drum_temp_C",         0))
        self._drum_level.set_value(data.get("drum_level_pct",     0))

        burner_state  = data.get("burner_state", 0)
        burner_map    = {0: "OFF", 1: "LOW", 2: "HIGH"}
        burner_colors = {0: theme.TEXT_DIM, 1: theme.AMBER, 2: theme.RED}
        self._burner_state.set_value(
            burner_map.get(burner_state, "?"),
            override_color=burner_colors.get(burner_state, theme.TEXT))

        self._fuel_flow.set_value(data.get("fuel_flow_kghr",      0))
        self._q_burner.set_value(data.get("Q_burner_kW",          0))
        self._flue_temp.set_value(data.get("flue_gas_temp_C",     0))
        self._comb_eff.set_value(data.get("combustion_eff_pct",   0))
        self._steam_flow.set_value(data.get("steam_flow_kghr",    0))
        self._fw_flow.set_value(data.get("feedwater_flow_kghr",   0))
        self._steam_valve.set_position(data.get("steam_valve_pos_pct",    0))
        self._fw_valve.set_position(data.get("fw_valve_pos_pct",         0))
        self._blowdown_valve.set_position(data.get("blowdown_valve_pos_pct",0))
        self._spark_press.push(data.get("drum_pressure_bar", 0))
        self._spark_level.push(data.get("drum_level_pct",    0))
