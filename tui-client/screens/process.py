"""
process.py — Detailed Process Monitoring Screen
MORBION SCADA v02

Provides a deep-dive view of all sensors and actuators for a specific station.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Static, Label

from widgets.status_badge import StatusBadge
from widgets.gauge import Gauge
from widgets.sparkline import Sparkline
from widgets.tank import Tank

class ProcessScreen(Screen):
    """
    Detailed monitoring screen for a specific industrial process.
    """
    DEFAULT_CSS = """
    ProcessScreen #main-container {
        padding: 1;
        background: #02080a;
    }

    .process-header {
        height: 3;
        border-bottom: double #00d4ff;
        margin-bottom: 1;
    }

    .process-title {
        color: #00d4ff;
        text-style: bold;
        width: 40;
    }

    .data-column {
        width: 1fr;
        padding: 1;
        border: tall #0a2229;
        background: #051014;
        margin: 0 1;
    }

    .section-label {
        color: #4a7a8c;
        margin-bottom: 1;
        text-style: underline;
    }

    #tank-container {
        width: 16;
        content-align: center top;
    }
    """

    def __init__(self, process_name: str, label: str, **kwargs):
        super().__init__(**kwargs)
        self.process_name = process_name
        self.process_label = label

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            # ── Header ──
            with Horizontal(classes="process-header"):
                yield Label(f"DETAILED VIEW: {self.process_label.upper()}", classes="process-title")
                yield StatusBadge(id="proc-badge")
                yield Label("", id="proc-location")

            with Horizontal():
                # ── Left Column: Primary Visualization ──
                if self.process_name in ("pumping_station", "boiler"):
                    with Vertical(id="tank-container"):
                        yield Label("LEVEL")
                        yield Tank(label="TANK", id="proc-tank")
                
                # ── Middle Column: Core Metrics ──
                with VerticalScroll(classes="data-column"):
                    yield Label("ANALOG SENSORS", classes="section-label")
                    if self.process_name == "pumping_station":
                        yield Gauge("Pump Speed", "RPM", max_val=1500, id="g-1")
                        yield Gauge("Pressure", "bar", max_val=10, hi_alarm=8.0, id="g-2")
                        yield Gauge("Current", "A", max_val=30, id="g-3")
                        yield Gauge("Power", "kW", max_val=15, id="g-4")
                    elif self.process_name == "heat_exchanger":
                        yield Gauge("T-Hot In", "°C", max_val=300, id="g-1")
                        yield Gauge("T-Hot Out", "°C", max_val=200, hi_alarm=160.0, id="g-2")
                        yield Gauge("T-Cold In", "°C", max_val=100, id="g-3")
                        yield Gauge("T-Cold Out", "°C", max_val=120, hi_alarm=95.0, id="g-4")
                    elif self.process_name == "boiler":
                        yield Gauge("Drum Press", "bar", max_val=15, hi_alarm=10.0, lo_alarm=6.0, id="g-1")
                        yield Gauge("Drum Temp", "°C", max_val=300, id="g-2")
                        yield Gauge("Steam Flow", "kg/hr", max_val=5000, id="g-3")
                        yield Gauge("Fuel Flow", "kg/hr", max_val=200, id="g-4")
                    elif self.process_name == "pipeline":
                        yield Gauge("Inlet P", "bar", max_val=10, lo_alarm=1.0, id="g-1")
                        yield Gauge("Outlet P", "bar", max_val=80, hi_alarm=55.0, lo_alarm=30.0, id="g-2")
                        yield Gauge("Pump Diff", "bar", max_val=60, id="g-3")
                        yield Gauge("Velocity", "m/s", max_val=5, id="g-4")

                # ── Right Column: Actuators & Status ──
                with VerticalScroll(classes="data-column"):
                    yield Label("VALVE & PUMP STATES", classes="section-label")
                    yield Gauge("V-Inlet", "%", id="v-1")
                    yield Gauge("V-Outlet", "%", id="v-2")
                    if self.process_name == "boiler":
                        yield Gauge("V-Blowdown", "%", id="v-3")
                    
                    yield Label("TRENDS", classes="section-label")
                    yield Sparkline("Primary", id="s-1")
                    yield Sparkline("Secondary", id="s-2")

        yield Footer()

    def update_data(self, full_plant_data: dict):
        """Update screen with data filtered for this specific process."""
        data = full_plant_data.get(self.process_name, {})
        if not data:
            return

        # Update Header
        self.query_one("#proc-badge", StatusBadge).update_status(data.get("online", False), data.get("fault_code", 0))
        self.query_one("#proc-location").update(f"[dim]{data.get('location', '')} (Port {data.get('port', '')})[/]")

        if not data.get("online"):
            return

        # Update Tank if applicable
        if self.process_name == "pumping_station":
            self.query_one("#proc-tank", Tank).update_level(data.get("tank_level_pct", 0))
        elif self.process_name == "boiler":
            self.query_one("#proc-tank", Tank).update_level(data.get("drum_level_pct", 0))

        # Dynamic Gauge Mapping
        if self.process_name == "pumping_station":
            self.query_one("#g-1", Gauge).update_value(data.get("pump_speed_rpm", 0))
            self.query_one("#g-2", Gauge).update_value(data.get("discharge_pressure_bar", 0))
            self.query_one("#g-3", Gauge).update_value(data.get("pump_current_A", 0))
            self.query_one("#g-4", Gauge).update_value(data.get("pump_power_kW", 0))
            self.query_one("#v-1", Gauge).update_value(data.get("inlet_valve_pos_pct", 0))
            self.query_one("#v-2", Gauge).update_value(data.get("outlet_valve_pos_pct", 0))
            self.query_one("#s-1", Sparkline).push(data.get("tank_level_pct", 0))
            self.query_one("#s-2", Sparkline).push(data.get("pump_flow_m3hr", 0))

        elif self.process_name == "heat_exchanger":
            self.query_one("#g-1", Gauge).update_value(data.get("T_hot_in_C", 0))
            self.query_one("#g-2", Gauge).update_value(data.get("T_hot_out_C", 0))
            self.query_one("#g-3", Gauge).update_value(data.get("T_cold_in_C", 0))
            self.query_one("#g-4", Gauge).update_value(data.get("T_cold_out_C", 0))
            self.query_one("#v-1", Gauge).update_value(data.get("hot_valve_pos_pct", 0))
            self.query_one("#v-2", Gauge).update_value(data.get("cold_valve_pos_pct", 0))
            self.query_one("#s-1", Sparkline).push(data.get("efficiency_pct", 0))
            self.query_one("#s-2", Sparkline).push(data.get("Q_duty_kW", 0))

        elif self.process_name == "boiler":
            self.query_one("#g-1", Gauge).update_value(data.get("drum_pressure_bar", 0))
            self.query_one("#g-2", Gauge).update_value(data.get("drum_temp_C", 0))
            self.query_one("#g-3", Gauge).update_value(data.get("steam_flow_kghr", 0))
            self.query_one("#g-4", Gauge).update_value(data.get("fuel_flow_kghr", 0))
            self.query_one("#v-1", Gauge).update_value(data.get("steam_valve_pos_pct", 0))
            self.query_one("#v-2", Gauge).update_value(data.get("fw_valve_pos_pct", 0))
            self.query_one("#v-3", Gauge).update_value(data.get("blowdown_valve_pos_pct", 0))
            self.query_one("#s-1", Sparkline).push(data.get("drum_pressure_bar", 0))
            self.query_one("#s-2", Sparkline).push(data.get("drum_level_pct", 0))

        elif self.process_name == "pipeline":
            self.query_one("#g-1", Gauge).update_value(data.get("inlet_pressure_bar", 0))
            self.query_one("#g-2", Gauge).update_value(data.get("outlet_pressure_bar", 0))
            self.query_one("#g-3", Gauge).update_value(data.get("pump_differential_bar", 0))
            self.query_one("#g-4", Gauge).update_value(data.get("flow_velocity_ms", 0))
            self.query_one("#v-1", Gauge).update_value(data.get("inlet_valve_pos_pct", 0))
            self.query_one("#v-2", Gauge).update_value(data.get("outlet_valve_pos_pct", 0))
            self.query_one("#s-1", Sparkline).push(data.get("outlet_pressure_bar", 0))
            self.query_one("#s-2", Sparkline).push(data.get("flow_rate_m3hr", 0))
