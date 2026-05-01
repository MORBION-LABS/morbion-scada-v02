"""
main_window.py — MORBION Main Window
Surgical Rebuild v07 — Adjustable Layout
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
        self._plant = {}
        self.setWindowTitle("MORBION SCADA v02 — INDUSTRIAL CONTROL")
        self.setMinimumSize(1280, 850); self.setStyleSheet(theme.QSS)
        self._build_ui()
        self._wire_ws()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        
        # VERTICAL SPLITTER: Tabs at top, Engine at bottom
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(6) # Thicker handle for easy grabbing
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BORDER}; }} QSplitter::handle:hover {{ background: {theme.ACCENT}; }}")
        
        # Tabs
        self._tabs = QTabWidget(); self._tabs.setDocumentMode(True)
        from views.overview_view import OverviewView
        from views.pumping_view import PumpingView
        from views.hx_view import HXView
        from views.boiler_view import BoilerView
        from views.pipeline_view import PipelineView
        from views.plc_view import PLCView
        from views.trends_view import TrendsView

        self._tabs.addTab(OverviewView(self._rest), "SYSTEM OVERVIEW")
        self._tabs.addTab(PumpingView(self._rest, self._config), "PUMPING STATION")
        self._tabs.addTab(HXView(self._rest, self._config), "HEAT EXCHANGER")
        self._tabs.addTab(BoilerView(self._rest, self._config), "STEAM BOILER")
        self._tabs.addTab(PipelineView(self._rest, self._config), "PETROLEUM PIPELINE")
        self._tabs.addTab(PLCView(self._rest), "PLC PROGRAMMING")
        self._tabs.addTab(TrendsView(), "HISTORICAL TRENDS")
        
        self._v_splitter.addWidget(self._tabs)

        # ENGINE
        from widgets.command_line import CommandLine
        self._cmd = CommandLine(self._rest, self._config, lambda: self._plant)
        self._v_splitter.addWidget(self._cmd)
        
        self._v_splitter.setSizes([550, 400])
        root.addWidget(self._v_splitter)

    def _wire_ws(self):
        self._ws._on_data = self._on_plant_data

    def _on_plant_data(self, data):
        if not data: return
        self._plant = data
        self._cmd.update_inspector(data) # Update the live Tag Watchlist
        # ... (rest of the tab push logic same as v06)
