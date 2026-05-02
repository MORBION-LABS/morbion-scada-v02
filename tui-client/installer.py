"""
installer.py — TUI Workstation Commissioning
MORBION SCADA v02 — REBOOT
"""
import json
import os

CONFIG_PATH = "config.json"

def run_installer():
    print("\n" + "═" * 60)
    print("  MORBION SCADA v02 — TUI WORKSTATION INSTALLER")
    print("═" * 60)

    # Load existing to provide defaults
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            cfg = json.load(f)
    else:
        cfg = {"server_host": "", "server_port": 5000, "operator": "OPERATOR_1", "refresh_rate": 1.0}

    host = input(f"  Enter SCADA Server IP [{cfg['server_host']}]: ").strip() or cfg['server_host']
    port = input(f"  Enter SCADA Server Port [{cfg['server_port']}]: ").strip() or cfg['server_port']
    op   = input(f"  Enter Operator Name [{cfg['operator']}]: ").strip() or cfg['operator']

    if not host:
        print("  [!] Error: Server Host cannot be empty.")
        return

    cfg['server_host'] = host
    cfg['server_port'] = int(port)
    cfg['operator'] = op

    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)

    print("\n  [+] Configuration Saved to config.json")
    print("  [+] Commissioning Complete.")
    print("═" * 60 + "\n")

if __name__ == "__main__":
    run_installer()
