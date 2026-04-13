"""
MORBION SCADA Server — InfluxDB Client
Wrapper around influxdb-client. Provides write_points().
"""

import logging

log = logging.getLogger(__name__)


class HistorianClient:
    """
    InfluxDB client wrapper.
    Requires influxdb-client package: pip install influxdb-client
    """

    def __init__(self, url: str, token: str, org: str, bucket: str):
        try:
            from influxdb_client import InfluxDBClient
            self._client = InfluxDBClient(url=url, token=token, org=org)
            self._bucket = bucket
            self._org = org
            self._writer = self._client.write_api()
            log.info("InfluxDB client initialized: %s/%s", url, bucket)
        except ImportError:
            log.error("influxdb-client package not installed")
            raise RuntimeError("influxdb-client required: pip install influxdb-client")

    def write_points(self, points):
        """Write points to InfluxDB."""
        self._writer.write(bucket=self._bucket, org=self._org, record=points)