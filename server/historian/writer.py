"""
writer.py — MORBION SCADA Historian Writer
MORBION SCADA v02

KEY FIX FROM v01:
  v01 used datetime.now(datetime.timezone.utc) which is wrong —
  datetime.timezone is not an attribute of datetime objects.
  It is datetime.timezone from the datetime module.
  This caused a silent crash every write cycle.

  v02 uses: from datetime import datetime, timezone
            datetime.now(timezone.utc)

  v01 also called Point().tag(**tags) which is wrong API usage.
  tag() takes two positional args (key, value), not **kwargs.
  v02 calls point.tag(key, value) for each tag individually.

  v01 imported Point inside the loop on every write — wasteful.
  v02 imports at module level with graceful fallback.
"""

import logging
from typing import Optional

log = logging.getLogger("historian.writer")

try:
    from influxdb_client import Point
    _INFLUX_AVAILABLE = True
except ImportError:
    _INFLUX_AVAILABLE = False
    log.warning("influxdb-client not installed — historian disabled")


class HistorianWriter:
    """
    Translates plant snapshots to InfluxDB points.
    write_snapshot() called by poller after every poll cycle.

    Each process becomes a measurement.
    Each numeric/bool field becomes a field in that measurement.
    String fields (fault_text, burner_text, label, location) are tags.
    """

    # Fields to skip — not useful as time series data
    _SKIP_FIELDS = frozenset({
        "online", "process", "label", "location",
        "port", "fault_text", "burner_text",
    })

    # Fields to store as tags rather than fields
    _TAG_FIELDS = frozenset({
        "process", "label", "location",
    })

    def __init__(self, influx_client):
        self._client = influx_client

    def write_snapshot(self, plant: dict) -> None:
        """
        Write complete plant snapshot to InfluxDB.
        Skips offline processes — no point writing zeros.
        Never raises — all exceptions logged and swallowed.
        """
        if not _INFLUX_AVAILABLE:
            return
        if self._client is None:
            return

        try:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc)
            points    = []

            for process_name, data in plant.items():
                # Skip non-process keys in plant dict
                if not isinstance(data, dict):
                    continue
                if process_name in ("alarms", "server_time",
                                    "poll_count", "poll_rate_ms"):
                    continue
                # Skip offline processes
                if not data.get("online", False):
                    continue

                point = Point(process_name)

                # Add standard tags
                point.tag("process",  process_name)
                point.tag("label",    data.get("label",    ""))
                point.tag("location", data.get("location", ""))
                point.time(timestamp)

                # Add numeric and bool fields
                has_fields = False
                for k, v in data.items():
                    if k in self._SKIP_FIELDS:
                        continue
                    if isinstance(v, bool):
                        point.field(k, int(v))
                        has_fields = True
                    elif isinstance(v, (int, float)):
                        point.field(k, float(v))
                        has_fields = True
                    # Skip strings — not useful as InfluxDB fields

                if has_fields:
                    points.append(point)

            if points:
                self._client.write_points(points)
                log.debug("Wrote %d points to InfluxDB", len(points))

        except Exception as e:
            log.error("Historian write failed: %s", e)
