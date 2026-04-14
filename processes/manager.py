"""
manager.py — MORBION Processes Central Manager
MORBION SCADA v02

KEY CHANGES FROM v01:
  - Shell scripts deleted entirely. This is the sole lifecycle manager.
  - Correct PID tracking via psutil — no more stale PID files
  - sys.executable used for Python path — works in any venv
  - Logs go to processes/logs/ directory
  - start/stop/restart/status/logs commands
  - Each process runs in its own subprocess with setsid
    so it survives manager exit
  - shared/ directory added to PYTHONPATH for ST runtime imports

Usage:
    sudo python3 manager.py start
    sudo python3 manager.py stop
    sudo python3 manager.py restart
    sudo python3 manager.py status
    sudo python3 manager.py logs
    sudo python3 manager.py logs -f
"""

import os
import sys
import time
import signal
import subprocess
import logging
from pathlib import Path
from typing import Optional

import yaml
import psutil

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("manager")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
LOG_DIR     = os.path.join(BASE_DIR, "logs")

# Each process folder has its main.py here
PROCESS_FOLDERS = {
    "pumping_station": os.path.join(BASE_DIR, "pumping_station"),
    "heat_exchanger":  os.path.join(BASE_DIR, "heat_exchanger"),
    "boiler":          os.path.join(BASE_DIR, "boiler"),
    "pipeline":        os.path.join(BASE_DIR, "pipeline"),
}

