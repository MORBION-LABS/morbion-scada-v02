"""
main_window.py — MORBION SCADA Main Window
Surgical Overhaul v06 — Purge Abbreviations
"""
# ... (imports remain same)
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
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(theme.QSS)
        self._build_ui()
        self._wire_ws()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        
        # Splitter between Content (Top) and Scripting Engine (Bottom)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Tabs
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

        # TAB TITLES EXPANDED
        self._tabs.addTab(self._view_overview, "SYSTEM OVERVIEW")
        self._tabs.addTab(self._view_pumping,  "PUMPING STATION")
        self._tabs.addTab(self._view_hx,       "HEAT EXCHANGER")
        self._tabs.addTab(self._view_boiler,   "STEAM BOILER")
        self._tabs.addTab(self._view_pipeline, "PETROLEUM PIPELINE")
        self._tabs.addTab(self._view_plc,      "PLC PROGRAMMING")
        self._tabs.addTab(self._view_trends,   "HISTORICAL TRENDS")
        
        self._splitter.addWidget(self._tabs)

        # SCRIPTING ENGINE (New Modern UI)
        from widgets.command_line import CommandLine
        self._cmd = CommandLine(self._rest, self._config, lambda: self._plant)
        self._splitter.addWidget(self._cmd)
        
        self._splitter.setSizes([600, 300])
        root.addWidget(self._splitter)

    # ... (WebSocket wiring same as before)
    def _on_plant_data(self, data):
        self._plant = data
        # Push to the new Live Inspector in the command line
        self._cmd.update_inspector(data)
        # ... (rest of push logic same)
