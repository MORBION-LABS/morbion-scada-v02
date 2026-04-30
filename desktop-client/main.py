"""
main.py — MORBION SCADA Desktop Client Entry Point
MORBION SCADA v02

KEY FIX FROM v01:
  v01 had `host` referenced in load_config() default return
  before it was defined. This caused NameError on missing config.
  v02 uses empty string default and validates in MorbionMainWindow.
"""

"""
main.py — MORBION SCADA Desktop Client Entry Point
MORBION SCADA v02
"""

import sys
import json
import os
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    defaults = {
        "server_host": "192.168.100.30",
        "server_port": 5000,
        "operator":    "OPERATOR",
    }
    if not os.path.exists(CONFIG_PATH):
        return defaults
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        defaults.update(data)
        return defaults
    except Exception:
        return defaults


def save_config(config: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MORBION SCADA v02")

    config = load_config()

    # Import here — after QApplication created
    from splash import SplashScreen
    splash = SplashScreen(config, save_config)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
