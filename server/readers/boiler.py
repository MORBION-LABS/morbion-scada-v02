"""
MORBION SCADA Server — Boiler Reader
EABL/Bidco — Industrial Steam Generation
Port 507 — 15 registers — 0-based indices

Register map (index: name, scale, unit):
  0  drum_pressure        ÷100  bar
  1  drum_temp_C          ÷10   °C
  2  drum_level_pct       ÷10   %
  3  steam_flow_kghr      ÷10   kg/hr
  4  feedwater_flow_kghr  ÷10   kg/hr
  5  fuel_flow_kghr       ÷10   kg/hr
  6  burner_state         raw   0=OFF 1=LOW 2=HIGH
  7  fw_pump_speed_rpm    raw   RPM
  8  steam_valve_pos_pct  ÷10   %
  9  fw_valve_pos_pct     ÷10   %
  10 blowdown_valve_pct   ÷10   %
  11 flue_gas_temp_C      ÷10   °C
  12 combustion_eff_pct   ÷10   %
  13 Q_burner_kW          raw   kW
  14 fault_code           raw   0=OK 1=LOW_WATER 2=OVERPRESSURE
                                3=FLAME_FAILURE 4=PUMP_FAULT
"""

from readers.base import BaseReader

_FAULT_MAP = {
    0: "OK",
    1: "LOW_WATER",
    2: "OVERPRESSURE",
    3: "FLAME_FAILURE",
    4: "PUMP_FAULT",
}

_BURNER_MAP = {
    0: "OFF",
    1: "LOW",
    2: "HIGH",
}

_REG_COUNT = 15


class BoilerReader(BaseReader):

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        super().__init__(host, port, timeout)
        self.process_name = "boiler"

    def read(self) -> dict:
        r = self._safe_read(_REG_COUNT)
        if r is None or len(r) < _REG_COUNT:
            return self._offline()

        fault_code   = r[14]
        burner_state = r[6]

        return {
            "online":   True,
            "process":  self.process_name,
            "label":    "Boiler",
            "location": "EABL/Bidco — Industrial Steam",
            "port":     self.port,

            # Drum
            "drum_pressure_bar":       round(r[0]  / 100.0, 2),
            "drum_temp_C":             round(r[1]  / 10.0, 1),
            "drum_level_pct":          round(r[2]  / 10.0, 1),

            # Flows
            "steam_flow_kghr":         round(r[3]  / 10.0, 1),
            "feedwater_flow_kghr":     round(r[4]  / 10.0, 1),
            "fuel_flow_kghr":          round(r[5]  / 10.0, 1),

            # Burner
            "burner_state":            burner_state,
            "burner_text":             _BURNER_MAP.get(burner_state, "UNKNOWN"),

            # Feedwater pump
            "fw_pump_speed_rpm":       r[7],

            # Valves
            "steam_valve_pos_pct":     round(r[8]  / 10.0, 1),
            "fw_valve_pos_pct":        round(r[9]  / 10.0, 1),
            "blowdown_valve_pos_pct":  round(r[10] / 10.0, 1),

            # Combustion
            "flue_gas_temp_C":         round(r[11] / 10.0, 1),
            "combustion_eff_pct":      round(r[12] / 10.0, 1),
            "Q_burner_kW":             r[13],

            # Status
            "fault_code":              fault_code,
            "fault_text":              _FAULT_MAP.get(fault_code, f"UNKNOWN_{fault_code}"),
        }