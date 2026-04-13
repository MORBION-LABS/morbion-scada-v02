"""
MORBION SCADA Server — Boiler Alarms
Limits from lab reference document.
"""

from alarms.base import BaseAlarmEvaluator


class BoilerAlarms(BaseAlarmEvaluator):

    def __init__(self):
        super().__init__("boiler")

    def evaluate(self, data: dict) -> list[dict]:
        if not data.get("online"):
            return []

        alarms   = []
        pressure = data.get("drum_pressure_bar", 8.0)
        level    = data.get("drum_level_pct",   50.0)
        fault    = data.get("fault_code", 0)

        # Overpressure — CRIT safety interlock
        if pressure >= 10.0:
            alarms.append(self._alarm(
                "BL-001", "drum_pressure_bar", "CRIT",
                f"Drum OVERPRESSURE {pressure:.2f} bar — safety trip limit 10 bar"))
        elif pressure <= 6.0:
            alarms.append(self._alarm(
                "BL-002", "drum_pressure_bar", "HIGH",
                f"Drum pressure low {pressure:.2f} bar — steam supply at risk"))

        # Low water — CRIT safety interlock
        if level <= 20.0:
            alarms.append(self._alarm(
                "BL-003", "drum_level_pct", "CRIT",
                f"Drum LOW WATER {level:.1f}% — burner trip active"))
        elif level >= 80.0:
            alarms.append(self._alarm(
                "BL-004", "drum_level_pct", "HIGH",
                f"Drum level high {level:.1f}% — carryover risk"))

        # PLC fault
        if fault != 0:
            alarms.append(self._alarm(
                "BL-005", "fault_code", "HIGH",
                f"PLC fault active: {data.get('fault_text', str(fault))}"))

        return alarms