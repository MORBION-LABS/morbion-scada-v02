"""
installer.py — MORBION TUI/CLI Client Installer
MORBION SCADA v02

Prompts for server address and operator name.
Writes config.json. Run once before first launch.
"""

import os
import json
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "server_port":      5000,
    "operator":         "OPERATOR",
    "poll_interval_s":  1.0,
    "history_file":     "~/.morbion_history",
    "verify_timeout_ms": 300,
}


def prompt(label: str, default=None, cast=str):
    if default is not None:
        raw = input(f"  {label} [{default}]: ").strip()
        if not raw:
            return default
    else:
        raw = ""
        while not raw:
            raw = input(f"  {label}: ").strip()
    try:
        return cast(raw)
    except Exception:
        return default


def main():
    print()
    print("═" * 52)
    print("  MORBION SCADA v02 — TUI/CLI Client Installer")
    print("═" * 52)
    print()

    existing = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                existing = json.load(f)
            print("  Existing config found — press Enter to keep values.\n")
        except Exception:
            pass

    server_host = prompt(
        "SCADA Server IP",
        default=existing.get("server_host") or None,
    )

    use_defaults = input(
        "\n  Use default port? (5000) [Y/n]: "
    ).strip().lower()

    if use_defaults in ("n", "no"):
        server_port = prompt(
            "Server port",
            default=existing.get("server_port", DEFAULTS["server_port"]),
            cast=int,
        )
    else:
        server_port = DEFAULTS["server_port"]

    operator = prompt(
        "Operator name (for alarm acknowledgment)",
        default=existing.get("operator", DEFAULTS["operator"]),
    )

    config = {
        "server_host":       server_host,
        "server_port":       server_port,
        "operator":          operator,
        "poll_interval_s":   existing.get("poll_interval_s",   DEFAULTS["poll_interval_s"]),
        "history_file":      existing.get("history_file",      DEFAULTS["history_file"]),
        "verify_timeout_ms": existing.get("verify_timeout_ms", DEFAULTS["verify_timeout_ms"]),
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print()
    print("═" * 52)
    print("  Configuration saved.")
    print(f"  Server:   http://{server_host}:{server_port}")
    print(f"  Operator: {operator}")
    print()
    print("  Run:  python main.py")
    print("═" * 52)
    print()


if __name__ == "__main__":
    main()
