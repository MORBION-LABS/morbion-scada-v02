"""
alarm_engine.py — MORBION SCADA Server Alarm Engine
MORBION SCADA v02

KEY FIX FROM v01:
  v01 imported from alarms.evaluators which duplicated all four
  alarm classes. evaluators.py has been deleted.
  v02 imports directly from the individual alarm modules.

One responsibility: produce unified sorted alarm list from plant dict.
Alarm evaluators never raise — engine catches all exceptions.
"""

import logging
from alarms.pumping_station import PumpingStationAlarms
from alarms.heat_exchanger  import HeatExchangerAlarms
from alarms.boiler          import BoilerAlarms
from alarms.pipeline        import PipelineAlarms

log = logging.getLogger("alarm_engine")

_SEV_ORDER = {"CRIT": 0, "HIGH": 1, "MED": 2, "LOW": 3}


class AlarmEngine:

    def __init__(self):
        self._evaluators = {
            "pumping_station": PumpingStationAlarms(),
            "heat_exchanger":  HeatExchangerAlarms(),
            "boiler":          BoilerAlarms(),
            "pipeline":        PipelineAlarms(),
        }

    def evaluate(self, plant: dict) -> list:
        """
        Evaluate all four processes.
        Returns alarm list sorted CRIT → HIGH → MED → LOW.
        Never raises — all evaluator exceptions caught here.
        """
        alarms = []
        for key, evaluator in self._evaluators.items():
            data = plant.get(key, {})
            try:
                alarms.extend(evaluator.evaluate(data))
            except Exception as e:
                log.error("Alarm evaluator %s failed: %s", key, e)

        alarms.sort(key=lambda a: _SEV_ORDER.get(a.get("sev", "LOW"), 9))
        return alarms
