"""
dashboard.py — Plant Overview Screen
MORBION SCADA v02

Four-quadrant real-time monitoring of all process stations.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Grid
from textual.widgets import Header, Footer, Static

from widgets.status_badge import StatusBadge
from widgets.gauge import Gauge
from widgets.sparkline import Sparkline

class ProcessQuadrant(Container):
    """A single process overview container."""
    
    def __init__(self, name: str, label: str, **kwargs):
        super().__init__(**kwargs)
        self.process_name = name
        self.process_label = label

    def compose(self) -> ComposeResult:
        yield Static(f"[bold cyan]◈ {self.process_label.upper()}[/]", classes="quadrant-title")
        yield StatusBadge(id=f"{self.process_name}-badge")
        
        # Specific metrics defined by quadrant
        if self.process_name == "pumping_station":
            yield Gauge("Level", "%", hi_alarm=90.0, lo_alarm=10.0, id="ps-level")
            yield Gauge("Flow", "m3/hr", max_val=150.0, id="ps-flow")
            yield Sparkline("Tank Trend", id="ps-spark")
            
        elif self.process_name == "heat_exchanger":
            yield Gauge("Efficiency", "%", lo_alarm=45.0, id="hx-eff")
            yield Gauge("T-Cold Out", "°C", hi_alarm=95.0, max_val=120.0, id="hx-temp")
            yield Sparkline("Eff Trend", id="hx-spark")
            
        elif self.process_name == "boiler":
            yield Gauge("Pressure", "bar", hi_alarm=10.0, lo_alarm=6.0, max_val=15.0, id="bl-press")
            yield Gauge("Level", "%", hi_alarm=80.0, lo_alarm=20.0, id="bl-level")
            yield Sparkline("P-Drum Trend", id="bl-spark")
            
        elif self.process_name == "pipeline":
            yield Gauge("Outlet P", "bar", hi_alarm=55.0, lo_alarm=30.0, max_val=80.0, id="pl-press")
            yield Gauge("Flow Rate", "m3/hr", max_val=600.0, id="pl-flow")
            yield Sparkline("Flow Trend", id="pl-spark")

class DashboardScreen(Screen):
    """
    Main overview screen with four quadrants.
    """
    DEFAULT_CSS = """
    DashboardScreen Grid {
        grid-size: 2 2;
        grid-gutter: 1;
        padding: 1;
    }

    ProcessQuadrant {
        background: #051014;
        border: tall #0a2229;
        padding: 1 2;
        height: 100%;
    }

    .quadrant-title {
        height: 1;
        margin-bottom: 1;
    }

    DashboardScreen #status-bar {
        background: #0a2229;
        color: #4a7a8c;
        dock: bottom;
        height: 1;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid():
            yield ProcessQuadrant("pumping_station", "Pumping Station")
            yield ProcessQuadrant("heat_exchanger", "Heat Exchanger")
            yield ProcessQuadrant("boiler", "Steam Boiler")
            yield ProcessQuadrant("pipeline", "Petroleum Pipeline")
        yield Static("Server: Disconnected", id="status-bar")
        yield Footer()

    def update_data(self, data: dict):
        """
        Main entry point for WebSocket data updates.
        Updates every widget in every quadrant.
        """
        # Update Status Bar
        status_bar = self.query_one("#status-bar")
        status_bar.update(f"Server Time: {data.get('server_time', 'N/A')} | Poll Rate: {data.get('poll_rate_ms', 0)}ms")

        # ── Pumping Station Update ───────────────────────────────────────────
        ps = data.get("pumping_station", {})
        self.query_one("#pumping_station-badge", StatusBadge).update_status(ps.get("online", False), ps.get("fault_code", 0))
        if ps.get("online"):
            self.query_one("#ps-level", Gauge).update_value(ps.get("tank_level_pct", 0))
            self.query_one("#ps-flow", Gauge).update_value(ps.get("pump_flow_m3hr", 0))
            self.query_one("#ps-spark", Sparkline).push(ps.get("tank_level_pct", 0))

        # ── Heat Exchanger Update ────────────────────────────────────────────
        hx = data.get("heat_exchanger", {})
        self.query_one("#heat_exchanger-badge", StatusBadge).update_status(hx.get("online", False), hx.get("fault_code", 0))
        if hx.get("online"):
            self.query_one("#hx-eff", Gauge).update_value(hx.get("efficiency_pct", 0))
            self.query_one("#hx-temp", Gauge).update_value(hx.get("T_cold_out_C", 0))
            self.query_one("#hx-spark", Sparkline).push(hx.get("efficiency_pct", 0))

        # ── Boiler Update ────────────────────────────────────────────────────
        bl = data.get("boiler", {})
        self.query_one("#boiler-badge", StatusBadge).update_status(bl.get("online", False), bl.get("fault_code", 0))
        if bl.get("online"):
            self.query_one("#bl-press", Gauge).update_value(bl.get("drum_pressure_bar", 0))
            self.query_one("#bl-level", Gauge).update_value(bl.get("drum_level_pct", 0))
            self.query_one("#bl-spark", Sparkline).push(bl.get("drum_pressure_bar", 0))

        # ── Pipeline Update ──────────────────────────────────────────────────
        pl = data.get("pipeline", {})
        self.query_one("#pipeline-badge", StatusBadge).update_status(pl.get("online", False), pl.get("fault_code", 0))
        if pl.get("online"):
            self.query_one("#pl-press", Gauge).update_value(pl.get("outlet_pressure_bar", 0))
            self.query_one("#pl-flow", Gauge).update_value(pl.get("flow_rate_m3hr", 0))
            self.query_one("#pl-spark", Sparkline).push(pl.get("outlet_pressure_bar", 0))
