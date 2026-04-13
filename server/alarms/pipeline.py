"""
MORBION SCADA Server — Pipeline Alarms
Limits from lab reference document.
"""

from alarms.base import BaseAlarmEvaluator


class PipelineAlarms(BaseAlarmEvaluator):

    def __init__(self):
        super().__init__("pipeline")

    def evaluate(self, data: dict) -> list[dict]:
        if not data.get("online"):
            return []

        alarms  = []
        outlet  = data.get("outlet_pressure_bar", 40.0)
        inlet   = data.get("inlet_pressure_bar",   2.0)
        flow    = data.get("flow_rate_m3hr",       450.0)
        leak    = data.get("leak_flag",             False)
        fault   = data.get("fault_code", 0)

        # Outlet overpressure — CRIT
        if outlet >= 55.0:
            alarms.append(self._alarm(
                "PL-001", "outlet_pressure_bar", "CRIT",
                f"Outlet OVERPRESSURE {outlet:.1f} bar — limit 55 bar"))
        elif outlet <= 38.0:
            alarms.append(self._alarm(
                "PL-002", "outlet_pressure_bar", "HIGH",
                f"Outlet pressure low {outlet:.1f} bar — delivery at risk"))

        # Inlet low — HIGH
        if inlet <= 1.0:
            alarms.append(self._alarm(
                "PL-003", "inlet_pressure_bar", "HIGH",
                f"Inlet pressure low {inlet:.2f} bar — pump cavitation risk"))

        # Flow low — MED
        if flow <= 200.0:
            alarms.append(self._alarm(
                "PL-004", "flow_rate_m3hr", "MED",
                f"Flow rate low {flow:.1f} m³/hr — possible blockage"))

        # Leak — CRIT
        if leak:
            alarms.append(self._alarm(
                "PL-005", "leak_flag", "CRIT",
                "Leak suspected — flow discrepancy >15 m³/hr — investigate immediately"))

        # PLC fault
        if fault != 0:
            alarms.append(self._alarm(
                "PL-006", "fault_code", "HIGH",
                f"PLC fault active: {data.get('fault_text', str(fault))}"))

        return alarms