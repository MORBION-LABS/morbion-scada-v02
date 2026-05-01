"""
main_window.py — MORBION Main Window
Surgical Rebuild v09 — SPLITTER UNLOCKED
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

class MainWindow(QMainWindow):
    def __init__(self, config, rest, ws_thread):
        super().__init__()
        self._config, self._rest, self._ws = config, rest, ws_thread
        self._plant = {}
        self.setWindowTitle("MORBION SCADA v02 — INDUSTRIAL CONTROL")
        self.setMinimumSize(1280, 850)
        self.setStyleSheet(theme.QSS)
        self._build_ui()
        self._wire_ws()

    def _build_ui(self):
        # CREATE THE MASTER VERTICAL SPLITTER
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(10) # Thick handle for easy grabbing
        self._v_splitter.setStyleSheet(f"""
            QSplitter::handle {{ background: {theme.BORDER}; }} 
            QSplitter::handle:hover {{ background: {theme.ACCENT}; }}
        """)

        # 1. TABS (Top Section)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        # REMOVE MINIMUM HEIGHTS TO UNLOCK SPLITTER
        self._tabs.setMinimumHeight(50) 
        
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
        
        self._v_splitter.addWidget(self._tabs)

        # 2. SCRIPTING ENGINE (Bottom Section)
        from widgets.command_line import CommandLine
        self._cmd = CommandLine(self._rest, self._config, lambda: self._plant)
        self._cmd.setMinimumHeight(50) # UNLOCK SPLITTER
        self._v_splitter.addWidget(self._cmd)
        
        # Initial proportions: 70% Tabs, 30% Engine
        self._v_splitter.setStretchFactor(0, 7)
        self._v_splitter.setStretchFactor(1, 3)
        
        self.setCentralWidget(self._v_splitter)

    def _wire_ws(self):
        self._ws._on_data = self._on_plant_data

    def _on_plant_data(self, data):
        if not data: return
        self._plant = data
        self._cmd.update_inspector(data)
        
        # Route to tabs
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
        try: self._view_trends.update_data(data)
        except: pass
