"""
MORBION SCADA Server — Poller
Background thread. Drives all readers every poll cycle.
Updates PlantState. Triggers historian writes.
Knows nothing about Flask or WebSocket.
"""

import threading
import time
import logging

from readers.pumping_station import PumpingStationReader
from readers.heat_exchanger  import HeatExchangerReader
from readers.boiler          import BoilerReader
from readers.pipeline        import PipelineReader
from alarm_engine            import AlarmEngine
from plant_state             import PlantState

log = logging.getLogger(__name__)

_PROCESS_KEYS = ("pumping_station", "heat_exchanger", "boiler", "pipeline")


class Poller:

    def __init__(self, config: dict, state: PlantState, historian_writer=None):
        host    = config["plc_host"]
        timeout = config.get("modbus_timeout_s", 3.0)
        procs   = config.get("processes", {})

        # Build only enabled readers
        self._readers: dict = {}
        reader_classes = {
            "pumping_station": PumpingStationReader,
            "heat_exchanger":  HeatExchangerReader,
            "boiler":          BoilerReader,
            "pipeline":        PipelineReader,
        }
        for key, cls in reader_classes.items():
            cfg = procs.get(key, {})
            if cfg.get("enabled", True):
                port = cfg.get("port")
                if port:
                    self._readers[key] = cls(host, port, timeout)
                    log.info("Reader enabled: %s on %s:%d", key, host, port)
                else:
                    log.warning("Reader %s has no port configured — skipped", key)

        self._alarm_engine     = AlarmEngine()
        self._state            = state
        self._historian_writer = historian_writer
        self._poll_rate        = config.get("poll_rate_s", 1.0)
        self._running          = False
        self._thread           = threading.Thread(
            target=self._loop,
            name="MorbionPoller",
            daemon=True,
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread.start()
        log.info("Poller started — poll rate %.1fs", self._poll_rate)

    def stop(self) -> None:
        self._running = False
        log.info("Poller stop requested")

    def _loop(self) -> None:
        while self._running:
            t0 = time.perf_counter()

            # Read all enabled processes
            plant: dict = {}
            for key in _PROCESS_KEYS:
                reader = self._readers.get(key)
                if reader is not None:
                    plant[key] = reader.read()
                else:
                    # Disabled process — report offline
                    plant[key] = {"online": False, "process": key}

            # Evaluate alarms
            alarms = self._alarm_engine.evaluate(plant)

            # Update central state
            poll_ms = (time.perf_counter() - t0) * 1000
            self._state.update(
                pumping_station = plant["pumping_station"],
                heat_exchanger  = plant["heat_exchanger"],
                boiler          = plant["boiler"],
                pipeline        = plant["pipeline"],
                alarms          = alarms,
                poll_rate_ms    = poll_ms,
            )

            # Write to historian if enabled
            if self._historian_writer is not None:
                try:
                    self._historian_writer.write_snapshot(plant)
                except Exception as e:
                    log.error("Historian write failed: %s", e)

            # Sleep remainder of poll interval
            elapsed = time.perf_counter() - t0
            sleep_s = max(0.0, self._poll_rate - elapsed)
            time.sleep(sleep_s)

        log.info("Poller loop exited")