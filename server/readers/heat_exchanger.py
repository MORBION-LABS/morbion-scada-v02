"""
MORBION SCADA Server — Heat Exchanger Reader
KenGen Olkaria — Geothermal Heat Recovery Station
Port 506 — 17 registers — 0-based indices

Register map (index: name, scale, unit):
  0  T_hot_in_C           ÷10   °C
  1  T_hot_out_C          ÷10   °C
  2  T_cold_in_C          ÷10   °C
  3  T_cold_out_C         ÷10   °C
  4  flow_hot_lpm         ÷10   L/min
  5  flow_cold_lpm        ÷10   L/min
  6  pressure_hot_in      ÷100  bar
  7  pressure_hot_out     ÷100  bar
  8  pressure_cold_in     ÷100  bar
  9  pressure_cold_out    ÷100  bar
  10 Q_duty_kW            raw   kW
  11 efficiency_pct       ÷10   %
  12 hot_pump_speed_rpm   raw   RPM
  13 cold_pump_speed_rpm  raw   RPM
  14 hot_valve_pos_pct    ÷10   %
  15 cold_valve_pos_pct   ÷10   %
  16 fault_code           raw   0=OK 1=PUMP 2=SENSOR 3=OVERTEMP
"""

from readers.base import BaseReader

_FAULT_MAP = {
    0: "OK",
    1: "PUMP_FAULT",
    2: "SENSOR_FAULT",
    3: "OVERTEMP",
}

_REG_COUNT = 17


class HeatExchangerReader(BaseReader):

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        super().__init__(host, port, timeout)
        self.process_name = "heat_exchanger"

    def read(self) -> dict:
        r = self._safe_read(_REG_COUNT)
        if r is None or len(r) < _REG_COUNT:
            return self._offline()

        fault_code = r[16]

        return {
            "online":   True,
            "process":  self.process_name,
            "label":    "Heat Exchanger",
            "location": "KenGen Olkaria — Geothermal",
            "port":     self.port,

            # Temperatures
            "T_hot_in_C":              round(r[0]  / 10.0, 1),
            "T_hot_out_C":             round(r[1]  / 10.0, 1),
            "T_cold_in_C":             round(r[2]  / 10.0, 1),
            "T_cold_out_C":            round(r[3]  / 10.0, 1),

            # Flows
            "flow_hot_lpm":            round(r[4]  / 10.0, 1),
            "flow_cold_lpm":           round(r[5]  / 10.0, 1),

            # Pressures
            "pressure_hot_in_bar":     round(r[6]  / 100.0, 2),
            "pressure_hot_out_bar":    round(r[7]  / 100.0, 2),
            "pressure_cold_in_bar":    round(r[8]  / 100.0, 2),
            "pressure_cold_out_bar":   round(r[9]  / 100.0, 2),

            # Performance
            "Q_duty_kW":               r[10],
            "efficiency_pct":          round(r[11] / 10.0, 1),

            # Pumps
            "hot_pump_speed_rpm":      r[12],
            "cold_pump_speed_rpm":     r[13],

            # Valves
            "hot_valve_pos_pct":       round(r[14] / 10.0, 1),
            "cold_valve_pos_pct":      round(r[15] / 10.0, 1),

            # Status
            "fault_code":              fault_code,
            "fault_text":              _FAULT_MAP.get(fault_code, f"UNKNOWN_{fault_code}"),
        }