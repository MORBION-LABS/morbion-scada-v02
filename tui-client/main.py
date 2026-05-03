"""
main.py — MORBION SCADA v02 TUI/CLI Client Entry Point
MORBION SCADA v02

Main menu. Choose TUI or CLI. Exit returns here.
Defensive: handles missing config, bad server, import errors.
"""

import os
import sys
import json
import asyncio

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS = {
    "server_host":       "",
    "server_port":       5000,
    "operator":          "OPERATOR",
    "poll_interval_s":   1.0,
    "history_file":      "~/.morbion_history",
    "verify_timeout_ms": 300,
}


def load_config() -> dict:
    """Load config.json. Falls back to defaults on any failure."""
    cfg = dict(DEFAULTS)
    if not os.path.exists(CONFIG_PATH):
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


# ── Server probe ──────────────────────────────────────────────────────────────

async def _probe_server(host: str, port: int) -> tuple:
    """
    Quick health check. Returns (online: bool, processes_online: int).
    Timeout 3s — menu must not hang.
    """
    if not host:
        return False, 0
    try:
        from core.rest_client import RestClient
        async with RestClient(host, port, timeout=3.0) as rest:
            health = await rest.get_health()
            if health is None:
                return False, 0
            n = health.get("processes_online", 0)
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = 0
            return True, n
    except Exception:
        return False, 0


def probe_server(host: str, port: int) -> tuple:
    """Synchronous wrapper around async probe."""
    try:
        return asyncio.run(_probe_server(host, port))
    except Exception:
        return False, 0


# ── Rich imports — degrade gracefully if not installed ────────────────────────

try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.text    import Text
    _RICH = True
    console = Console(highlight=False)
except ImportError:
    _RICH   = False
    console = None


def _print(text: str, colour: str = "#d0e8f0") -> None:
    """Print with Rich if available, else plain."""
    if _RICH and console:
        console.print(f"[{colour}]{text}[/{colour}]")
    else:
        print(text)


# ── Menu drawing ──────────────────────────────────────────────────────────────

