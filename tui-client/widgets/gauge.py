"""
gauge.py — Horizontal Bar Gauge
MORBION SCADA v02

Terminal-based progress bar for analog process values.
Changes color based on alarm thresholds.
"""

from textual.widgets import Static
from textual.app import RenderResult
from textual.geometry import Size

class Gauge(Static):
    """
    A horizontal gauge representing a value within a range.
    """
    
    def __init__(
        self, 
        label: str, 
        unit: str, 
        min_val: float = 0.0, 
        max_val: float = 100.0, 
        hi_alarm: float = None, 
        lo_alarm: float = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.label = label
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.hi_alarm = hi_alarm
        self.lo_alarm = lo_alarm
        self.value = 0.0

    def update_value(self, value: float):
        self.value = value
        self.refresh()

    def render(self) -> RenderResult:
        # Calculate percentage
        span = self.max_val - self.min_val
        if span <= 0: span = 1.0
        
        pct = (self.value - self.min_val) / span
        pct = max(0.0, min(1.0, pct))
        
        # Determine bar width based on widget size
        width = self.size.width - 20 # Account for labels
        if width < 10: width = 10
        
        filled_chars = int(pct * width)
        empty_chars = width - filled_chars
        
        # Determine Color
        color = "#00d4ff" # ACCENT (Cyan)
        if self.hi_alarm is not None and self.value >= self.hi_alarm:
            color = "#ff3333" # RED
        elif self.lo_alarm is not None and self.value <= self.lo_alarm:
            color = "#ffaa00" # AMBER

        bar = f"[{color}]" + "█" * filled_chars + "[/]" + " " * empty_chars
        
        # Format display string
        # [LABEL     ] [████████      ] 85.0 UNIT
        return f"{self.label.upper():<12} [white]│[/]{bar}[white]│[/] [bold]{self.value:>6.1f}[/] {self.unit}"

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return container.width
