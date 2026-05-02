"""
tui/screens/trends.py — Historical Trends Screen
MORBION SCADA v02

Multi-process rolling sparklines — 120-point history.
Updates on every WS push.
Two columns: left = PS + HX, right = Boiler + Pipeline.
Defensive: None pushes, missing fields.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.binding import Binding

from tui.widgets.sparkline import SparklineWidget
from core.commands import PROCESS_NAMES

_CYAN = "#00d4ff"
_DIM  = "#4a7a8c"

# All sparklines: (process, label, field, unit, hi, lo)
TREND_SPECS = {
    "left": [
        ("pumping_station","Tank Level",  "tank_level_pct",        "%",    90.0,10.0),
        ("pumping_station","Pump Flow",   "pump_flow_m3hr",         "m³/hr",None,None),
        ("pumping_station","Discharge P", "discharge_pressure_bar", "bar",  8.0, None),
        ("heat_exchanger", "Efficiency",  "efficiency_pct",         "%",    None,45.0),
        ("heat_exchanger", "T Cold Out",  "T_cold_out_C",           "°C",   95.0,None),
        ("heat_exchanger", "Q Duty",      "Q_duty_kW",              "kW",   None,None),
    ],
    "right": [
        ("boiler",  "Drum Pressure", "drum_pressure_bar", "bar",   10.0, 6.0),
        ("boiler",  "Drum Level",    "drum_level_pct",   "%",     80.0,20.0),
        ("boiler",  "Steam Flow",    "steam_flow_kghr",  "kg/hr", None, None),
        ("pipeline","Outlet P",      "outlet_pressure_bar","bar",  55.0,30.0),
        ("pipeline","Flow Rate",     "flow_rate_m3hr",   "m³/hr", None,200.0),
        ("pipeline","Duty Speed",    "duty_pump_speed_rpm","RPM",  None, None),
    ],
}


class TrendsScreen(Screen):
    """All-process sparkline trends view."""

    BINDINGS = [
        Binding("escape", "go_back",       "Dashboard", show=True),
        Binding("f2",     "goto_process",  "Process",   show=True),
        Binding("f3",     "goto_alarms",   "Alarms",    show=True),
        Binding("f4",     "goto_plc",      "PLC",       show=True),
    ]

    DEFAULT_CSS = """
    TrendsScreen {
        background: #02080a;
    }
    #trends-header {
        height: 1;
        background: #051014;
        padding: 0 2;
        border-bottom: solid #0a2229;
    }
    #trends-body {
        height: 1fr;
        layout: horizontal;
    }
    #trends-left {
        width: 50%;
        border-right: solid #0a2229;
        overflow-y: scroll;
        padding: 1;
    }
    #trends-right {
        width: 50%;
        overflow-y: scroll;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # (process, field) → SparklineWidget
        self._sparks: dict[tuple, SparklineWidget] = {}

    def compose(self) -> ComposeResult:
        yield Label(
            f"[{_CYAN}]◈ PROCESS TRENDS  —  120-point rolling history[/{_CYAN}]",
            id="trends-header"
        )

        with Horizontal(id="trends-body"):
            with ScrollableContainer(id="trends-left"):
                yield Label(
                    f"[{_CYAN}]PUMPING STATION + HEAT EXCHANGER[/{_CYAN}]"
                )
                prev_proc = None
                for proc, label, field, unit, hi, lo in TREND_SPECS["left"]:
                    if proc != prev_proc:
                        yield Label(
                            f"\n[{_DIM}]── {proc.upper().replace('_',' ')} ──[/{_DIM}]"
                        )
                        prev_proc = proc
                    spark = SparklineWidget(
                        label, unit, 120, hi, lo,
                        id=f"trend-{proc}-{field}"
                    )
                    self._sparks[(proc, field)] = spark
                    yield spark

            with ScrollableContainer(id="trends-right"):
                yield Label(
                    f"[{_CYAN}]BOILER + PIPELINE[/{_CYAN}]"
                )
                prev_proc = None
                for proc, label, field, unit, hi, lo in TREND_SPECS["right"]:
                    if proc != prev_proc:
                        yield Label(
                            f"\n[{_DIM}]── {proc.upper().replace('_',' ')} ──[/{_DIM}]"
                        )
                        prev_proc = proc
                    spark = SparklineWidget(
                        label, unit, 120, hi, lo,
                        id=f"trend-{proc}-{field}"
                    )
                    self._sparks[(proc, field)] = spark
                    yield spark

    def update_trends(self, plant: dict) -> None:
        """Push new values to all sparklines from plant snapshot."""
        if not isinstance(plant, dict):
            return

        for (proc, field), spark in self._sparks.items():
            try:
                val = plant.get(proc, {}).get(field)
                if val is not None:
                    spark.push(val)
            except Exception:
                pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_goto_process(self) -> None:
        self.app.push_screen("process")

    def action_goto_alarms(self) -> None:
        self.app.push_screen("alarms")

    def action_goto_plc(self) -> None:
        self.app.push_screen("plc")
