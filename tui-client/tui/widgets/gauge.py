"""
tui/widgets/gauge.py — Horizontal Bar Gauge
MORBION SCADA v02

Renders a labelled horizontal bar gauge using Unicode blocks.
Colour: cyan normal, amber lo alarm, red hi alarm.
Defensive: handles None values, zero ranges, negative inputs.
"""

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text


# Colour constants — exact hex from theme
_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"

# Block chars for sub-character resolution
_BLOCKS = " ▏▎▍▌▋▊▉█"


def _render_bar(
    value: float,
    min_val: float,
    max_val: float,
    width: int,
    hi_alarm: float | None,
    lo_alarm: float | None,
) -> tuple[str, str]:
    """
    Render a bar of `width` chars.
    Returns (bar_string, colour_hex).
    Defensive: clamps value, handles zero/negative range.
    """
    # Defensive range
    rng = max_val - min_val
    if rng <= 0:
        rng = 1.0

    value = max(min_val, min(max_val, value if value is not None else min_val))

    ratio   = (value - min_val) / rng
    ratio   = max(0.0, min(1.0, ratio))
    filled  = ratio * width

    full_blocks = int(filled)
    remainder   = filled - full_blocks
    partial_idx = int(remainder * 8)

    bar = "█" * full_blocks
    if full_blocks < width:
        bar += _BLOCKS[partial_idx]
        bar += " " * (width - full_blocks - 1)

    bar = bar[:width]   # defensive truncate

    # Colour
    if hi_alarm is not None and value >= hi_alarm:
        colour = _RED
    elif lo_alarm is not None and value <= lo_alarm:
        colour = _AMBER
    else:
        colour = _CYAN

    return bar, colour


class GaugeWidget(Widget):
    """
    Horizontal bar gauge.

    Props (set after construction):
        label    : str
        unit     : str
        min_val  : float
        max_val  : float
        hi_alarm : float | None
        lo_alarm : float | None
        value    : float
    """

    DEFAULT_CSS = """
    GaugeWidget {
        height: 3;
        padding: 0 1;
    }
    """

    value: reactive[float] = reactive(0.0)

    def __init__(
        self,
        label:    str,
        unit:     str   = "",
        min_val:  float = 0.0,
        max_val:  float = 100.0,
        hi_alarm: float | None = None,
        lo_alarm: float | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.label    = label
        self.unit     = unit
        self.min_val  = min_val
        self.max_val  = max_val
        self.hi_alarm = hi_alarm
        self.lo_alarm = lo_alarm

    def set_value(self, v: float | None) -> None:
        """Safely set value. None becomes min_val."""
        try:
            self.value = float(v) if v is not None else self.min_val
        except (TypeError, ValueError):
            self.value = self.min_val

    def render(self) -> Text:
        w         = max(4, self.size.width - 2)
        bar_width = max(4, w - 28)   # leave room for label + value

        bar, colour = _render_bar(
            self.value, self.min_val, self.max_val,
            bar_width, self.hi_alarm, self.lo_alarm,
        )

        val_colour = colour   # value inherits alarm colour

        text = Text()
        text.append(f"{self.label[:16]:<16} ", style=_DIM)
        text.append(f"[", style=_DIM)
        text.append(bar, style=colour)
        text.append(f"] ", style=_DIM)
        text.append(f"{self.value:>7.1f}", style=val_colour)
        text.append(f" {self.unit}", style=_DIM)
        return text
