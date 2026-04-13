"""
MORBION SCADA Server — Pumping Station Reader
Nairobi Water — Municipal Water Pumping Station
Port 502 — 15 registers — 0-based indices

Register map (index: name, scale, unit):
  0  tank_level_pct        ÷10   %
  1  tank_volume_m3        ÷10   m³
  2  pump_speed_rpm        raw   RPM
  3  pump_flow_m3hr        ÷10   m³/hr
  4  discharge_pressure    ÷100  bar
  5  pump_current_A        ÷10   A
  6  pump_power_kW         ÷10   kW
  7  pump_running          raw   0/1
  8  inlet_valve_pos_pct   ÷10   %
  9  outlet_valve_pos_pct  ÷10   %
  10 demand_flow_m3hr      ÷10   m³/hr
  11 net_flow_m3hr         ÷10   m³/hr
  12 pump_starts_today     raw   count
  13 level_sensor_mm       raw   mm
  14 fault_code            raw   0=OK 1=HIGH 2=LOW 3=PUMP 4=DRY_RUN
"""

from readers.base import BaseReader

_FAULT_MAP = {
    0: "OK",
    1: "HIGH_LEVEL",
    2: "LOW_LEVEL",
    3: "PUMP_FAULT",
    4: "DRY_RUN",
}

_REG_COUNT = 15


class PumpingStationReader(BaseReader):

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        super().__init__(host, port, timeout)
        self.process_name = "pumping_station"

    def read(self) -> dict:
        r = self._safe_read(_REG_COUNT)
        if r is None or len(r) < _REG_COUNT:
            return self._offline()

        fault_code = r[14]

        return {
            "online":   True,
            "process":  self.process_name,
            "label":    "Pumping Station",
            "location": "Nairobi Water — Municipal",
            "port":     self.port,

            # Tank
            "tank_level_pct":         round(r[0]  / 10.0, 1),
            "tank_volume_m3":          round(r[1]  / 10.0, 1),

            # Pump
            "pump_speed_rpm":          r[2],
            "pump_flow_m3hr":          round(r[3]  / 10.0, 1),
            "discharge_pressure_bar":  round(r[4]  / 100.0, 2),
            "pump_current_A":          round(r[5]  / 10.0, 1),
            "pump_power_kW":           round(r[6]  / 10.0, 1),
            "pump_running":            bool(r[7]),

            # Valves
            "inlet_valve_pos_pct":     round(r[8]  / 10.0, 1),
            "outlet_valve_pos_pct":    round(r[9]  / 10.0, 1),

            # Flows
            "demand_flow_m3hr":        round(r[10] / 10.0, 1),
            "net_flow_m3hr":           round(r[11] / 10.0, 1),

            # Counters & sensors
            "pump_starts_today":       r[12],
            "level_sensor_mm":         r[13],

            # Status
            "fault_code":              fault_code,
            "fault_text":              _FAULT_MAP.get(fault_code, f"UNKNOWN_{fault_code}"),
        }