# Ports used by each process — for port-based health check
PROCESS_PORTS = {
    "pumping_station": 502,
    "heat_exchanger":  506,
    "boiler":          507,
    "pipeline":        508,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        log.error("Config not found: %s", CONFIG_PATH)
        log.error("Run: python3 installer.py")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def is_port_listening(port: int) -> bool:
    """Check if a TCP port is listening on this machine."""
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port == port and conn.status == "LISTEN":
                return True
    except (psutil.AccessDenied, PermissionError):
        # On some systems net_connections requires root
        # Fall back to socket check
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    return False


def get_pid_for_port(port: int) -> Optional[int]:
    """Find PID of process listening on given port."""
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port == port and conn.status == "LISTEN":
                return conn.pid
    except (psutil.AccessDenied, PermissionError):
        pass
    return None


def start_process(name: str, folder: str, log_dir: str) -> bool:
    """
    Start a single process.
    Uses setsid so process survives manager exit.
    Adds shared/ to PYTHONPATH for ST runtime imports.
    Returns True if started or already running.
    """
    port = PROCESS_PORTS[name]

    if is_port_listening(port):
        pid = get_pid_for_port(port)
        print(f"  [{name}] Already running on port {port} (PID {pid})")
        return True

    main_py = os.path.join(folder, "main.py")
    if not os.path.exists(main_py):
        print(f"  [{name}] ERROR: main.py not found at {main_py}")
        return False

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{name}.log")

    # Build environment — add shared/ to PYTHONPATH for ST runtime
    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH", "")
    shared_dir    = BASE_DIR   # processes/ dir contains shared/
    if shared_dir not in existing_path:
        env["PYTHONPATH"] = f"{shared_dir}:{existing_path}" if existing_path else shared_dir

    try:
        with open(log_path, "a") as log_file:
            proc = subprocess.Popen(
                [sys.executable, main_py],
                stdout     = log_file,
                stderr     = subprocess.STDOUT,
                cwd        = folder,
                env        = env,
                start_new_session = True,   # setsid equivalent
            )

        # Wait briefly and check process didn't immediately die
        time.sleep(0.5)
        if proc.poll() is not None:
            print(f"  [{name}] ERROR: Process exited immediately. Check log: {log_path}")
            return False

        # Wait for port to come up — up to 10 seconds
        for _ in range(20):
            if is_port_listening(port):
                pid = get_pid_for_port(port)
                print(f"  [{name}] Started on port {port} (PID {pid})")
                return True
            time.sleep(0.5)

        # Port not up but process running — may still be initialising
        print(f"  [{name}] Started (PID {proc.pid}) — port {port} not yet listening")
        return True

    except Exception as e:
        print(f"  [{name}] ERROR starting: {e}")
        return False


def stop_process(name: str) -> bool:
    """
    Stop a single process gracefully.
    Sends SIGTERM, waits 10 seconds, then SIGKILL if needed.
    Returns True if stopped or was not running.
    """
    port = PROCESS_PORTS[name]

    if not is_port_listening(port):
        print(f"  [{name}] Not running")
        return True

    pid = get_pid_for_port(port)
    if pid is None:
        print(f"  [{name}] Port {port} listening but cannot find PID")
        return False

    try:
        proc = psutil.Process(pid)

        # SIGTERM — ask nicely
        proc.terminate()

        # Wait up to 10 seconds
        for i in range(20):
            if not is_port_listening(port):
                print(f"  [{name}] Stopped cleanly")
                return True
            time.sleep(0.5)

        # SIGKILL — force
        print(f"  [{name}] Not responding to SIGTERM — sending SIGKILL")
        proc.kill()
        time.sleep(1)

        if not is_port_listening(port):
            print(f"  [{name}] Force stopped")
            return True
        else:
            print(f"  [{name}] ERROR: Failed to stop")
            return False

    except psutil.NoSuchProcess:
        print(f"  [{name}] Process already gone")
        return True
    except Exception as e:
        print(f"  [{name}] ERROR stopping: {e}")
        return False


def start_all(config: dict) -> bool:
    """Start all enabled processes."""
    log_dir    = os.path.join(BASE_DIR,
                              config.get("settings", {}).get("log_dir", "logs"))
    processes  = config.get("processes", {})

    print("\n" + "═" * 56)
    print("  MORBION SCADA v02 — Starting Processes")
    print("═" * 56)

    success = True
    for key, cfg in processes.items():
        if not cfg.get("enabled", True):
            print(f"  [{key}] Disabled in config — skipping")
            continue
        folder = PROCESS_FOLDERS.get(key)
        if folder is None:
            print(f"  [{key}] Unknown process — skipping")
            continue
        if not start_process(key, folder, log_dir):
            success = False
        time.sleep(0.3)

    print("═" * 56)
    return success


def stop_all(config: dict) -> bool:
    """Stop all processes."""
    processes = config.get("processes", {})

    print("\n" + "═" * 56)
    print("  MORBION SCADA v02 — Stopping Processes")
    print("═" * 56)

    success = True
    for key in processes:
        if not stop_process(key):
            success = False
        time.sleep(0.3)

    print("═" * 56)
    return success


def restart_all(config: dict) -> bool:
    """Restart all processes."""
    stop_all(config)
    time.sleep(2)
    return start_all(config)


def status_all(config: dict) -> None:
    """Print status of all processes."""
    processes = config.get("processes", {})

    print("\n" + "═" * 56)
    print("  MORBION SCADA v02 — Process Status")
    print("═" * 56)
    print(f"  {'NAME':<22} {'STATUS':<12} {'PORT':<8} {'PID'}")
    print("  " + "─" * 52)

    for key in processes:
        port    = PROCESS_PORTS.get(key, 0)
        running = is_port_listening(port)
        pid     = get_pid_for_port(port) if running else "—"
        status  = "RUNNING" if running else "STOPPED"
        marker  = "●" if running else "○"
        print(f"  {marker} {key:<21} {status:<12} {port:<8} {pid}")

    print("═" * 56)


def logs_all(config: dict, follow: bool = False, lines: int = 50) -> None:
    """Show logs from all processes."""
    log_dir   = os.path.join(BASE_DIR,
                             config.get("settings", {}).get("log_dir", "logs"))
    processes = list(config.get("processes", {}).keys())

    if follow:
        _follow_logs(log_dir, processes)
        return

    for key in processes:
        log_path = os.path.join(log_dir, f"{key}.log")
        if not os.path.exists(log_path):
            print(f"\n=== {key} — no log file ===")
            continue

        print(f"\n{'═' * 56}")
        print(f"  {key.upper()} — last {lines} lines")
        print(f"{'═' * 56}")

        with open(log_path) as f:
            all_lines = f.readlines()
            tail      = all_lines[-lines:] if len(all_lines) > lines else all_lines
            print("".join(tail), end="")


def _follow_logs(log_dir: str, processes: list) -> None:
    """Follow all process logs live. Ctrl+C to exit."""
    print("Following logs — Ctrl+C to stop\n")

    positions = {}
    for key in processes:
        path = os.path.join(log_dir, f"{key}.log")
        if os.path.exists(path):
            positions[key] = os.path.getsize(path)
        else:
            positions[key] = 0

    try:
        while True:
            for key in processes:
                path = os.path.join(log_dir, f"{key}.log")
                if not os.path.exists(path):
                    continue
                size = os.path.getsize(path)
                if size > positions[key]:
                    with open(path) as f:
                        f.seek(positions[key])
                        new_data = f.read()
                        if new_data:
                            for line in new_data.splitlines():
                                print(f"[{key[:4].upper()}] {line}")
                    positions[key] = size
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDetached from logs")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 manager.py <command>")
        print("Commands: start, stop, restart, status, logs, logs -f")
        sys.exit(1)

    command = sys.argv[1].lower()
    config  = load_config()

    if command == "start":
        success = start_all(config)
        sys.exit(0 if success else 1)

    elif command == "stop":
        success = stop_all(config)
        sys.exit(0 if success else 1)

    elif command == "restart":
        success = restart_all(config)
        sys.exit(0 if success else 1)

    elif command == "status":
        status_all(config)

    elif command == "logs":
        follow = len(sys.argv) > 2 and sys.argv[2] == "-f"
        logs_all(config, follow=follow)

    else:
        print(f"Unknown command: {command}")
        print("Commands: start, stop, restart, status, logs, logs -f")
        sys.exit(1)


if __name__ == "__main__":
    main()
