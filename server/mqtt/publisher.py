"""
publisher.py — MORBION SCADA MQTT Publisher
MORBION SCADA v02

Publishes all process variables to Mosquitto broker.
Topic pattern: morbion/<process>/<variable>

Examples:
    morbion/pumping_station/tank_level_pct      → "73.4"
    morbion/boiler/drum_pressure_bar            → "8.02"
    morbion/pipeline/duty_pump_running          → "true"
    morbion/server/status                       → "online"
    morbion/alarms/count                        → "2"
    morbion/alarms/crit_count                   → "1"

Enables:
    - Node-RED integration
    - Grafana via MQTT datasource
    - Mobile monitoring apps
    - Any MQTT subscriber on the network
    - Inter-process communication

Retained topics:
    morbion/server/status — so new subscribers know server is alive

paho-mqtt must be installed: pip install paho-mqtt
If not installed, MQTT is silently disabled.
"""

import logging
import threading
from typing import Optional

log = logging.getLogger("mqtt.publisher")

try:
    import paho.mqtt.client as mqtt
    _MQTT_AVAILABLE = True
except ImportError:
    _MQTT_AVAILABLE = False
    log.warning("paho-mqtt not installed — MQTT publishing disabled")
    log.warning("Install with: pip install paho-mqtt")


class MQTTPublisher:
    """
    Publishes plant data to Mosquitto MQTT broker.
    Non-blocking — uses paho async loop.
    Reconnects automatically on disconnect.
    """

    # Fields to skip — internal metadata not useful on MQTT
    _SKIP_FIELDS = frozenset({
        "online", "process", "label", "location",
        "port", "fault_text", "burner_text",
    })

    def __init__(self, config: dict):
        mqtt_cfg        = config.get("mqtt", {})
        self._enabled   = mqtt_cfg.get("enabled", False)
        self._host      = mqtt_cfg.get("host",         "localhost")
        self._port      = mqtt_cfg.get("port",         1883)
        self._prefix    = mqtt_cfg.get("topic_prefix", "morbion")
        self._keepalive = mqtt_cfg.get("keepalive",    60)
        self._connected = False
        self._client: Optional[object] = None

        if not self._enabled:
            log.info("MQTT publishing disabled in config")
            return

        if not _MQTT_AVAILABLE:
            log.warning("MQTT enabled in config but paho-mqtt not installed")
            return

        self._connect()

    def _connect(self):
        try:
            self._client = mqtt.Client(
                client_id="morbion-scada-v02",
                clean_session=True,
            )
            self._client.on_connect    = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_log        = self._on_log

            # Will message — published if we disconnect ungracefully
            self._client.will_set(
                f"{self._prefix}/server/status",
                payload="offline",
                qos=0,
                retain=True,
            )

            self._client.connect_async(self._host, self._port, self._keepalive)
            self._client.loop_start()
            log.info("MQTT connecting to %s:%d", self._host, self._port)

        except Exception as e:
            log.error("MQTT connection setup failed: %s", e)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info("MQTT connected: %s:%d", self._host, self._port)
            # Announce server online
            client.publish(
                f"{self._prefix}/server/status",
                "online",
                retain=True,
            )
        else:
            rc_messages = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorised",
            }
            log.warning("MQTT connection refused: %s",
                        rc_messages.get(rc, f"rc={rc}"))

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            log.warning("MQTT unexpected disconnect rc=%d — will reconnect", rc)
        else:
            log.info("MQTT disconnected cleanly")

    def _on_log(self, client, userdata, level, buf):
        # Only log errors from paho internals
        if "error" in buf.lower():
            log.debug("MQTT paho: %s", buf)

    def publish_plant(self, plant: dict) -> None:
        """
        Publish complete plant snapshot to MQTT.
        Called every poll cycle from the WS broadcast loop.
        Non-blocking — paho handles the actual send asynchronously.
        """
        if not self._enabled or not self._connected or self._client is None:
            return

        try:
            for process_name, data in plant.items():
                if not isinstance(data, dict):
                    continue
                if process_name in ("alarms", "server_time",
                                    "poll_count", "poll_rate_ms"):
                    continue

                base   = f"{self._prefix}/{process_name}"
                online = data.get("online", False)

                # Publish online status
                self._client.publish(
                    f"{base}/online",
                    "true" if online else "false",
                    retain=False,
                )

                if not online:
                    continue

                # Publish each numeric and bool field
                for k, v in data.items():
                    if k in self._SKIP_FIELDS:
                        continue
                    if isinstance(v, bool):
                        self._client.publish(
                            f"{base}/{k}",
                            "true" if v else "false",
                            retain=False,
                        )
                    elif isinstance(v, (int, float)):
                        self._client.publish(
                            f"{base}/{k}",
                            f"{v}",
                            retain=False,
                        )

            # Publish alarm summary
            alarms     = plant.get("alarms", [])
            crit_count = sum(1 for a in alarms if a.get("sev") == "CRIT")

            self._client.publish(
                f"{self._prefix}/alarms/count",
                str(len(alarms)),
                retain=False,
            )
            self._client.publish(
                f"{self._prefix}/alarms/crit_count",
                str(crit_count),
                retain=False,
            )

        except Exception as e:
            log.error("MQTT publish error: %s", e)

    def stop(self) -> None:
        """Clean shutdown — publish offline status before disconnecting."""
        if not self._enabled or self._client is None:
            return
        try:
            self._client.publish(
                f"{self._prefix}/server/status",
                "offline",
                retain=True,
            )
            self._client.loop_stop()
            self._client.disconnect()
            log.info("MQTT publisher stopped")
        except Exception as e:
            log.error("MQTT stop error: %s", e)
