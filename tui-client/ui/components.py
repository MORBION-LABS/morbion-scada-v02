"""
components.py — Mythic Visual Architecture
MORBION SCADA v02 — REBOOT
"""
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from .styles import ACCENT, SAFE, DANGER, DIM

class UIComponents:
    @staticmethod
    def create_status_header(state):
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(
            Text(f" ◈ MORBION COMMAND STATION v02", style=f"bold {ACCENT}"),
            Text(f"SCAN: {state.get('poll_count', 0)} | {state.get('server_time', 'OFFLINE')} ", style=SAFE)
        )
        return Panel(grid, border_style=ACCENT, box=None)

    @staticmethod
    def create_process_card(name, data):
        """High-density data matrix for a single process."""
        if not data.get("online"):
            return Panel(Align.center(Text(f"\n{name.upper()}\nOFFLINE", style=DANGER)), border_style=DANGER)

        table = Table(box=None, expand=True, padding=(0,1))
        table.add_column("TAG", style=DIM)
        table.add_column("VALUE", justify="right", style="bold white")
        
        skip = ["online", "process", "label", "location", "port", "fault_text", "burner_text"]
        for k, v in data.items():
            if k in skip: continue
            color = SAFE if v != 0 else DIM
            if "fault" in k and v != 0: color = DANGER
            table.add_row(k.replace("_"," ").upper(), Text(str(v), style=color))

        return Panel(table, title=f"[bold {ACCENT}]{data.get('label', name).upper()}[/]", border_style=ACCENT)
