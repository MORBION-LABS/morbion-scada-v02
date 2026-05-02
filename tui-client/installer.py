"""
installer.py — MORBION SCADA TUI Client Installer
MORBION SCADA v02

Commissioning script to configure server connectivity.
Writes to config.json.
"""

import os
import json
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def main():
    print("\n" + "═" * 60)
    print("  MORBION SCADA v02 — TUI Client Installer")
    print("═" * 60)

    # Load existing config if present
    config = {"server_host": "", "server_port": 5000, "operator": "OPERATOR"}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config.update(json.load(f))
            print(f"  [+] Existing configuration found.")
        except Exception:
            pass

    # Prompt for Server IP
    host = input(f"  Enter SCADA Server IP [{config['server_host']}]: ").strip()
    if host:
        config["server_host"] = host
    
    if not config["server_host"]:
        print("  [-] Error: Server IP is required for operation.")
        sys.exit(1)

    # Prompt for Server Port
    port_raw = input(f"  Enter Server Port [{config['server_port']}]: ").strip()
    if port_raw:
        try:
            config["server_port"] = int(port_raw)
        except ValueError:
            print("  [-] Invalid port. Keeping default.")

    # Prompt for Operator Name
    op = input(f"  Enter Operator Name [{config['operator']}]: ").strip()
    if op:
        config["operator"] = op

    # Save configuration
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        print("\n  [+] Configuration saved to config.json")
        print(f"      Host: {config['server_host']}")
        print(f"      Port: {config['server_port']}")
        print(f"      Op:   {config['operator']}")
    except Exception as e:
        print(f"  [-] Failed to write config: {e}")
        sys.exit(1)

    print("\n  [!] Installation Complete. Run 'python main.py' to start.")
    print("═" * 60 + "\n")

if __name__ == "__main__":
    main()
