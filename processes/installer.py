"""
installer.py - MORBION Processes Installer
OOP implementation for cross-platform installation.
Auto-detects OS, creates directories, generates config, optionally installs services.
"""

import os
import sys
import platform
import subprocess
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional


class ConfigManager:
    """Handles config.yaml read/write."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data: Dict = {}

    def load(self) -> Dict:
        """Load config from YAML file."""
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r") as f:
            self.data = yaml.safe_load(f) or {}
        return self.data

    def save(self, data: Dict) -> None:
        """Save config to YAML file."""
        with open(self.config_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)
        self.data = data


class OSDetector:
    """Detects the operating system."""

    @staticmethod
    def detect() -> str:
        """Detect OS: linux, windows, or unknown."""
        system = platform.system().lower()
        if system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        else:
            return "unknown"

    @staticmethod
    def is_admin() -> bool:
        """Check if running with admin/root privileges."""
        try:
            if OSDetector.detect() == "windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False


class ServiceManager:
    """Handles system service registration (systemd/sc)."""

    def __init__(self, os_type: str):
        self.os_type = os_type

    def create_service(self, process_name: str, process_folder: str, port: int, base_path: str) -> bool:
        """Create systemd service (Linux) or Windows Service."""
        if self.os_type == "linux":
            return self._create_systemd_service(process_name, process_folder, port, base_path)
        elif self.os_type == "windows":
            return self._create_windows_service(process_name, process_folder, port, base_path)
        else:
            print(f"[ServiceManager] Unsupported OS: {self.os_type}")
            return False

    def _create_systemd_service(self, name: str, folder: str, port: int, base_path: str) -> bool:
        """Create systemd service file."""
        service_name = f"morbion-{name.replace(' ', '-').lower()}"

        service_content = f"""[Unit]
Description=MORBION {name} Process (port {port})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={base_path}/{folder}
ExecStart={sys.executable} {base_path}/{folder}/main.py
Restart=on-failure
RestartSec=5
StandardOutput=append:{base_path}/logs/{folder}.log
StandardError=append:{base_path}/logs/{folder}.log

