#!/usr/bin/env python3
"""
desktop-client/installer.py - MORBION Desktop Client Installer
Prompts for Server Host IP, updates config.json
"""

import os
import sys
import json


class DesktopInstaller:
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
        print("  MORBION Desktop Client Installer")
        print("=" * 50)

        # Get Server Host IP (where SCADA server runs)
        server_host = input("Enter SCADA Server Host IP: ").strip()
        if not server_host:
            print("[-] Error: Server Host IP is required")
            return

        # Load and update config
        config = self.load_config()
        if "server" not in config:
            config["server"] = {}
        config["server"]["host"] = server_host
        self.save_config(config)

        print("\n[+] Installation complete!")
        print(f"    Config file: {self.config_path}")
        print(f"    Server Host: {server_host}")


if __name__ == "__main__":
    installer = DesktopInstaller()
    installer.run()