"""
main.py — MORBION SCADA Server Entry Point
MORBION SCADA v02

KEY CHANGES FROM v01:
  - MQTT publisher initialized and wired to broadcast loop
  - PLC runtimes passed to init_server() for PLC API endpoints
  - Alarm history updated on every broadcast cycle
  - plc_host validation before starting — fail fast with clear message
  - server_host defaults to 0.0.0.0 if not configured (listens on all)
"""

import json
import sys
import time
import threading
import logging
import argparse

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("morbion.main")


def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        log.critical("Config not found: %s", path)
        sys.exit(1)
    except json.JSONDecodeError as e:
        log.critical("Config invalid JSON: %s", e)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MORBION SCADA Server v2.0")
    parser.add_argument("--config", default="config.json")
    args   = parser.parse_args()
    config = load_config(args.config)

    # ── Validate required config ───────────────────────────────────────────────
    plc_host = config.get("plc_host", "").strip()
    if not plc_host:
        log.critical("plc_host not configured in %s", args.config)
        log.critical("Run: python3 installer.py")
        sys.exit(1)

    server_host = config.get("server_host", "0.0.0.0").strip()
    if not server_host:
        server_host = "0.0.0.0"
        log.warning("server_host not configured — defaulting to 0.0.0.0")

    server_port = config.get("server_port", 5000)
    poll_rate   = config.get("poll_rate_s",  1.0)

    print("━" * 64)
    print("  MORBION SCADA Server v2.0")
    print("  Intelligence. Precision. Vigilance.")
    print("━" * 64)
    print(f"  PLC host    : {plc_host}")
    print(f"  Poll rate   : {poll_rate}s")
    print(f"  Server host : {server_host}:{server_port}")
    print("━" * 64)

    # ── Historian ──────────────────────────────────────────────────────────────
    historian_writer = None
    influx_cfg = config.get("influxdb", {})
    if influx_cfg.get("enabled", False):
        try:
            from historian.client import HistorianClient
            from historian.writer import HistorianWriter
            hc = HistorianClient(
                url    = influx_cfg["url"],
                token  = influx_cfg["token"],
                org    = influx_cfg["org"],
                bucket = influx_cfg["bucket"],
            )
            historian_writer = HistorianWriter(hc)
            print("  InfluxDB    : connected")
        except Exception as e:
            print(f"  InfluxDB    : disabled ({e})")
    else:
        print("  InfluxDB    : disabled in config")

    # ── MQTT Publisher ─────────────────────────────────────────────────────────
    mqtt_publisher = None
    mqtt_cfg = config.get("mqtt", {})
    if mqtt_cfg.get("enabled", False):
        try:
            from mqtt.publisher import MQTTPublisher
            mqtt_publisher = MQTTPublisher(config)
            print(f"  MQTT        : connecting to "
                  f"{mqtt_cfg.get('host', 'localhost')}:"
                  f"{mqtt_cfg.get('port', 1883)}")
        except Exception as e:
            print(f"  MQTT        : disabled ({e})")
    else:
        print("  MQTT        : disabled in config")

    print("━" * 64)

    # ── Import server BEFORE threading ────────────────────────────────────────
    from server import app, init_server, broadcast, _update_alarm_history

    # ── Plant state ────────────────────────────────────────────────────────────
    from plant_state import PlantState
    state = PlantState()

    # ── Wire server to state and services ─────────────────────────────────────
    # PLC runtimes are in the processes — not directly accessible from the
    # server process. The PLC API endpoints work via Modbus writes.
    # plc_runtimes dict is empty here — processes run in separate PIDs.
    # For future single-process mode this dict would be populated.
    init_server(
        state          = state,
        plc_host       = plc_host,
        mqtt_publisher = mqtt_publisher,
        plc_runtimes   = {},
    )

    # ── Poller ─────────────────────────────────────────────────────────────────
    from poller import Poller
    poller = Poller(config, state, historian_writer)
    poller.start()

    # Allow one full poll cycle before opening Flask
    time.sleep(poll_rate + 0.5)

    # ── WebSocket broadcast loop ───────────────────────────────────────────────
    def ws_broadcast_loop():
        while True:
            try:
                snap    = state.snapshot()
                payload = json.dumps(snap)

                # Update alarm history before broadcast
                _update_alarm_history(snap.get("alarms", []))

                # Broadcast to all WebSocket clients
                broadcast(payload)

                # Publish to MQTT if enabled
                if mqtt_publisher is not None:
                    mqtt_publisher.publish_plant(snap)

            except Exception as e:
                log.error("Broadcast loop error: %s", e)

            time.sleep(poll_rate)

    threading.Thread(
        target = ws_broadcast_loop,
        name   = "MorbionWSBroadcast",
        daemon = True,
    ).start()

    print(f"  REST        : http://{server_host}:{server_port}/data")
    print(f"  WebSocket   : ws://{server_host}:{server_port}/ws")
    print(f"  Alarms      : http://{server_host}:{server_port}/data/alarms")
    print(f"  PLC API     : http://{server_host}:{server_port}/plc/<process>/program")
    print(f"  Health      : http://{server_host}:{server_port}/health")
    print("━" * 64)

    # ── Start Flask ────────────────────────────────────────────────────────────
    try:
        app.run(
            host         = server_host,
            port         = server_port,
            debug        = False,
            threaded     = True,
            use_reloader = False,
        )
    except KeyboardInterrupt:
        log.info("Server shutting down...")
    finally:
        if mqtt_publisher is not None:
            mqtt_publisher.stop()
        poller.stop()
        log.info("MORBION SCADA Server stopped")


if __name__ == "__main__":
    main()
