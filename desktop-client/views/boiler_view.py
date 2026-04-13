"""
MORBION — Boiler View
EABL/Bidco — Industrial Steam Generation — Port 507
"""

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QGroupBox, QSplitter, QLabel
from PyQt6.QtCore    import Qt

from views.base_view           import BaseView
from widgets.value_label       import ValueLabel
from widgets.tank_widget       import TankWidget
from widgets.sparkline_widget  import SparklineWidget
from widgets.valve_bar         import ValveBar
from widgets.status_badge      import StatusBadge
from widgets.control_panel     import ControlPanel
from theme import C_GREEN, C_YELLOW, C_ORANGE, C_MUTED


_CONTROL_SPEC = {
    "process": "boiler",
    "faults": [
        {"name": "Inject LOW WATER (15%)",      "register": 2,  "value": 150,  "danger": True},
        {"name": "Inject OVERPRESSURE (11 bar)", "register": 0,  "value": 1100, "danger": True},
        {"name": "Trip Burner (OFF)",             "register": 6,  "value": 0,    "danger": True},
        {"name": "Clear Fault Code",              "register": 14, "value": 0,    "danger": False},
    ],
    "writes": [
        {"label": "Drum Level (raw ×10)",   "register": 2,  "min": 0, "max": 1000, "default": 500},
        {"label": "Burner State (0/1/2)",   "register": 6,  "min": 0, "max": 2,    "default": 1},
        {"label": "Steam Valve (raw ×10)",  "register": 8,  "min": 0, "max": 1000, "default": 800},
        {"label": "Fault Code (0=clear)",   "register": 14, "min": 0, "max": 4,    "default": 0},
    ],
}

_BURNER_COLORS = {"OFF": C_MUTED, "LOW": C_YELLOW, "HIGH": C_ORANGE}


class BoilerView(BaseView):

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

        # Drum
        drum_group = QGroupBox("STEAM DRUM")
        drum_layout = QHBoxLayout(drum_group)
        self._drum = TankWidget(0, 100, warn_pct=80, crit_pct=20)
        self._drum.setFixedWidth(70)
        drum_layout.addWidget(self._drum)
        drum_vals = QVBoxLayout()
        self._v_pressure  = ValueLabel("Drum Pressure", "bar", warn_threshold=9,  crit_threshold=10)
        self._v_temp      = ValueLabel("Drum Temp",     "°C")
        self._v_level     = ValueLabel("Drum Level",    "%",   warn_threshold=None)
        self._spark_press = SparklineWidget(color="#ff8800")
        for w in (self._v_pressure, self._v_temp, self._v_level, self._spark_press):
            drum_vals.addWidget(w)
        drum_layout.addLayout(drum_vals)
        left.addWidget(drum_group)

        # Burner
        burn_group = QGroupBox("BURNER & COMBUSTION")
        burn_layout = QVBoxLayout(burn_group)
        self._burner_lbl = QLabel("● OFF")
        self._burner_lbl.setStyleSheet(
            f"color:{C_MUTED};font-size:18px;font-weight:bold;letter-spacing:4px;")
        self._burner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._v_fuel     = ValueLabel("Fuel Flow",     "kg/hr")
        self._v_q_burner = ValueLabel("Q Burner",      "kW")
        self._v_comb_eff = ValueLabel("Comb. Eff.",    "%")
        self._v_flue     = ValueLabel("Flue Gas Temp", "°C")
        for w in (self._burner_lbl, self._v_fuel, self._v_q_burner,
                  self._v_comb_eff, self._v_flue):
            burn_layout.addWidget(w)
        left.addWidget(burn_group)

        # Steam & FW
        sf_group = QGroupBox("STEAM & FEEDWATER")
        sf_layout = QVBoxLayout(sf_group)
        self._v_steam_flow = ValueLabel("Steam Flow",  "kg/hr")
        self._v_fw_flow    = ValueLabel("FW Flow",     "kg/hr")
        self._v_fw_pump    = ValueLabel("FW Pump",     "RPM")
        self._spark_steam  = SparklineWidget(color="#00d4ff")
        self._vb_steam     = ValveBar("Steam Valve")
        self._vb_fw        = ValveBar("FW Valve")
        self._vb_bd        = ValveBar("Blowdown")
        self._v_fault      = ValueLabel("Fault",       "")
        for w in (self._v_steam_flow, self._v_fw_flow, self._v_fw_pump,
                  self._spark_steam, self._vb_steam, self._vb_fw,
                  self._vb_bd, self._v_fault):
            sf_layout.addWidget(w)
        left.addWidget(sf_group)
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

        lvl = data.get("drum_level_pct", 0)
        self._drum.set_value(lvl, f"{lvl:.1f}%")

        self._v_pressure.set_value(data.get("drum_pressure_bar"), 2)
        self._v_temp.set_value(data.get("drum_temp_C"), 1)
        self._v_level.set_value(lvl, 1)
        self._spark_press.push(data.get("drum_pressure_bar", 0))

        btext = data.get("burner_text", "OFF")
        color = _BURNER_COLORS.get(btext, C_MUTED)
        self._burner_lbl.setText(f"● {btext}")
        self._burner_lbl.setStyleSheet(
            f"color:{color};font-size:18px;font-weight:bold;letter-spacing:4px;")

        self._v_fuel.set_value(data.get("fuel_flow_kghr"), 1)
        self._v_q_burner.set_value(data.get("Q_burner_kW"), 0)
        self._v_comb_eff.set_value(data.get("combustion_eff_pct"), 1)
        self._v_flue.set_value(data.get("flue_gas_temp_C"), 1)
        self._v_steam_flow.set_value(data.get("steam_flow_kghr"), 1)
        self._v_fw_flow.set_value(data.get("feedwater_flow_kghr"), 1)
        self._v_fw_pump.set_value(data.get("fw_pump_speed_rpm"), 0)
        self._spark_steam.push(data.get("steam_flow_kghr", 0))
        self._vb_steam.set_value(data.get("steam_valve_pos_pct", 0))
        self._vb_fw.set_value(data.get("fw_valve_pos_pct", 0))
        self._vb_bd.set_value(data.get("blowdown_valve_pos_pct", 0))
        self._v_fault.set_value(f"{data.get('fault_code',0)} — {data.get('fault_text','OK')}")