"""
MORBION SCADA Server — Alarm Engine
Aggregates all four process alarm evaluators.
One responsibility: produce unified alarm list from plant dict.
"""

from alarms.evaluators import (
    PumpingStationAlarms,
    HeatExchangerAlarms,
    BoilerAlarms,
    PipelineAlarms,
)


class AlarmEngine:

    def __init__(self):
        self._evaluators = {
            "pumping_station": PumpingStationAlarms(),
            "heat_exchanger":  HeatExchangerAlarms(),
            "boiler":          BoilerAlarms(),
            "pipeline":        PipelineAlarms(),
        }

    def evaluate(self, plant: dict) -> list[dict]:
        """
        Evaluate all processes. Return sorted alarm list.
        CRIT first, then HIGH, MED, LOW.
        """
        alarms = []
        for key, evaluator in self._evaluators.items():
            data = plant.get(key, {})
            try:
                alarms.extend(evaluator.evaluate(data))
            except Exception:
                # Alarm engine must never crash the poller
                pass

        _SEV_ORDER = {"CRIT": 0, "HIGH": 1, "MED": 2, "LOW": 3}
        alarms.sort(key=lambda a: _SEV_ORDER.get(a.get("sev", "LOW"), 9))
        return alarms