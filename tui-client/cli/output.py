"""
cli/output.py — MORBION CLI Rich Output Formatter
MORBION SCADA v02

Maps ExecutorResult style strings to Rich markup.
Single responsibility: take ExecutorResult lines and print them.
Never raises. Defensive against None, empty, malformed input.
"""

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box

# Singleton console — 256 colour, stderr=False
console = Console(highlight=False)

# Colour map — style string → Rich colour string
STYLE_MAP = {
    "normal": "#d0e8f0",
    "dim":    "#4a7a8c",
    "green":  "#00ff88",
    "red":    "#ff3333",
    "amber":  "#ffaa00",
    "cyan":   "#00d4ff",
    "white":  "#ffffff",
}


def print_result(result) -> None:
    """
    Print an ExecutorResult to terminal.
    Defensive: handles None result, empty lines, unknown styles.
    """
    if result is None:
        console.print("[#ff3333]ERROR: executor returned None[/#ff3333]")
        return

    lines = getattr(result, "lines", None)
    if not lines:
        return

    for item in lines:
        # Defensive: handle malformed tuples
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            text = str(item) if item else ""
            style_key = "normal"
        else:
            text, style_key = item[0], item[1]

        # Skip sentinels — handled by shell
        if isinstance(text, str) and text.startswith("__"):
            continue

        colour = STYLE_MAP.get(style_key, STYLE_MAP["normal"])
        safe_text = str(text) if text is not None else ""
        console.print(f"[{colour}]{safe_text}[/{colour}]")


def print_banner(server_host: str, server_port: int,
                 online: bool, processes_online: int) -> None:
    """Print the CLI session header."""
    status_colour = "#00ff88" if online else "#ff3333"
    status_text   = f"●ONLINE {processes_online}/4" if online else "○OFFLINE"
    console.print()
    console.print(
        f"[#00d4ff]MORBION SCADA v02[/#00d4ff] — "
        f"[#4a7a8c]Scripting Shell[/#4a7a8c]"
    )
    console.print(
        f"[#4a7a8c]Connected:[/#4a7a8c] "
        f"[#d0e8f0]{server_host}:{server_port}[/#d0e8f0]  "
        f"[{status_colour}]{status_text}[/{status_colour}]"
    )
    console.print(
        "[#4a7a8c]Type [/#4a7a8c]"
        "[#00d4ff]help[/#00d4ff]"
        "[#4a7a8c] for commands. "
        "Tab to complete. ↑↓ for history. "
        "[/#4a7a8c]"
        "[#00d4ff]exit[/#00d4ff]"
        "[#4a7a8c] to return to menu.[/#4a7a8c]"
    )
    console.print()


def print_watch_line(timestamp: str, process: str,
                     tag: str, value, unit: str) -> None:
    """Print a single watch output line."""
    try:
        val_str = str(value) if value is not None else "N/A"
    except Exception:
        val_str = "?"

    console.print(
        f"[#4a7a8c]{timestamp}[/#4a7a8c]  "
        f"[#00d4ff]{process:<25}[/#00d4ff]"
        f"[#d0e8f0]{tag:<35}[/#d0e8f0]"
        f"[#ffffff]{val_str}[/#ffffff]"
        f" [#4a7a8c]{unit}[/#4a7a8c]"
    )


def print_error(message: str) -> None:
    """Print a standalone error line."""
    if not message:
        return
    console.print(f"[#ff3333]ERROR: {message}[/#ff3333]")


def print_info(message: str) -> None:
    """Print a dim info line."""
    if not message:
        return
    console.print(f"[#4a7a8c]{message}[/#4a7a8c]")


def print_success(message: str) -> None:
    """Print a green success line."""
    if not message:
        return
    console.print(f"[#00ff88]{message}[/#00ff88]")


def print_warn(message: str) -> None:
    """Print an amber warning line."""
    if not message:
        return
    console.print(f"[#ffaa00]{message}[/#ffaa00]")
