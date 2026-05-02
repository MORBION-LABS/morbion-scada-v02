"""
tui/widgets/tank.py — ASCII Vertical Tank Level
MORBION SCADA v02

Renders a vertical tank using box-drawing characters.
Fill colour: cyan normal, amber lo alarm, red hi alarm.
Defensive: clamped 0-100%, None value → 0.
"""

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

_CYAN  = "#00d4ff"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"


class TankWidget(Widget):
    """
    Vertical ASCII tank.
    Call set_level(pct, volume_m3) to update.
    """

    DEFAULT_CSS = """
    TankWidget {
        height: 12;
        width: 14;
    }
    """

    def __init__(
        self,
        label:    str   = "TANK",
        hi_alarm: float = 90.0,
        lo_alarm: float = 10.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.label     = label
        self.hi_alarm  = hi_alarm
        self.lo_alarm  = lo_alarm
        self._level    = 0.0
        self._volume   = 0.0

    def set_level(self, pct: float | None, volume_m3: float = 0.0) -> None:
        """Update tank level. Clamps 0-100. None → 0."""
        try:
            self._level = max(0.0, min(100.0, float(pct) if pct is not None else 0.0))
        except (TypeError, ValueError):
            self._level = 0.0
        try:
            self._volume = float(volume_m3) if volume_m3 is not None else 0.0
        except (TypeError, ValueError):
            self._volume = 0.0
        self.refresh()

    def render(self) -> Text:
        inner_h = 8   # rows inside tank walls
        inner_w = 10  # chars inside tank walls

        level   = self._level
        fill_rows = int((level / 100.0) * inner_h)
        fill_rows = max(0, min(inner_h, fill_rows))

        if level >= self.hi_alarm:
            colour = _RED
        elif level <= self.lo_alarm:
            colour = _AMBER
        else:
            colour = _CYAN

        text = Text()

        # Label
        text.append(f"{self.label:^{inner_w + 2}}\n", style=_DIM)

        # Top wall
        text.append("┌" + "─" * inner_w + "┐\n", style=_DIM)

        # Tank rows — top to bottom
        for row in range(inner_h, 0, -1):
            text.append("│", style=_DIM)
            if row <= fill_rows:
                # Filled row
                if row == fill_rows:
                    # Top of fill — show level text in middle
                    mid   = f"{level:>4.0f}%"
                    left  = (inner_w - len(mid)) // 2
                    right = inner_w - len(mid) - left
                    text.append("█" * left, style=colour)
                    text.append(mid, style=_TEXT)
                    text.append("█" * right, style=colour)
                else:
                    text.append("█" * inner_w, style=colour)
            else:
                text.append(" " * inner_w, style=_DIM)
            text.append("│\n", style=_DIM)

        # Bottom wall
        text.append("└" + "─" * inner_w + "┘\n", style=_DIM)

        # Volume
        text.append(f"{self._volume:>5.1f} m³".center(inner_w + 2), style=_DIM)

        return text
