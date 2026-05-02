"""
tank.py — ASCII Tank Level Widget
MORBION SCADA v02

Vertical representation of fluid storage levels.
"""

from textual.widgets import Static
from textual.app import RenderResult

class Tank(Static):
    """
    A vertical ASCII tank display.
    """
    DEFAULT_CSS = """
    Tank {
        width: 12;
        height: 12;
        padding: 0 1;
    }
    """

    def __init__(self, label: str, hi_alarm=90.0, lo_alarm=10.0, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.level = 0.0 # 0 to 100
        self.hi_alarm = hi_alarm
        self.lo_alarm = lo_alarm

    def update_level(self, pct: float):
        self.level = max(0.0, min(100.0, pct))
        self.refresh()

    def render(self) -> RenderResult:
        # 10 rows for the tank body
        height = 10
        filled_rows = int((self.level / 100.0) * height)
        
        color = "#00d4ff" # ACCENT
        if self.level >= self.hi_alarm:
            color = "#ff3333" # RED
        elif self.level <= self.lo_alarm:
            color = "#ffaa00" # AMBER

        lines = []
        lines.append("[white]┌──────┐[/]") # Top
        
        for i in range(height):
            # Check if this row is filled (from bottom up)
            row_idx = height - 1 - i
            if row_idx < filled_rows:
                content = f"[{color}]██████[/]"
            else:
                content = "      "
            lines.append(f"[white]│[/]{content}[white]│[/]")
            
        lines.append("[white]└──────┘[/]") # Bottom
        lines.append(f"[bold]{self.level:>5.1f}%[/]")
        
        return "\n".join(lines)
