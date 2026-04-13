"""
MORBION SCADA Server — Pumping Station Alarms
Limits from lab reference document.
"""

from alarms.base import BaseAlarmEvaluator


class PumpingStationAlarms(BaseAlarmEvaluator):

    def __init__(self):
        super().__init__("pumping_station")

    def evaluate(self, data: dict) -> list[dict]:
        if not data.get("online"):
            return []

        alarms = []
        level    = data.get("tank_level_pct", 50.0)
        pressure = data.get("discharge_pressure_bar", 0.0)
        fault    = data.get("fault_code", 0)

        # Level — CRIT above 90%, HIGH above 80%
        if level >= 90.0:
            alarms.append(self._alarm(
                "PS-001", "tank_level_pct", "CRIT",
                f"Tank CRITICAL HIGH {level:.1f}% — overflow risk, restrict outlet"))
        elif level >= 80.0:
            alarms.append(self._alarm(
                "PS-002", "tank_level_pct", "HIGH",
                f"Tank level high {level:.1f}% — approaching pump stop"))

        # Level — CRIT below 5%, HIGH below 10%
        if level <= 5.0:
            alarms.append(self._alarm(
                "PS-003", "tank_level_pct", "CRIT",
                f"Tank CRITICAL LOW {level:.1f}% — dry run imminent"))
        elif level <= 10.0:
            alarms.append(self._alarm(
                "PS-004", "tank_level_pct", "HIGH",
                f"Tank level low {level:.1f}% — pump start imminent"))

        # Discharge pressure
        if pressure >= 8.0:
            alarms.append(self._alarm(
                "PS-005", "discharge_pressure_bar", "HIGH",
                f"Discharge pressure high {pressure:.2f} bar — limit 8.0 bar"))

        # PLC fault
        if fault != 0:
            alarms.append(self._alarm(
                "PS-006", "fault_code", "HIGH",
                f"PLC fault active: {data.get('fault_text', str(fault))}"))

        return alarms