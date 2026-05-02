"""
tui/widgets/sparkline.py — Rolling Sparkline
MORBION SCADA v02

120-point rolling sparkline rendered as Unicode Braille or block chars.
Colour: cyan normal, amber lo alarm, red hi alarm.
Defensive: empty data, None pushes, zero range.
"""

from collections import deque
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

_CYAN  = "#00d4ff"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_WHITE = "#ffffff"

# 8-level block chars for vertical resolution
_SPARKS = "▁▂▃▄▅▆▇█"


class SparklineWidget(Widget):
    """
    Rolling sparkline with label, current value, and alarm markers.

    Call push(value) to add a data point.
    """

    DEFAULT_CSS = """
    SparklineWidget {
        height: 4;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        label:      str,
        unit:       str   = "",
        max_points: int   = 120,
        hi_alarm:   float | None = None,
        lo_alarm:   float | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.label      = label
        self.unit       = unit
        self.hi_alarm   = hi_alarm
        self.lo_alarm   = lo_alarm
        self._data: deque[float] = deque(maxlen=max(10, max_points))
        self._last: float | None = None

    def push(self, value: float | None) -> None:
        """Add a data point. None is silently ignored."""
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        self._data.append(v)
        self._last = v
        self.refresh()

    def render(self) -> Text:
        data  = list(self._data)
        last  = self._last
        w     = max(10, self.size.width - 2)

        # Value colour
        if last is None:
            val_str    = "—"
            val_colour = _DIM
        else:
            val_str = f"{last:.1f}"
            if self.hi_alarm is not None and last >= self.hi_alarm:
                val_colour = _RED
            elif self.lo_alarm is not None and last <= self.lo_alarm:
                val_colour = _AMBER
            else:
                val_colour = _WHITE

        text = Text()

        # Header row: label + value
        header = f"{self.label[:20]:<20}"
        text.append(header, style=_DIM)
        text.append(f" {val_str}", style=val_colour)
        text.append(f" {self.unit}\n", style=_DIM)

        # Sparkline row
        if len(data) < 2:
            text.append("─" * w, style=_DIM)
            return text

        mn  = min(data)
        mx  = max(data)
        rng = mx - mn
        if rng < 0.001:
            rng = 1.0

        # How many chars to render
        n_chars = min(len(data), w)
        subset  = data[-n_chars:]

        spark_colour = val_colour if last is not None else _CYAN

        spark_line = ""
        for v in subset:
            ratio = max(0.0, min(1.0, (v - mn) / rng))
            idx   = int(ratio * 7)
            spark_line += _SPARKS[idx]

        # Pad left if shorter than width
        if len(spark_line) < w:
            text.append(" " * (w - len(spark_line)), style=_DIM)

        text.append(spark_line, style=spark_colour)

        # Alarm threshold markers
        if self.hi_alarm is not None or self.lo_alarm is not None:
            text.append("\n", style=_DIM)
            hi_str = f"▲{self.hi_alarm}" if self.hi_alarm is not None else ""
            lo_str = f"▼{self.lo_alarm}" if self.lo_alarm is not None else ""
            marker = f"{lo_str}  {hi_str}"
            text.append(f"{marker[:w]}", style=_DIM)

        return text
