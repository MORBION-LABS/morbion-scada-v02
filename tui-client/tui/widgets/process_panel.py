"""
tui/widgets/process_panel.py — Dashboard Process Quadrant Panel
MORBION SCADA v02

One of the four panels in the 2×2 dashboard grid.
Shows: status badge, key gauges, key values, fault state.
Updates from plant snapshot dict on every WS push.
Defensive: handles offline process, missing fields, None values.
"""

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich import box

_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"
_WHITE = "#ffffff"

# Per-process display config: list of (label, field, unit, hi_alarm, lo_alarm)
PROCESS_DISPLAY = {
    "pumping_station": {
        "title":    "PUMPING STATION",
        "location": "Nairobi Water",
        "gauges": [
            ("Tank",   "tank_level_pct",        "%",     90.0, 10.0),
            ("Flow",   "pump_flow_m3hr",         "m³/hr", None, None),
            ("Press",  "discharge_pressure_bar", "bar",   8.0,  None),
        ],
        "values": [
            ("Pump",   "pump_running",   ""),
            ("Fault",  "fault_text",     ""),
        ],
    },
    "heat_exchanger": {
        "title":    "HEAT EXCHANGER",
        "location": "KenGen Olkaria",
        "gauges": [
            ("Eff",    "efficiency_pct",  "%",   None, 45.0),
            ("T Hot",  "T_hot_in_C",      "°C",  200,  None),
            ("T Cold", "T_cold_out_C",    "°C",  95.0, None),
        ],
        "values": [
            ("Q Duty", "Q_duty_kW",  "kW"),
            ("Fault",  "fault_text", ""),
        ],
    },
    "boiler": {
        "title":    "BOILER",
        "location": "EABL/Bidco",
        "gauges": [
            ("Drum P", "drum_pressure_bar", "bar", 10.0, 6.0),
            ("Level",  "drum_level_pct",    "%",   80.0, 20.0),
            ("Steam",  "steam_flow_kghr",   "kg/h",None, None),
        ],
        "values": [
            ("Burner", "burner_text", ""),
            ("Fault",  "fault_text",  ""),
        ],
    },
    "pipeline": {
        "title":    "PIPELINE",
        "location": "Kenya Pipeline Co.",
        "gauges": [
            ("Outlet", "outlet_pressure_bar", "bar",   55.0, 30.0),
            ("Flow",   "flow_rate_m3hr",      "m³/hr", None, 200.0),
            ("Duty",   "duty_pump_running",   ""),
        ],
        "values": [
            ("Leak",   "leak_flag",  ""),
            ("Fault",  "fault_text", ""),
        ],
    },
}


def _gauge_bar(value: float, min_v: float, max_v: float,
               width: int, hi: float | None, lo: float | None) -> tuple[str, str]:
    """Render a compact inline gauge bar. Returns (bar_str, colour)."""
    rng = max_v - min_v
    if rng <= 0:
        rng = 1.0
    try:
        v = float(value) if value is not None else min_v
    except (TypeError, ValueError):
        v = min_v
    v     = max(min_v, min(max_v, v))
    ratio = (v - min_v) / rng
    filled = int(ratio * width)
    empty  = width - filled
    bar    = "█" * filled + "░" * empty

    if hi is not None and v >= hi:
        colour = _RED
    elif lo is not None and v <= lo:
        colour = _AMBER
    else:
        colour = _CYAN

    return bar, colour


def _fmt_value(field: str, val: object) -> tuple[str, str]:
    """Format a value for display. Returns (string, colour)."""
    if val is None:
        return "—", _DIM

    # Boolean fields
    if isinstance(val, bool):
        if field == "pump_running":
            return ("RUNNING ●", _GREEN) if val else ("STOPPED ○", _DIM)
        if field == "duty_pump_running":
            return ("RUNNING ●", _GREEN) if val else ("STOPPED ○", _DIM)
        if field == "leak_flag":
            return ("⚠ LEAK", _RED) if val else ("OK ●", _GREEN)
        return ("YES", _GREEN) if val else ("NO", _DIM)

    # String fields
    if isinstance(val, str):
        if field == "fault_text":
            return (val, _GREEN) if val == "OK" else (val, _RED)
        if field == "burner_text":
            colours = {"OFF": _DIM, "LOW": _AMBER, "HIGH": _RED}
            return val, colours.get(val, _TEXT)
        return val, _TEXT

    # Numeric
    try:
        return f"{float(val):.1f}", _WHITE
    except (TypeError, ValueError):
        return str(val), _TEXT


