"""
main_window.py — Main Application Window
Surgical Overhaul v06 — Full Industrial Titles
"""
import logging
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

class MainWindow(QMainWindow):
    def __init__(self, config, rest, ws_thread):
        super().__init__()
        self._config, self._rest, self._ws = config, rest, ws_thread
        self._plant, self._alarms = {}, []
        self.setWindowTitle("MORBION SCADA v02 — INDUSTRIAL CONTROL")
        self.setMinimumSize(1280, 850); self.setStyleSheet(theme.QSS)
        self._build_ui(); self._wire_ws()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        
        self._tabs = QTabWidget(); self._tabs.setDocumentMode(True)
        from views.overview_view import OverviewView
        from views.pumping_view import PumpingView
        from views.hx_view import HXView
        from views.boiler_view import BoilerView
        from views.pipeline_view import PipelineView
        from views.plc_view import PLCView
        from views.trends_view import TrendsView

        self._view_overview = OverviewView(self._rest)
        self._view_pumping = PumpingView(self._rest, self._config)
        self._view_hx = HXView(self._rest, self._config)
        self._view_boiler = BoilerView(self._rest, self._config)
        self._view_pipeline = PipelineView(self._rest, self._config)
        self._view_plc = PLCView(self._rest)
        self._view_trends = TrendsView()

        self._tabs.addTab(self._view_overview, "SYSTEM OVERVIEW")
        self._tabs.addTab(self._view_pumping,  "PUMPING STATION")
        self._tabs.addTab(self._view_hx,       "HEAT EXCHANGER")
        self._tabs.addTab(self._view_boiler,   "STEAM BOILER")
        self._tabs.addTab(self._view_pipeline, "PETROLEUM PIPELINE")
        self._tabs.addTab(self._view_plc,      "PLC PROGRAMMING")
        self._tabs.addTab(self._view_trends,   "HISTORICAL TRENDS")
        self._splitter.addWidget(self._tabs)

        from widgets.command_line import CommandLine
        self._cmd = CommandLine(self._rest, self._config, lambda: self._plant)
        self._splitter.addWidget(self._cmd)
        self._splitter.setSizes([600, 350]); root.addWidget(self._splitter)

    def _wire_ws(self):
        self._ws._on_data = self._on_plant_data
        if self._ws.connected: self._on_plant_data({})

    def _on_plant_data(self, data):
        if not data: return
        self._plant = data
        self._cmd.update_inspector(data) # NEW: Update the Variable Inspector
        # Push to views
        try: self._view_overview.update_data(data)
        except: pass
        try: self._view_pumping.update_data(data.get("pumping_station", {}))
        except: pass
        try: self._view_hx.update_data(data.get("heat_exchanger", {}))
        except: pass
        try: self._view_boiler.update_data(data.get("boiler", {}))
        except: pass
        try: self._view_pipeline.update_data(data.get("pipeline", {}))
        except: pass
        try: self._view_plc.scan(data) # Optional status sync
        except: pass
