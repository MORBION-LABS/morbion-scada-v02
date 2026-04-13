"""
MORBION SCADA Server — Entry Point v3.0 fixed
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args   = parser.parse_args()
    config = load_config(args.config)

    print("━" * 64)
    print("  MORBION SCADA Server v3.0")
    print("  Intelligence. Precision. Vigilance.")
    print("━" * 64)
    print(f"  PLC host    : {config['plc_host']}")
    print(f"  Poll rate   : {config['poll_rate_s']}s")
    print(f"  Server port : {config['server_port']}")
    print("━" * 64)

    # ── Historian ─────────────────────────────────────────────────────────────
    historian_writer = None
    if config.get("influxdb", {}).get("enabled"):
        try:
            from historian.historian import HistorianClient, HistorianWriter
            hc = HistorianClient(
                url    = config["influxdb"]["url"],
                token  = config["influxdb"]["token"],
                org    = config["influxdb"]["org"],
                bucket = config["influxdb"]["bucket"],
            )
            historian_writer = HistorianWriter(hc)
            print("  InfluxDB    : connected")
        except Exception as e:
            print(f"  InfluxDB    : disabled ({e})")
    else:
        print("  InfluxDB    : disabled in config")

    print("━" * 64)

    # ── Import server FIRST so _ws_clients is initialized ────────────────────
    # Critical: import before any thread touches broadcast()
    from server import app, init_server, broadcast

    # ── Plant state ───────────────────────────────────────────────────────────
    from plant_state import PlantState
    state = PlantState()

    # ── Wire server to state ──────────────────────────────────────────────────
    init_server(state, config["plc_host"])

    # ── Poller ────────────────────────────────────────────────────────────────
    from poller import Poller
    poller = Poller(config, state, historian_writer)
    poller.start()

    # Allow one full poll cycle to complete before opening Flask
    time.sleep(config["poll_rate_s"] + 0.5)

    # ── WS broadcast thread ───────────────────────────────────────────────────
    # Only starts AFTER server is imported and init_server() called
    poll_rate = config["poll_rate_s"]

    def ws_broadcast_loop():
        while True:
            try:
                broadcast(json.dumps(state.snapshot()))
            except Exception as e:
                log.error("WS broadcast error: %s", e)
            time.sleep(poll_rate)

    threading.Thread(
        target  = ws_broadcast_loop,
        name    = "MorbionWSBroadcast",
        daemon  = True,
    ).start()

    print(f"  REST        : http://{config['server_host']}:{config['server_port']}/data")
    print(f"  WebSocket   : ws://{config['server_host']}:{config['server_port']}/ws")
    print(f"  Control     : POST /control")
    print("━" * 64)

    app.run(
        host         = config["server_host"],
        port         = config["server_port"],
        debug        = False,
        threaded     = True,
        use_reloader = False,
    )


if __name__ == "__main__":
    main()