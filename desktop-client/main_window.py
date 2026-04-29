"""
main_window.py — MORBION SCADA Desktop Main Window
MORBION SCADA v02

KEY CHANGES FROM v01:
  - CommandLine widget added at bottom of main window
  - Command execution wired to REST client
  - Alarm acknowledgment wired to server /alarms/ack endpoint
  - PLCView tab added
  - TrendsView tab added
  - Header shows unacknowledged alarm count separately
  - Graceful degradation if server host not configured
"""
"""
main_window.py — MORBION SCADA Main Window
MORBION SCADA v02

Flex layout. No fixed heights on charts.
Vertical splitter: content area | scripting engine.
Scripting engine drag-resizable upward.
"""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QSplitter, QSizePolicy,
)
from PyQt6.QtCore    import Qt, QTimer, pyqtSlot
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore    import QByteArray

import theme

log = logging.getLogger("main_window")


class MainWindow(QMainWindow):

    def __init__(self, config: dict, rest, ws_thread):
        super().__init__()
        self._config    = config
        self._rest      = rest
        self._ws        = ws_thread
        self._plant     = {}
        self._alarms    = []

        self.setWindowTitle("MORBION SCADA v02")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(theme.QSS)

        self._build_ui()
        self._wire_ws()
        self._start_poll_timer()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        root.addWidget(self._build_header())

        # Main splitter — content top, scripting engine bottom
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(4)
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.BORDER}; }}"
            f"QSplitter::handle:hover {{ background: {theme.ACCENT}; }}"
        )

        # Tab area
        self._tabs = self._build_tabs()
        self._splitter.addWidget(self._tabs)

        # Scripting engine
        from widgets.command_line import CommandLine
        self._cmd = CommandLine(
            rest     = self._rest,
            config   = self._config,
            get_plant= lambda: self._plant,
        )
        self._splitter.addWidget(self._cmd)

        # Default split: 70% content, 30% scripting
        self._splitter.setSizes([500, 220])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)

        root.addWidget(self._splitter)

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"background-color: {theme.SURFACE}; "
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)

        # Logo
        logo = QSvgWidget()
        logo.load(QByteArray(theme.LOGO_SVG.encode()))
        logo.setFixedSize(32, 32)
        logo.setStyleSheet("background: transparent;")
        layout.addWidget(logo)

        # Name
        name = QLabel("MORBION SCADA v02")
        name.setStyleSheet(
            f"color: {theme.ACCENT}; font-family: 'Courier New', monospace; "
            f"font-size: 14px; font-weight: bold; letter-spacing: 2px; "
            f"background: transparent;"
        )
        layout.addWidget(name)

        layout.addStretch()

        # Live indicator
        self._live_dot = QLabel("●")
        self._live_dot.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 14px; background: transparent;"
        )
        layout.addWidget(self._live_dot)

        self._ws_label = QLabel("CONNECTING")
        self._ws_label.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._ws_label)

        layout.addSpacing(16)

        # Poll rate
        self._poll_label = QLabel("POLL —")
        self._poll_label.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._poll_label)

        layout.addSpacing(16)

        # Alarm count
        self._alarm_label = QLabel("ALARMS  0")
        self._alarm_label.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._alarm_label)

        layout.addSpacing(16)

        # Server time
        self._time_label = QLabel("--:--:--")
        self._time_label.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._time_label)

        return bar

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        from views.overview_view  import OverviewView
        from views.pumping_view   import PumpingView
        from views.hx_view        import HXView
        from views.boiler_view    import BoilerView
        from views.pipeline_view  import PipelineView
        from views.alarms_view    import AlarmsView
        from views.plc_view       import PLCView
        from views.trends_view    import TrendsView

        self._view_overview  = OverviewView(self._rest)
        self._view_pumping   = PumpingView(self._rest, self._config)
        self._view_hx        = HXView(self._rest, self._config)
        self._view_boiler    = BoilerView(self._rest, self._config)
        self._view_pipeline  = PipelineView(self._rest, self._config)
        self._view_alarms    = AlarmsView(self._rest, self._config)
        self._view_plc       = PLCView(self._rest)
        self._view_trends    = TrendsView()

        tabs.addTab(self._view_overview,  "OVERVIEW")
        tabs.addTab(self._view_pumping,   "PUMP STN")
        tabs.addTab(self._view_hx,        "HEAT EXC")
        tabs.addTab(self._view_boiler,    "BOILER")
        tabs.addTab(self._view_pipeline,  "PIPELINE")
        tabs.addTab(self._view_alarms,    "ALARMS")
        tabs.addTab(self._view_plc,       "PLC PROG")
        tabs.addTab(self._view_trends,    "TRENDS")

        return tabs

    # ── Data wiring ───────────────────────────────────────────────────────────

    def _wire_ws(self):
        # Reconnect WS on_data to our update slot
        self._ws._on_data       = self._on_plant_data
        self._ws._on_connect    = self._on_ws_connect
        self._ws._on_disconnect = self._on_ws_disconnect

        # Animate live dot
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._blink_dot)
        self._dot_timer.start(1000)
        self._dot_on = True

    def _start_poll_timer(self):
        # Fallback REST poll if WS drops
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._rest_poll)
        self._poll_timer.start(2000)

    @pyqtSlot()
    def _rest_poll(self):
        if self._ws.connected:
            return
        import threading
        threading.Thread(target=self._fetch_rest, daemon=True).start()

    def _fetch_rest(self):
        data = self._rest.get_all()
        if data:
            QTimer.singleShot(0, lambda: self._on_plant_data(data))

    def _on_plant_data(self, data: dict):
        self._plant  = data
        self._alarms = data.get("alarms", [])
        self._update_header(data)
        self._push_to_views(data)

    def _on_ws_connect(self):
        QTimer.singleShot(0, lambda: self._ws_label.setStyleSheet(theme.STYLE_GREEN))
        QTimer.singleShot(0, lambda: self._ws_label.setText("LIVE"))

    def _on_ws_disconnect(self):
        QTimer.singleShot(0, lambda: self._ws_label.setStyleSheet(theme.STYLE_DIM))
        QTimer.singleShot(0, lambda: self._ws_label.setText("RECONNECTING"))

    def _update_header(self, data: dict):
        # Server time
        t = data.get("server_time", "")
        if t and len(t) >= 19:
            self._time_label.setText(t[11:19])

        # Poll rate
        ms = data.get("poll_rate_ms", 0)
        self._poll_label.setText(f"POLL {ms:.0f}ms")

        # Alarm count
        crit  = sum(1 for a in self._alarms if a.get("sev") == "CRIT")
        total = len(self._alarms)
        if crit > 0:
            self._alarm_label.setStyleSheet(theme.STYLE_RED)
            self._alarm_label.setText(f"⚠ ALARMS  {total}  CRIT {crit}")
        elif total > 0:
            self._alarm_label.setStyleSheet(theme.STYLE_AMBER)
            self._alarm_label.setText(f"⚠ ALARMS  {total}")
        else:
            self._alarm_label.setStyleSheet(theme.STYLE_GREEN)
            self._alarm_label.setText("ALARMS  OK")

    def _push_to_views(self, data: dict):
        ps  = data.get("pumping_station", {})
        hx  = data.get("heat_exchanger",  {})
        bl  = data.get("boiler",          {})
        pl  = data.get("pipeline",        {})
        alm = data.get("alarms",          [])

        try: self._view_overview.update_data(data)
        except Exception: pass
        try: self._view_pumping.update_data(ps)
        except Exception: pass
        try: self._view_hx.update_data(hx)
        except Exception: pass
        try: self._view_boiler.update_data(bl)
        except Exception: pass
        try: self._view_pipeline.update_data(pl)
        except Exception: pass
        try: self._view_alarms.update_data(alm)
        except Exception: pass
        try: self._view_trends.update_data(data)
        except Exception: pass

    def _blink_dot(self):
        self._dot_on = not self._dot_on
        if self._ws.connected:
            color = theme.GREEN if self._dot_on else theme.TEXT_DIM
        else:
            color = theme.AMBER if self._dot_on else theme.TEXT_DIM
        self._live_dot.setStyleSheet(
            f"color: {color}; font-size: 14px; background: transparent;"
        )
