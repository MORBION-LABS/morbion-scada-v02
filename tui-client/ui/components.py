"""
components.py — Mythic UI Building Blocks
MORBION SCADA v02 — REBOOT
"""
from rich.table import Table
from rich.panel import Panel
from rich.progress import ProgressBar
from rich.console import Group
from rich.text import Text
from .styles import ACCENT, SAFE, DANGER, WARN, DIM

class UIComponents:

    @staticmethod
    def create_gauge(label, value, min_val, max_val, unit="", hi=None, lo=None):
        """Standard horizontal industrial gauge."""
        color = SAFE
        if hi and value >= hi: color = DANGER
        elif lo and value <= lo: color = WARN
        
        # Build progress bar
        pb = ProgressBar(total=max_val, completed=value, width=30, pulse=False, 
                         style=f"dim {DIM}", complete_style=color)
        
        return Table.grid(expand=True).add_row(
            Text(f"{label:<18}", style=f"bold {ACCENT}"),
            pb,
            Text(f" {value:>7.1f} {unit}", style="white")
        )

    @staticmethod
    def create_tank(label, level_pct):
        """Vertical ASCII Tank representation."""
        color = SAFE
        if level_pct > 90: color = DANGER
        elif level_pct < 10: color = WARN
        
        filled = int(level_pct / 10)
        lines = []
        for i in range(10, 0, -1):
            char = "█" if filled >= i else " "
            lines.append(f"[white]│ [/{color}{char*6}[/][white] │[/]")
        
        body = "\n".join(lines)
        return Panel(
            Group(
                Text(body, justify="center"),
                Text(f" {level_pct:.1f}%", style=f"bold {color}", justify="center")
            ),
            title=f"[bold]{label}[/]", border_style=ACCENT, width=14
        )

    @staticmethod
    def create_register_table(process_name, data):
        """High-density full register dump."""
        table = Table(title=f"RAW DATA: {process_name.upper()}", 
                      box=None, expand=True, header_style=f"bold {ACCENT}")
        table.add_column("TAG", style=DIM)
        table.add_column("VALUE", justify="right", style="bold white")
        table.add_column("UNIT", style=ACCENT)

        # Iterate through all data keys
        # We skip metadata like 'online', 'process', 'label', 'port'
        skip = ["online", "process", "label", "location", "port", "fault_text", "burner_text"]
        
        for key, val in data.items():
            if key in skip: continue
            
            # Clean key name for display
            clean_key = key.replace("_", " ").upper()
            
            # Logic-based coloring (Faults/Booleans)
            val_str = str(val)
            if isinstance(val, bool):
                val_str = "[bold #00ff88]TRUE[/]" if val else "[dim]FALSE[/]"
            if "fault" in key and val != 0:
                val_str = f"[bold {DANGER}]{val}[/]"

            table.add_row(clean_key, val_str, "")
            
        return Panel(table, border_style=DIM)

    @staticmethod
    def create_status_header(plant_data):
        """Global status line (Server health + Count)."""
        time = plant_data.get("server_time", "OFFLINE")
        count = plant_data.get("poll_count", 0)
        rate = plant_data.get("poll_rate_ms", 0.0)
        
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="center")
        grid.add_column(justify="right")
        
        grid.add_row(
            Text(f" ◈ MORBION WORKSTATION v02", style=f"bold {ACCENT}"),
            Text(f"TIME: {time}", style=DIM),
            Text(f"SCAN: {count} | RATE: {rate:.1f}ms ", style=SAFE)
        )
        return Panel(grid, border_style=ACCENT, padding=(0,1))
