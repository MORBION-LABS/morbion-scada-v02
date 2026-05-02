"""
tui/screens/process.py — Single Process Deep View
MORBION SCADA v02

Full detail view for one process at a time.
Process selector at top. All tags displayed. Sparklines.
Command bar for writes. Back to dashboard with Esc.
Defensive: all data access guarded.
"""

import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Select, RichLog, Input
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.binding import Binding
from textual.reactive import reactive

from tui.widgets.gauge import GaugeWidget
from tui.widgets.sparkline import SparklineWidget
from tui.widgets.tank import TankWidget
from core.commands import PROCESS_NAMES, TAG_MAP

_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"
_WHITE = "#ffffff"

# Key gauges per process: (label, field, unit, min, max, hi, lo)
PROCESS_GAUGES = {
    "pumping_station": [
        ("Tank Level",   "tank_level_pct",        "%",    0, 100, 90.0, 10.0),
        ("Pump Flow",    "pump_flow_m3hr",         "m³/hr",0, 150, None, None),
        ("Discharge P",  "discharge_pressure_bar", "bar",  0,  10,  8.0, None),
        ("Pump Speed",   "pump_speed_rpm",         "RPM",  0,1500, None, None),
    ],
    "heat_exchanger": [
        ("Efficiency",   "efficiency_pct",  "%",    0, 100, None, 45.0),
        ("T Hot In",     "T_hot_in_C",      "°C",   0, 300, 200,  None),
        ("T Cold Out",   "T_cold_out_C",    "°C",   0, 150,  95,  None),
        ("Q Duty",       "Q_duty_kW",       "kW",   0,5000, None, None),
    ],
    "boiler": [
        ("Drum Pressure","drum_pressure_bar","bar",  0,  12, 10.0,  6.0),
        ("Drum Level",   "drum_level_pct",  "%",    0, 100, 80.0, 20.0),
        ("Steam Flow",   "steam_flow_kghr", "kg/hr",0,6000, None, None),
        ("Flue Temp",    "flue_gas_temp_C", "°C",   0, 400, None, None),
    ],
    "pipeline": [
        ("Outlet P",     "outlet_pressure_bar","bar",  0,  70, 55.0, 30.0),
        ("Flow Rate",    "flow_rate_m3hr",     "m³/hr",0, 600, None, 200.0),
        ("Inlet P",      "inlet_pressure_bar", "bar",  0,  10, None,  1.0),
        ("Pump Diff",    "pump_differential_bar","bar",0,  60, None, None),
    ],
}

# Sparkline tags per process
SPARK_TAGS = {
    "pumping_station": [
        ("Tank Level",  "tank_level_pct",        "%",   90.0, 10.0),
        ("Pump Flow",   "pump_flow_m3hr",         "m³/hr",None,None),
        ("Discharge P", "discharge_pressure_bar", "bar",  8.0, None),
    ],
    "heat_exchanger": [
        ("Efficiency",  "efficiency_pct",  "%",   None, 45.0),
        ("T Cold Out",  "T_cold_out_C",    "°C",  95.0, None),
    ],
    "boiler": [
        ("Drum P",      "drum_pressure_bar","bar", 10.0,  6.0),
        ("Drum Level",  "drum_level_pct",  "%",   80.0, 20.0),
    ],
    "pipeline": [
        ("Outlet P",    "outlet_pressure_bar","bar", 55.0, 30.0),
        ("Flow Rate",   "flow_rate_m3hr",    "m³/hr",None, 200.0),
    ],
}


