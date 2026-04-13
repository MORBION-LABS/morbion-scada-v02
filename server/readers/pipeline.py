"""
MORBION SCADA Server — Pipeline Reader
Kenya Pipeline Company — Petroleum Product Transfer
Port 508 — 15 registers — 0-based indices

Register map (index: name, scale, unit):
  0  inlet_pressure_bar    ÷100  bar
  1  outlet_pressure_bar   ÷100  bar
  2  flow_rate_m3hr        ÷10   m³/hr
  3  duty_pump_speed_rpm   raw   RPM
  4  duty_pump_current_A   ÷10   A
  5  duty_pump_running     raw   0/1
  6  standby_pump_speed    raw   RPM
  7  standby_pump_running  raw   0/1
  8  inlet_valve_pos_pct   ÷10   %
  9  outlet_valve_pos_pct  ÷10   %
  10 pump_differential_bar ÷100  bar
  11 flow_velocity_ms      ÷100  m/s
  12 duty_pump_power_kW    raw   kW
  13 leak_flag             raw   0=OK 1=SUSPECTED
  14 fault_code            raw   0=OK 1=DUTY 2=BOTH 3=OVERPRESSURE
"""

from readers.base import BaseReader

_FAULT_MAP = {
    0: "OK",
    1: "DUTY_FAULT",
    2: "BOTH_FAULT",
    3: "OVERPRESSURE",
}

_REG_COUNT = 15


class PipelineReader(BaseReader):

    def __init__(self, host: str, port: int, timeout: float = 3.0):
        super().__init__(host, port, timeout)
        self.process_name = "pipeline"

    def read(self) -> dict:
        r = self._safe_read(_REG_COUNT)
        if r is None or len(r) < _REG_COUNT:
            return self._offline()

        fault_code = r[14]

        return {
            "online":   True,
            "process":  self.process_name,
            "label":    "Pipeline",
            "location": "Kenya Pipeline Co. — Petroleum",
            "port":     self.port,

            # Pressures
            "inlet_pressure_bar":      round(r[0]  / 100.0, 2),
            "outlet_pressure_bar":     round(r[1]  / 100.0, 2),
            "pump_differential_bar":   round(r[10] / 100.0, 2),

            # Flow
            "flow_rate_m3hr":          round(r[2]  / 10.0, 1),
            "flow_velocity_ms":        round(r[11] / 100.0, 2),

            # Duty pump
            "duty_pump_speed_rpm":     r[3],
            "duty_pump_current_A":     round(r[4]  / 10.0, 1),
            "duty_pump_running":       bool(r[5]),
            "duty_pump_power_kW":      r[12],

            # Standby pump
            "standby_pump_speed_rpm":  r[6],
            "standby_pump_running":    bool(r[7]),

            # Valves
            "inlet_valve_pos_pct":     round(r[8]  / 10.0, 1),
            "outlet_valve_pos_pct":    round(r[9]  / 10.0, 1),

            # Safety
            "leak_flag":               bool(r[13]),

            # Status
            "fault_code":              fault_code,
            "fault_text":              _FAULT_MAP.get(fault_code, f"UNKNOWN_{fault_code}"),
        }