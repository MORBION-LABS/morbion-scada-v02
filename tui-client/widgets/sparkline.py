"""
sparkline.py — Terminal Trend Sparkline
MORBION SCADA v02

Uses Unicode block characters to show a rolling history of values.
"""

from collections import deque
from textual.widgets import Static
from textual.app import RenderResult

class Sparkline(Static):
    """
    A rolling trend line for terminal displays.
    """
    BLOCKS = "  ▂ ▃ ▄ ▅ ▆ ▇ █"

    def __init__(self, label: str, max_points: int = 40, hi_alarm=None, lo_alarm=None, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.data = deque(maxlen=max_points)
        self.hi_alarm = hi_alarm
        self.lo_alarm = lo_alarm

    def push(self, value: float):
        """Add a new data point to the trend."""
        self.data.append(value)
        self.refresh()

    def render(self) -> RenderResult:
        if not self.data:
            return f"{self.label.upper()}: [dim]NO DATA[/]"

        # Scale data to block character indices (0-8)
        min_v = min(self.data)
        max_v = max(self.data)
        span = max_v - min_v
        if span <= 0: span = 1.0

        line_chars = []
        for v in self.data:
            # Determine color for this specific point
            color = "#00d4ff" # ACCENT
            if self.hi_alarm is not None and v >= self.hi_alarm:
                color = "#ff3333" # RED
            elif self.lo_alarm is not None and v <= self.lo_alarm:
                color = "#ffaa00" # AMBER
            
            # Map value to block index
            idx = int(((v - min_v) / span) * (len(self.BLOCKS) - 1))
            line_chars.append(f"[{color}]{self.BLOCKS[idx]}[/]")

        spark = "".join(line_chars)
        last_val = self.data[-1]
        
        return f"{self.label.upper():<12} {spark} [bold]{last_val:>6.1f}[/]"
