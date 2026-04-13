"""
MORBION SCADA Server — Base Alarm Evaluator
Abstract contract. One responsibility: define evaluate() interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseAlarmEvaluator(ABC):

    def __init__(self, process_name: str):
        self.process_name = process_name

    @abstractmethod
    def evaluate(self, data: dict) -> list[dict]:
        """
        Evaluate process data dict against alarm limits.
        Returns list of alarm dicts. Empty list = no alarms.
        Never raises. If data is missing a key, treat as no alarm for that check.
        """

    def _alarm(self, alarm_id: str, tag: str, sev: str, desc: str) -> dict:
        """Build a standard alarm dict."""
        return {
            "id":      alarm_id,
            "process": self.process_name,
            "tag":     tag,
            "sev":     sev,          # CRIT | HIGH | MED | LOW
            "desc":    desc,
            "ts":      datetime.now().strftime("%H:%M:%S"),
        }