class ProcessScreen(Screen):
    """Single process deep-dive view."""

    BINDINGS = [
        Binding("escape", "go_back",       "Dashboard", show=True),
        Binding("f3",     "goto_alarms",   "Alarms",    show=True),
        Binding("f4",     "goto_plc",      "PLC",       show=True),
        Binding("colon",  "show_cmd",      "Command",   show=True),
    ]

    DEFAULT_CSS = """
    ProcessScreen {
        background: #02080a;
    }
    #proc-header {
        height: 2;
        background: #051014;
        border-bottom: solid #0a2229;
        padding: 0 2;
    }
    #proc-selector {
        height: 3;
        background: #051014;
        padding: 0 2;
    }
    #proc-body {
        height: 1fr;
        layout: horizontal;
    }
    #proc-left {
        width: 60%;
        border-right: solid #0a2229;
        overflow-y: scroll;
        padding: 1;
    }
    #proc-right {
        width: 40%;
        overflow-y: scroll;
        padding: 1;
    }
    #proc-cmd {
        height: 3;
        border-top: solid #00d4ff;
        background: #051014;
        padding: 0 1;
        display: none;
    }
    #proc-cmd.visible {
        display: block;
    }
    #proc-cmd-input {
        background: #02080a;
        border: none;
        color: #d0e8f0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current   = "pumping_station"
        self._gauges:  dict[str, list[GaugeWidget]]   = {}
        self._sparks:  dict[str, list[SparklineWidget]]= {}
        self._tank:    TankWidget | None               = None
        self._data_log: RichLog | None                 = None

    def compose(self) -> ComposeResult:
        yield Label("", id="proc-header")

        # Process selector buttons
        with Horizontal(id="proc-selector"):
            for p in PROCESS_NAMES:
                short = {"pumping_station":"PS","heat_exchanger":"HX",
                         "boiler":"BL","pipeline":"PL"}.get(p, p[:2].upper())
                yield Label(
                    f"[{_CYAN}][{short}][/{_CYAN}]",
                    id=f"sel-{p}", classes="proc-sel-btn"
                )

        with Horizontal(id="proc-body"):
            # Left — gauges + all values
            with ScrollableContainer(id="proc-left"):
                yield Label("", id="proc-title")
                yield Label("", id="proc-badge")

                # Tank widget (pumping station only)
                tank = TankWidget(id="proc-tank")
                self._tank = tank
                yield tank

                # Gauges
                yield Label(
                    f"[{_DIM}]── GAUGES ──[/{_DIM}]",
                    id="gauges-label"
                )
                for proc in PROCESS_NAMES:
                    gauge_list = []
                    for label, field, unit, mn, mx, hi, lo in PROCESS_GAUGES.get(proc, []):
                        g = GaugeWidget(
                            label, unit, mn, mx, hi, lo,
                            id=f"gauge-{proc}-{field}",
                            classes=f"gauge-{proc}"
                        )
                        gauge_list.append(g)
                        yield g
                    self._gauges[proc] = gauge_list

                # All values as rich log
                yield Label(
                    f"[{_DIM}]── ALL VALUES ──[/{_DIM}]",
                    id="values-label"
                )
                log = RichLog(id="proc-values", markup=True,
                              highlight=False, max_lines=100, wrap=False)
                self._data_log = log
                yield log

            # Right — sparklines
            with ScrollableContainer(id="proc-right"):
                yield Label(
                    f"[{_CYAN}]TRENDS (120s)[/{_CYAN}]",
                    id="trends-title"
                )
                for proc in PROCESS_NAMES:
                    spark_list = []
                    for label, field, unit, hi, lo in SPARK_TAGS.get(proc, []):
                        s = SparklineWidget(
                            label, unit, 120, hi, lo,
                            id=f"spark-{proc}-{field}",
                            classes=f"spark-{proc}"
                        )
                        spark_list.append((field, s))
                        yield s
                    self._sparks[proc] = spark_list

        # Command bar
        with Container(id="proc-cmd"):
            yield Label(f"[{_CYAN}]morbion ›[/{_CYAN}]", id="proc-cmd-label")
            yield Input(
                placeholder="write/inject/fault/read...",
                id="proc-cmd-input"
            )
            yield Label("", id="proc-cmd-result")

    def on_mount(self) -> None:
        self._switch_process("pumping_station")

    def _switch_process(self, proc: str) -> None:
        """Switch visible process. Hide all, show selected."""
        if proc not in PROCESS_NAMES:
            return
        self._current = proc

        # Show/hide gauges
        for p in PROCESS_NAMES:
            for g in self._gauges.get(p, []):
                g.display = (p == proc)
            for _, s in self._sparks.get(p, []):
                s.display = (p == proc)

        # Tank only for pumping station
        if self._tank:
            self._tank.display = (proc == "pumping_station")

        # Update header
        try:
            title_map = {
                "pumping_station": "PUMPING STATION — Nairobi Water",
                "heat_exchanger":  "HEAT EXCHANGER — KenGen Olkaria",
                "boiler":          "BOILER — EABL/Bidco",
                "pipeline":        "PIPELINE — Kenya Pipeline Co.",
            }
            self.query_one("#proc-title", Label).update(
                f"[{_CYAN}]{title_map.get(proc, proc)}[/{_CYAN}]"
            )
        except Exception:
            pass

        # Refresh with latest data
        plant = getattr(self.app, "_plant_cache", {})
        self.update_process(plant)

    def update_process(self, plant: dict) -> None:
        """Update current process view from plant snapshot."""
        if not isinstance(plant, dict):
            return

        proc = self._current
        data = plant.get(proc, {})
        if not isinstance(data, dict):
            return

        online = data.get("online", False)
        fault  = data.get("fault_code", 0)

        # Badge
        try:
            if online:
                badge = (f"[{_RED}]⚠ FAULT {data.get('fault_text','')}[/{_RED}]"
                         if fault else f"[{_GREEN}]●ONLINE[/{_GREEN}]")
            else:
                badge = f"[{_RED}]○OFFLINE[/{_RED}]"
            self.query_one("#proc-badge", Label).update(badge)
        except Exception:
            pass

        if not online:
            return

        # Tank
        if proc == "pumping_station" and self._tank:
            try:
                self._tank.set_level(
                    data.get("tank_level_pct"),
                    data.get("tank_volume_m3", 0)
                )
            except Exception:
                pass

        # Gauges
        for label, field, unit, mn, mx, hi, lo in PROCESS_GAUGES.get(proc, []):
            try:
                gid   = f"gauge-{proc}-{field}"
                gauge = self.query_one(f"#{gid}", GaugeWidget)
                gauge.set_value(data.get(field))
            except Exception:
                pass

        # Sparklines
        for field, spark in self._sparks.get(proc, []):
            try:
                spark.push(data.get(field))
            except Exception:
                pass

        # All values log
        try:
            if self._data_log:
                self._data_log.clear()
                for key, val in data.items():
                    if key in ("online", "process", "label", "location", "port"):
                        continue
                    unit = TAG_MAP.get(proc, {}).get(key, ("","","",""))[2] if key in TAG_MAP.get(proc,{}) else ""
                    colour = _DIM
                    if key == "fault_code" and val != 0:
                        colour = _RED
                    elif key == "fault_text" and val != "OK":
                        colour = _RED
                    self._data_log.write(
                        f"[{_DIM}]{key:<35}[/{_DIM}]"
                        f"[{colour}]{val}[/{colour}]"
                        f"[{_DIM}] {unit}[/{_DIM}]"
                    )
        except Exception:
            pass

    # ── Selector clicks ───────────────────────────────────────────────────────

    def on_label_click(self, event) -> None:
        """Handle process selector label clicks."""
        label_id = event.label.id or ""
        if label_id.startswith("sel-"):
            proc = label_id[4:]
            if proc in PROCESS_NAMES:
                self._switch_process(proc)

    # ── Command bar ───────────────────────────────────────────────────────────

    def action_show_cmd(self) -> None:
        try:
            self.query_one("#proc-cmd").add_class("visible")
            self.query_one("#proc-cmd-input", Input).focus()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "proc-cmd-input":
            return
        line = event.value.strip()
        if not line:
            return
        event.input.value = ""
        try:
            executor = getattr(self.app, "_executor", None)
            if not executor:
                return
            tokens  = line.split()
            verb    = tokens[0].lower() if tokens else ""
            args    = tokens[1:]
            handler_map = {
                "read":   executor.cmd_read,
                "write":  lambda a: executor.cmd_write(a, "write"),
                "inject": executor.cmd_inject,
                "fault":  executor.cmd_fault,
                "status": executor.cmd_status,
            }
            handler = handler_map.get(verb)
            if handler:
                result = await handler(args)
                if result and result.lines:
                    for text, style in reversed(result.lines):
                        if text and not text.startswith("__"):
                            colour_map = {
                                "green":_GREEN,"red":_RED,"amber":_AMBER,
                                "cyan":_CYAN,"dim":_DIM,"white":_WHITE,
                            }
                            c = colour_map.get(style, _TEXT)
                            try:
                                self.query_one("#proc-cmd-result", Label).update(
                                    f"[{c}]{text[:100]}[/{c}]"
                                )
                            except Exception:
                                pass
                            break
            else:
                try:
                    self.query_one("#proc-cmd-result", Label).update(
                        f"[{_AMBER}]Unknown verb: {verb!r}[/{_AMBER}]"
                    )
                except Exception:
                    pass
        except Exception as e:
            try:
                self.query_one("#proc-cmd-result", Label).update(
                    f"[{_RED}]Error: {e}[/{_RED}]"
                )
            except Exception:
                pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_goto_alarms(self) -> None:
        self.app.push_screen("alarms")

    def action_goto_plc(self) -> None:
        self.app.push_screen("plc")
