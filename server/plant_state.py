"""
MORBION SCADA Server — Plant State
Thread-safe central state. Single source of truth.
Same role as process_state.py in each individual process.

The poller writes. The server reads. Never the other way around.
Lock held for minimum time — snapshot() returns a copy.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PlantState:

    # ── Process data ──────────────────────────────────────────────────────────
    pumping_station: dict = field(default_factory=lambda: {"online": False, "process": "pumping_station"})
    heat_exchanger:  dict = field(default_factory=lambda: {"online": False, "process": "heat_exchanger"})
    boiler:          dict = field(default_factory=lambda: {"online": False, "process": "boiler"})
    pipeline:        dict = field(default_factory=lambda: {"online": False, "process": "pipeline"})

    # ── System state ──────────────────────────────────────────────────────────
    alarms:       list = field(default_factory=list)
    server_time:  str  = ""
    poll_count:   int  = 0
    poll_rate_ms: float = 0.0     # actual measured poll duration

    # ── Internal lock — not serialized ───────────────────────────────────────
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def update(
        self,
        pumping_station: dict,
        heat_exchanger:  dict,
        boiler:          dict,
        pipeline:        dict,
        alarms:          list,
        poll_rate_ms:    float = 0.0,
    ) -> None:
        """Atomic update of all process data. Called by poller thread only."""
        with self._lock:
            self.pumping_station = pumping_station
            self.heat_exchanger  = heat_exchanger
            self.boiler          = boiler
            self.pipeline        = pipeline
            self.alarms          = alarms
            self.poll_rate_ms    = poll_rate_ms
            self.poll_count     += 1
            self.server_time     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def snapshot(self) -> dict:
        """
        Return a complete copy of current state.
        Copy ensures server can serialize without holding the lock.
        """
        with self._lock:
            return {
                "pumping_station": dict(self.pumping_station),
                "heat_exchanger":  dict(self.heat_exchanger),
                "boiler":          dict(self.boiler),
                "pipeline":        dict(self.pipeline),
                "alarms":          list(self.alarms),
                "server_time":     self.server_time,
                "poll_count":      self.poll_count,
                "poll_rate_ms":    round(self.poll_rate_ms, 1),
            }

    def processes_online(self) -> int:
        with self._lock:
            return sum(1 for p in (
                self.pumping_station,
                self.heat_exchanger,
                self.boiler,
                self.pipeline,
            ) if p.get("online"))