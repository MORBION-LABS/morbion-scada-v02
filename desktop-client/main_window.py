"""
main_window.py — Main Application Window
Surgical Rebuild v08 — DATA FLOW RESTORATION
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
        self._plant = {}
        self.setWindowTitle("MORBION SCADA v02 — INDUSTRIAL CONTROL")
        self.setMinimumSize(1280, 850)
        self.setStyleSheet(theme.QSS)
        self._build_ui()
        self._wire_ws()

    def _build_ui(self):
        # CREATE THE SPLITTER FIRST - THIS IS THE MAIN CONTAINER
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(8)
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BORDER}; }} QSplitter::handle:hover {{ background: {theme.ACCENT}; }}")

        # 1. TABS (Top Section)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        
        from views.overview_view import OverviewView
        from views.pumping_view import PumpingView
        from views.hx_view import HXView
        from views.boiler_view import BoilerView
        from views.pipeline_view import PipelineView
        from views.plc_view import PLCView
        from views.trends_view import TrendsView

        # CRITICAL: We MUST name these so _on_plant_data can find them!
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
        self._v_splitter.addWidget(self._cmd)
        
        # Set initial split (70% top, 30% bottom)
        self._v_splitter.setSizes([600, 250])
        
        # SET SPLITTER AS THE CENTRAL WIDGET TO ENSURE RESIZABILITY
        self.setCentralWidget(self._v_splitter)

    def _wire_ws(self):
        self._ws._on_data = self._on_plant_data

    def _on_plant_data(self, data):
        if not data: return
        self._plant = data
        
        # Update the Inspector tree in the engine
        self._cmd.update_inspector(data)
        
        # ROUTE DATA TO TABS (Now that references exist, this will work)
        try: self._view_overview.update_data(data)
        except Exception as e: print(f"Err Overview: {e}")
            
        try: self._view_pumping.update_data(data.get("pumping_station", {}))
        except Exception as e: print(f"Err Pumping: {e}")
            
        try: self._view_hx.update_data(data.get("heat_exchanger", {}))
        except Exception as e: print(f"Err HX: {e}")
            
        try: self._view_boiler.update_data(data.get("boiler", {}))
        except Exception as e: print(f"Err Boiler: {e}")
            
        try: self._view_pipeline.update_data(data.get("pipeline", {}))
        except Exception as e: print(f"Err Pipeline: {e}")
            
        try: self._view_trends.update_data(data)
        except Exception as e: print(f"Err Trends: {e}")