class ProcessPanel(Widget):
    """
    One dashboard quadrant for a single process.
    Call update_data(process_dict) on every WS push.
    """

    DEFAULT_CSS = """
    ProcessPanel {
        border: solid #0a2229;
        padding: 0 1;
        height: 100%;
    }
    ProcessPanel.fault {
        border: solid #ff3333;
    }
    ProcessPanel.warning {
        border: solid #ffaa00;
    }
    """

    def __init__(self, process_name: str, **kwargs):
        super().__init__(**kwargs)
        if process_name not in PROCESS_DISPLAY:
            raise ValueError(f"Unknown process: {process_name!r}")
        self._process = process_name
        self._cfg     = PROCESS_DISPLAY[process_name]
        self._data: dict = {}
        self._online     = False

    def update_data(self, data: dict | None) -> None:
        """
        Update panel from process snapshot dict.
        Defensive: None → offline display.
        """
        if not isinstance(data, dict):
            self._data   = {}
            self._online = False
        else:
            self._data   = data
            self._online = bool(data.get("online", False))

        # Update border class for fault state
        fault = self._data.get("fault_code", 0)
        self.remove_class("fault", "warning")
        if not self._online:
            self.add_class("warning")
        elif fault and fault != 0:
            self.add_class("fault")

        self.refresh()

    def render(self) -> Text:
        cfg    = self._cfg
        data   = self._data
        online = self._online
        w      = max(20, self.size.width - 4)

        text = Text()

        # ── Title + status badge ───────────────────────────────────────────
        title = cfg["title"]
        if online:
            fault = data.get("fault_code", 0)
            if fault and fault != 0:
                badge       = "⚠FAULT"
                badge_style = _RED
            else:
                badge       = "●ONLINE"
                badge_style = _GREEN
        else:
            badge       = "○OFFLINE"
            badge_style = _RED

        text.append(f"{title:<20}", style=_CYAN)
        text.append(f" {badge}\n", style=badge_style)
        text.append(f"{cfg['location']}\n", style=_DIM)
        text.append("─" * w + "\n", style=_DIM)

        if not online:
            text.append("  No data\n", style=_DIM)
            return text

        # ── Gauges ────────────────────────────────────────────────────────
        bar_w = max(8, w - 26)

        for label, field, unit, hi, lo in cfg["gauges"]:
            val = data.get(field)

            # Special: boolean gauge (pump running)
            if isinstance(val, bool):
                val_str, val_col = _fmt_value(field, val)
                text.append(f"  {label:<8}", style=_DIM)
                text.append(f" {val_str}\n", style=val_col)
                continue

            # Numeric gauge
            try:
                fval = float(val) if val is not None else 0.0
            except (TypeError, ValueError):
                fval = 0.0

            # Determine range from hi/lo alarm or defaults
            max_v = (hi * 1.2) if hi else 100.0
            min_v = 0.0

            bar, bar_col = _gauge_bar(fval, min_v, max_v, bar_w, hi, lo)

            val_col = bar_col
            try:
                val_str = f"{fval:>6.1f}"
            except Exception:
                val_str = "  —   "

            text.append(f"  {label:<8}", style=_DIM)
            text.append(f"[", style=_DIM)
            text.append(bar, style=bar_col)
            text.append(f"] ", style=_DIM)
            text.append(f"{val_str}", style=val_col)
            text.append(f" {unit}\n", style=_DIM)

        text.append("─" * w + "\n", style=_DIM)

        # ── Key values ────────────────────────────────────────────────────
        for label, field, unit in cfg["values"]:
            val              = data.get(field)
            val_str, val_col = _fmt_value(field, val)
            suffix           = f" {unit}" if unit else ""
            text.append(f"  {label:<8}", style=_DIM)
            text.append(f" {val_str}{suffix}\n", style=val_col)

        return text
