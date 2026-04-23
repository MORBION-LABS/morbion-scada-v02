"""
MORBION SCADA Server — Heat Exchanger Alarms
Limits from lab reference document.

REVISION HISTORY:
  2026-04-XX  v02    Initial MORBION SCADA v02 version
  2026-04-23  v02a   [CHANGE] Lowered efficiency alarm threshold
                          From 60% to 45%
                          Reflects fouling tolerance in dirty conditions
"""

from alarms.base import BaseAlarmEvaluator


class HeatExchangerAlarms(BaseAlarmEvaluator):

    def __init__(self):
        super().__init__("heat_exchanger")

    def evaluate(self, data: dict) -> list[dict]:
        if not data.get("online"):
            return []

        alarms     = []
        t_cold_out = data.get("T_cold_out_C", 0.0)
        t_hot_out  = data.get("T_hot_out_C",  0.0)
        efficiency = data.get("efficiency_pct", 100.0)
        fault      = data.get("fault_code", 0)

        # Cold outlet overtemp — CRIT
        if t_cold_out >= 95.0:
            alarms.append(self._alarm(
                "HX-001", "T_cold_out_C", "CRIT",
                f"Cold outlet OVERTEMP {t_cold_out:.1f}°C — limit 95°C"))

        # Hot outlet high — HIGH
        if t_hot_out >= 160.0:
            alarms.append(self._alarm(
                "HX-002", "T_hot_out_C", "HIGH",
                f"Hot outlet temp high {t_hot_out:.1f}°C — limit 160°C"))

        # Efficiency low — MED (fouling indicator)
        # CHANGE 2026-04-23: threshold 60.0 → 45.0 (lower tolerance)
        if efficiency < 45.0:
            alarms.append(self._alarm(
                "HX-003", "efficiency_pct", "MED",
                f"Efficiency low {efficiency:.1f}% — possible tube fouling"))

        # PLC fault
        if fault != 0:
            alarms.append(self._alarm(
                "HX-004", "fault_code", "HIGH",
                f"PLC fault active: {data.get('fault_text', str(fault))}"))

        return alarms