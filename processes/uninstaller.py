"""
uninstaller.py - MORBION Processes Uninstaller
OOP implementation for cross-platform uninstallation.
Stops processes, removes services, cleans up directories.
"""

import os
import sys
import platform
import subprocess
import shutil
import yaml
from pathlib import Path
from typing import Dict


class ConfigManager:
    """Handles config.yaml read."""

    @staticmethod
    def load(config_path: str) -> Dict:
        """Load config from YAML file."""
        if not os.path.exists(config_path):
            return {}
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}


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


class ProcessStopper:
    """Stops all MORBION processes."""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def stop_all(self) -> bool:
        """Stop all running processes."""
        print("\n[Uninstaller] Stopping all processes...")

        processes = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]

        for proc_name in processes:
            self._stop_single_process(proc_name)

        print("[Uninstaller] All processes stopped")
        return True

    def _stop_single_process(self, proc_name: str) -> None:
        """Stop a single process."""
        os_type = OSDetector.detect()

        if os_type == "linux":
            try:
                subprocess.run(
                    ["pkill", "-f", f"{proc_name}/main.py"],
                    check=False
                )
                print(f"[Uninstaller] Stopped: {proc_name}")
            except Exception as e:
                print(f"[Uninstaller] Error stopping {proc_name}: {e}")

        elif os_type == "windows":
            try:
                subprocess.run(
                    ["powershell", "-Command", f"Get-Process -Name python* | Stop-Process -Force"],
                    check=False
                )
                print(f"[Uninstaller] Stopped: {proc_name}")
            except Exception as e:
                print(f"[Uninstaller] Error stopping {proc_name}: {e}")


class ServiceRemover:
    """Removes system services."""

    def __init__(self, os_type: str):
        self.os_type = os_type

    def remove_all_services(self, process_names: list) -> bool:
        """Remove all MORBION services."""
        print("\n[Uninstaller] Removing system services...")

        for name in process_names:
            self._remove_single_service(name)

        print("[Uninstaller] All services removed")
        return True

    def _remove_single_service(self, name: str) -> bool:
        """Remove a single service."""
        if self.os_type == "linux":
            service_name = f"morbion-{name.replace(' ', '-').lower()}"
            try:
                subprocess.run(["sudo", "systemctl", "stop", service_name], check=False)
                subprocess.run(["sudo", "systemctl", "disable", service_name], check=False)
                subprocess.run(
                    ["sudo", "rm", "-f", f"/etc/systemd/system/{service_name}.service"],
                    check=True
                )
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
                print(f"[Uninstaller] Removed service: {service_name}")
                return True
            except Exception as e:
                print(f"[Uninstaller] Error removing {service_name}: {e}")
                return False

        elif self.os_type == "windows":
            service_name = f"MORBION_{name.replace(' ', '_').upper()}"
            try:
                subprocess.run(["sc", "stop", service_name], check=False)
                subprocess.run(["sc", "delete", service_name], check=True)
                print(f"[Uninstaller] Removed service: {service_name}")
                return True
            except Exception as e:
                print(f"[Uninstaller] Error removing {service_name}: {e}")
                return False

        return False


class CleanupManager:
    """Handles cleanup of directories and files."""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def cleanup_logs(self) -> bool:
        """Delete logs directory."""
        log_dir = os.path.join(self.base_path, "logs")

        if not os.path.exists(log_dir):
            print("[Uninstaller] Logs directory does not exist")
            return True

        try:
            shutil.rmtree(log_dir)
            print(f"[Uninstaller] Removed logs directory: {log_dir}")
            return True
        except Exception as e:
            print(f"[Uninstaller] Error removing logs: {e}")
            return False

    def cleanup_config(self) -> bool:
        """Delete config.yaml."""
        config_path = os.path.join(self.base_path, "config.yaml")

        if not os.path.exists(config_path):
            return True

        try:
            os.remove(config_path)
            print(f"[Uninstaller] Removed config: {config_path}")
            return True
        except Exception as e:
            print(f"[Uninstaller] Error removing config: {e}")
            return False


class Uninstaller:
    """Cross-platform uninstaller for MORBION processes."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.os_type = OSDetector.detect()
        self.config = ConfigManager.load(os.path.join(base_path, "config.yaml"))

        self.process_stopper = ProcessStopper(base_path)
        self.service_remover = ServiceRemover(self.os_type)
        self.cleanup = CleanupManager(base_path)

    def run(self, remove_services: bool = True, cleanup_logs: bool = True, cleanup_config: bool = True) -> bool:
        """Run full uninstallation."""
        print("\n" + "=" * 60)
        print("  MORBION Processes Uninstaller")
        print(f"  Detected OS: {self.os_type}")
        print("=" * 60)

        self.process_stopper.stop_all()

        if remove_services and OSDetector.is_admin():
            process_names = [
                proc.get("folder", key)
                for key, proc in self.config.get("processes", {}).items()
                if proc.get("enabled", True)
            ]
            self.service_remover.remove_all_services(process_names)
        else:
            print("\n[Uninstaller] Skipping service removal (not admin or --no-services flag)")

        if cleanup_logs:
            self.cleanup.cleanup_logs()

        if cleanup_config:
            self.cleanup.cleanup_config()

        print("\n" + "=" * 60)
        print("  Uninstall complete!")
        print("=" * 60)

        return True


def main():
    """Main entry point."""
    base_path = os.path.dirname(os.path.abspath(__file__))

    remove_services = True
    cleanup_logs = True
    cleanup_config = True

    if len(sys.argv) > 1:
        if "--no-services" in sys.argv:
            remove_services = False
        if "--no-logs" in sys.argv:
            cleanup_logs = False
        if "--no-config" in sys.argv:
            cleanup_config = False

    uninstaller = Uninstaller(base_path)
    uninstaller.run(
        remove_services=remove_services,
        cleanup_logs=cleanup_logs,
        cleanup_config=cleanup_config
    )


if __name__ == "__main__":
    main()