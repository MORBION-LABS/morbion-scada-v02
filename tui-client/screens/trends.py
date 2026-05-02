"""
trends.py — Historical Trend Analysis Screen
MORBION SCADA v02

Visualizes rolling 40-point history for all critical process variables.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, VerticalScroll, Container
from textual.widgets import Header, Footer, Label

from widgets.sparkline import Sparkline

class TrendGroup(Container):
    """A container for a set of sparklines belonging to one process."""
    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.group_title = title

    def compose(self) -> ComposeResult:
        yield Label(f"[bold cyan]▶ {self.group_title.upper()}[/]")
        with Vertical(classes="sparkline-list"):
            yield from self.yield_content()

class TrendsScreen(Screen):
    """
    Multi-process historical trend viewer.
    """
    DEFAULT_CSS = """
    TrendsScreen #main-container {
        padding: 1;
        background: #02080a;
    }

    .trends-header {
        height: 3;
        border-bottom: double #00d4ff;
        margin-bottom: 1;
    }

    TrendGroup {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid #0a2229;
        background: #051014;
    }

    .sparkline-list {
        margin-left: 2;
        height: auto;
    }

    Sparkline {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Container(classes="trends-header"):
                yield Label("PLANT-WIDE TREND ANALYSIS", classes="process-title")
            
            yield Label("[dim]Rolling 40-point history — updates every 1.0s[/]", classes="info-bar")
            
            with VerticalScroll():
                # ── Pumping Station ──
                with TrendGroup("Pumping Station"):
                    yield Sparkline("Level %", id="tr-ps-level", hi_alarm=90.0, lo_alarm=10.0)
                    yield Sparkline("Flow m3/h", id="tr-ps-flow")
                
                # ── Heat Exchanger ──
                with TrendGroup("Heat Exchanger"):
                    yield Sparkline("Efficiency %", id="tr-hx-eff", lo_alarm=45.0)
                    yield Sparkline("T-Cold Out", id="tr-hx-temp", hi_alarm=95.0)
                
                # ── Boiler ──
                with TrendGroup("Boiler"):
                    yield Sparkline("Drum P bar", id="tr-bl-press", hi_alarm=10.0, lo_alarm=6.0)
                    yield Sparkline("Drum Level %", id="tr-bl-level", hi_alarm=80.0, lo_alarm=20.0)
                
                # ── Pipeline ──
                with TrendGroup("Pipeline"):
                    yield Sparkline("Outlet P bar", id="tr-pl-press", hi_alarm=55.0, lo_alarm=30.0)
                    yield Sparkline("Flow Rate", id="tr-pl-flow")

        yield Footer()

    def update_data(self, data: dict):
        """
        Receives WebSocket data and pushes values into the trend buffers.
        """
        # Pumping Station
        ps = data.get("pumping_station", {})
        if ps.get("online"):
            self.query_one("#tr-ps-level", Sparkline).push(ps.get("tank_level_pct", 0))
            self.query_one("#tr-ps-flow", Sparkline).push(ps.get("pump_flow_m3hr", 0))

        # Heat Exchanger
        hx = data.get("heat_exchanger", {})
        if hx.get("online"):
            self.query_one("#tr-hx-eff", Sparkline).push(hx.get("efficiency_pct", 0))
            self.query_one("#tr-hx-temp", Sparkline).push(hx.get("T_cold_out_C", 0))

        # Boiler
        bl = data.get("boiler", {})
        if bl.get("online"):
            self.query_one("#tr-bl-press", Sparkline).push(bl.get("drum_pressure_bar", 0))
            self.query_one("#tr-bl-level", Sparkline).push(bl.get("drum_level_pct", 0))

        # Pipeline
        pl = data.get("pipeline", {})
        if pl.get("online"):
            self.query_one("#tr-pl-press", Sparkline).push(pl.get("outlet_pressure_bar", 0))
            self.query_one("#tr-pl-flow", Sparkline).push(pl.get("flow_rate_m3hr", 0))
