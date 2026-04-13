#!/usr/bin/env python3
"""
server/installer.py - MORBION SCADA Server Installer
Prompts for PLC Host IP and Server Host IP, updates config.json
"""

import os
import sys
import json
import platform


class ServerInstaller:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_path, "config.json")

    def load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r") as f:
            return json.load(f)

    def save_config(self, data: dict) -> None:
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def run(self) -> None:
        print("\n" + "=" * 50)
        print("  MORBION SCADA Server Installer")
        print("=" * 50)

        # Get PLC Host IP
        plc_host = input("Enter PLC Host IP: ").strip()
        if not plc_host:
            print("[-] Error: PLC Host IP is required")
            return

        # Get Server Host IP
        server_host = input("Enter Server Host IP: ").strip()
        if not server_host:
            print("[-] Error: Server Host IP is required")
            return

        # Load and update config
        config = self.load_config()
        config["plc_host"] = plc_host
        config["server_host"] = server_host
        self.save_config(config)

        print("\n[+] Installation complete!")
        print(f"    Config file: {self.config_path}")
        print(f"    PLC Host: {plc_host}")
        print(f"    Server Host: {server_host}")


if __name__ == "__main__":
    installer = ServerInstaller()
    installer.run()