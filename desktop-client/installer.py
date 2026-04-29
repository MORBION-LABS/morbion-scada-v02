"""
installer.py — MORBION SCADA Desktop Client Installer
MORBION SCADA v02

Interactive installer. Prompts for server IP and ports.
Writes config.json. Run once before first launch.
"""

import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "server_port": 5000,
    "operator":    "OPERATOR",
    "logo_path":   "MORBION__.png",
}


def prompt(label: str, default=None, cast=str) -> str:
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
    print("  MORBION SCADA v02 — Desktop Client Installer")
    print("═" * 52)
    print()

    # Load existing config if present
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
        "\n  Use default ports? (server=5000) [Y/n]: "
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

    logo_path = prompt(
        "Logo filename (must be in same directory as main.py)",
        default=existing.get("logo_path", DEFAULTS["logo_path"]),
    )

    config = {
        "server_host": server_host,
        "server_port": server_port,
        "operator":    operator,
        "logo_path":   logo_path,
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print()
    print("═" * 52)
    print("  Configuration saved.")
    print(f"  Server:   http://{server_host}:{server_port}")
    print(f"  Operator: {operator}")
    print(f"  Logo:     {logo_path}")
    print()
    print("  Run:  python main.py")
    print("═" * 52)
    print()


if __name__ == "__main__":
    main()