def _draw_menu(config: dict, online: bool, n_online: int) -> None:
    """Draw the main menu to terminal."""
    host   = config.get("server_host") or "NOT CONFIGURED"
    port   = config.get("server_port", 5000)
    op     = config.get("operator", "OPERATOR")

    if online:
        status_str    = f"●ONLINE  {n_online}/4 processes"
        status_colour = "#00ff88"
    elif not config.get("server_host"):
        status_str    = "○NOT CONFIGURED — run installer.py"
        status_colour = "#ffaa00"
    else:
        status_str    = "○OFFLINE — server unreachable"
        status_colour = "#ff3333"

    if _RICH and console:
        console.clear()
        # Header
        console.print()
        console.print(
            "[#00d4ff]╔══════════════════════════════════════════════╗[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [bold #00d4ff]MORBION SCADA v02[/bold #00d4ff]"
            "                            "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [#4a7a8c]Intelligence. Precision. Vigilance.[/#4a7a8c]"
            "        "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]╠══════════════════════════════════════════════╣[/#00d4ff]"
        )
        console.print(
            f"[#00d4ff]║[/#00d4ff]"
            f"   [#4a7a8c]Server:  [/#4a7a8c][#d0e8f0]{host}:{port}[/#d0e8f0]"
            + " " * max(0, 20 - len(f"{host}:{port}")) +
            f"[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            f"[#00d4ff]║[/#00d4ff]"
            f"   [#4a7a8c]Status:  [/#4a7a8c]"
            f"[{status_colour}]{status_str}[/{status_colour}]"
            + " " * max(0, 23 - len(status_str)) +
            f"[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            f"[#00d4ff]║[/#00d4ff]"
            f"   [#4a7a8c]Operator:[/#4a7a8c] [#d0e8f0]{op}[/#d0e8f0]"
            + " " * max(0, 29 - len(op)) +
            f"[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]╠══════════════════════════════════════════════╣[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "                                              "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [#ffffff][1][/#ffffff]  "
            "[#d0e8f0]TUI  — Full-screen dashboard[/#d0e8f0]"
            "          "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [#ffffff][2][/#ffffff]  "
            "[#d0e8f0]CLI  — Scripting shell[/#d0e8f0]"
            "               "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [#ffffff][i][/#ffffff]  "
            "[#4a7a8c]Configure server address[/#4a7a8c]"
            "              "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "   [#ffffff][q][/#ffffff]  "
            "[#4a7a8c]Quit[/#4a7a8c]"
            "                                  "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]║[/#00d4ff]"
            "                                              "
            "[#00d4ff]║[/#00d4ff]"
        )
        console.print(
            "[#00d4ff]╚══════════════════════════════════════════════╝[/#00d4ff]"
        )
        console.print()
    else:
        # Plain fallback
        print()
        print("=" * 50)
        print("  MORBION SCADA v02")
        print("  Intelligence. Precision. Vigilance.")
        print("=" * 50)
        print(f"  Server:   {host}:{port}")
        print(f"  Status:   {status_str}")
        print(f"  Operator: {op}")
        print("=" * 50)
        print()
        print("  [1]  TUI  — Full-screen dashboard")
        print("  [2]  CLI  — Scripting shell")
        print("  [i]  Configure server address")
        print("  [q]  Quit")
        print()


# ── Mode launchers ────────────────────────────────────────────────────────────

def _launch_cli(config: dict) -> None:
    """Launch CLI shell. Blocks until user exits."""
    if not config.get("server_host"):
        _print(
            "  Server not configured. Press [i] to configure.",
            "#ffaa00"
        )
        input("  Press Enter to return to menu...")
        return
    try:
        from cli.shell import CLIShell
        shell = CLIShell(config)
        shell.run()
    except ImportError as e:
        _print(f"  CLI import error: {e}", "#ff3333")
        _print("  Run: pip install -r requirements.txt", "#ffaa00")
        input("  Press Enter to return to menu...")
    except Exception as e:
        _print(f"  CLI error: {e}", "#ff3333")
        input("  Press Enter to return to menu...")


def _launch_tui(config: dict) -> None:
    """Launch TUI dashboard. Blocks until user exits (Ctrl+Q)."""
    if not config.get("server_host"):
        _print(
            "  Server not configured. Press [i] to configure.",
            "#ffaa00"
        )
        input("  Press Enter to return to menu...")
        return
    try:
        from tui.app import MorbionTUI
        app = MorbionTUI(config=config)
        app.run()
    except ImportError as e:
        _print(f"  TUI import error: {e}", "#ff3333")
        _print("  Run: pip install -r requirements.txt", "#ffaa00")
        input("  Press Enter to return to menu...")
    except Exception as e:
        _print(f"  TUI error: {e}", "#ff3333")
        input("  Press Enter to return to menu...")


def _run_installer() -> dict:
    """Run installer inline and reload config."""
    try:
        import installer
        installer.main()
    except Exception as e:
        _print(f"  Installer error: {e}", "#ff3333")
    return load_config()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Main menu loop.
    Probes server on each menu draw.
    Dispatches to TUI or CLI.
    Returns on quit.
    Defensive: all branches wrapped, never crashes to traceback.
    """
    config = load_config()

    while True:
        # Probe server — non-blocking, timeout 3s
        host = config.get("server_host", "")
        port = config.get("server_port", 5000)

        if host:
            try:
                online, n_online = probe_server(host, int(port))
            except Exception:
                online, n_online = False, 0
        else:
            online, n_online = False, 0

        _draw_menu(config, online, n_online)

        # Input
        try:
            if _RICH and console:
                console.print("[#00d4ff]Choice:[/#00d4ff] ", end="")
            else:
                print("Choice: ", end="", flush=True)
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D or Ctrl+C at menu → clean exit
            _print("\n  Goodbye.", "#4a7a8c")
            sys.exit(0)
        except Exception:
            continue

        if choice in ("1", "tui"):
            _launch_tui(config)
            # Reload config in case it changed during session
            config = load_config()

        elif choice in ("2", "cli"):
            _launch_cli(config)
            config = load_config()

        elif choice in ("i", "install", "configure"):
            config = _run_installer()

        elif choice in ("q", "quit", "exit"):
            _print("  Goodbye.", "#4a7a8c")
            sys.exit(0)

        else:
            _print(
                f"  Unknown choice: {choice!r}. Press 1, 2, i, or q.",
                "#ffaa00"
            )
            try:
                input("  Press Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                _print("\n  Goodbye.", "#4a7a8c")
                sys.exit(0)


if __name__ == "__main__":
    main()