[Install]
WantedBy=multi-user.target
"""

        service_path = f"/etc/systemd/system/{service_name}.service"

        try:
            with open(service_path, "w") as f:
                f.write(service_content)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
            print(f"[ServiceManager] Created systemd service: {service_name}")
            return True
        except Exception as e:
            print(f"[ServiceManager] ERROR creating service: {e}")
            return False

    def _create_windows_service(self, name: str, folder: str, port: int, base_path: str) -> bool:
        """Create Windows Service using NSSM or sc."""
        service_name = f"MORBION_{name.replace(' ', '_').upper()}"
        exe_path = sys.executable
        script_path = os.path.join(base_path, folder, "main.py")

        try:
            cmd = [
                "sc", "create", service_name,
                "binPath=", f'"{exe_path}" "{script_path}"',
                "DisplayName=", f"MORBION {name}",
                "start=", "auto"
            ]
            subprocess.run(cmd, check=True)
            print(f"[ServiceManager] Created Windows service: {service_name}")
            return True
        except Exception as e:
            print(f"[ServiceManager] ERROR creating service: {e}")
            return False

    def remove_service(self, name: str) -> bool:
        """Remove systemd service (Linux) or Windows Service."""
        if self.os_type == "linux":
            service_name = f"morbion-{name.replace(' ', '-').lower()}"
            try:
                subprocess.run(["sudo", "systemctl", "stop", service_name], check=False)
                subprocess.run(["sudo", "systemctl", "disable", service_name], check=False)
                subprocess.run(["sudo", "rm", f"/etc/systemd/system/{service_name}.service"], check=True)
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
                print(f"[ServiceManager] Removed systemd service: {service_name}")
                return True
            except Exception as e:
                print(f"[ServiceManager] ERROR removing service: {e}")
                return False
        elif self.os_type == "windows":
            service_name = f"MORBION_{name.replace(' ', '_').upper()}"
            try:
                subprocess.run(["sc", "stop", service_name], check=False)
                subprocess.run(["sc", "delete", service_name], check=True)
                print(f"[ServiceManager] Removed Windows service: {service_name}")
                return True
            except Exception as e:
                print(f"[ServiceManager] ERROR removing service: {e}")
                return False
        return False


class Installer:
    """Cross-platform installer for MORBION processes."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.os_type = OSDetector.detect()
        self.service_manager = ServiceManager(self.os_type)
        self.config_manager = ConfigManager(os.path.join(base_path, "config.yaml"))

    def detect_os(self) -> str:
        """Get detected OS type."""
        return self.os_type

    def create_logs_dir(self) -> bool:
        """Create logs directory."""
        log_dir = os.path.join(self.base_path, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            print(f"[Installer] Created logs directory: {log_dir}")
            return True
        except Exception as e:
            print(f"[Installer] ERROR creating logs directory: {e}")
            return False

    def create_config(self) -> bool:
        """Generate default config.yaml if not exists."""
        config_path = os.path.join(self.base_path, "config.yaml")

        if os.path.exists(config_path):
            print(f"[Installer] Config already exists: {config_path}")
            return True

        default_config = {
            "processes": {
                "pumping_station": {
                    "name": "Pumping Station",
                    "description": "Nairobi Water Municipal Pumping Station",
                    "port": 502,
                    "enabled": True,
                    "folder": "pumping_station"
                },
                "heat_exchanger": {
                    "name": "Heat Exchanger",
                    "description": "KenGen Olkaria Geothermal Heat Recovery",
                    "port": 506,
                    "enabled": True,
                    "folder": "heat_exchanger"
                },
                "boiler": {
                    "name": "Boiler",
                    "description": "EABL/Bidco Industrial Steam Generation",
                    "port": 507,
                    "enabled": True,
                    "folder": "boiler"
                },
                "pipeline": {
                    "name": "Pipeline",
                    "description": "Kenya Pipeline Co. Petroleum Transfer",
                    "port": 508,
                    "enabled": True,
                    "folder": "pipeline"
                }
            },
            "settings": {
                "log_dir": "logs",
                "scan_interval_ms": 100,
                "auto_restart_on_failure": False,
                "log_lines": 50
            }
        }

        try:
            self.config_manager.save(default_config)
            print(f"[Installer] Created config file: {config_path}")
            return True
        except Exception as e:
            print(f"[Installer] ERROR creating config: {e}")
            return False

    def install_services(self) -> bool:
        """Install systemd/Windows services for all processes."""
        if not OSDetector.is_admin():
            print("[Installer] Admin privileges required. Run as sudo/Administrator.")
            print("[Installer] Skipping service installation.")
            return False

        print("\n" + "=" * 50)
        print("  Installing system services (requires sudo/admin)")
        print("=" * 50)

        config = self.config_manager.load()
        processes = config.get("processes", {})

        success = True
        for key, proc in processes.items():
            if proc.get("enabled", True):
                result = self.service_manager.create_service(
                    name=proc.get("name", key),
                    process_folder=proc.get("folder", key),
                    port=proc.get("port", 5000),
                    base_path=self.base_path
                )
                if not result:
                    success = False

        print("=" * 50)
        return success

    def run(self) -> None:
        """Run installation."""
        print("\n" + "=" * 50)
        print("  MORBION Processes Installer")
        print("=" * 50)

        # Get PLC Host IP
        plc_host = input("Enter PLC Host IP: ").strip()
        if not plc_host:
            print("[-] Error: PLC Host IP is required")
            return

        # Get Server Host IP
        server_host = input("Enter SCADA Server Host IP: ").strip()
        if not server_host:
            print("[-] Error: Server Host IP is required")
            return

        # Load existing config
        config = self.config_manager.load()
        if "settings" not in config:
            config["settings"] = {}

        # Update with user input
        config["settings"]["plc_host"] = plc_host
        config["settings"]["server_host"] = server_host

        # Save
        self.config_manager.save(config)

        self.create_logs_dir()

        print("\n[+] Installation complete!")
        print("    Logs directory: logs/")
        print("    Config file: config.yaml")
        print(f"    PLC Host: {plc_host}")
        print(f"    Server Host: {server_host}")


def main():
    """Main entry point."""
    base_path = os.path.dirname(os.path.abspath(__file__))

    installer = Installer(base_path)
    installer.run()

    sys.exit(0)


if __name__ == "__main__":
    main()