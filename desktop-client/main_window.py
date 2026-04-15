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

import json
import os
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QStatusBar, QSizePolicy, QMessageBox
)
from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import (
    QFont, QColor, QPalette, QPixmap, QPainter,
    QLinearGradient
)

from connection.ws_thread   import WSThread
from connection.rest_client import RestClient
from views.overview_view    import OverviewView
from views.pumping_view     import PumpingView
from views.hx_view          import HXView
from views.boiler_view      import BoilerView
from views.pipeline_view    import PipelineView
from views.alarms_view      import AlarmsView
from views.plc_view         import PLCView
from views.trends_view      import TrendsView
from widgets.command_line   import CommandLine
from theme import (STYLESHEET, C_ACCENT, C_RED, C_GREEN,
                   C_MUTED, C_TEXT2, C_YELLOW)

log = logging.getLogger(__name__)


class HeaderWidget(QWidget):
    """Top bar: logo + brand + live stats."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)

        logo_path = config.get("ui", {}).get("logo_path", "")
        if logo_path and os.path.isfile(logo_path):
            self._logo_pixmap = QPixmap(logo_path).scaledToHeight(
                40, Qt.TransformationMode.SmoothTransformation)
        else:
            self._logo_pixmap = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Logo or hex icon
        if self._logo_pixmap:
            logo_lbl = QLabel()
            logo_lbl.setPixmap(self._logo_pixmap)
            layout.addWidget(logo_lbl)
        else:
            hex_lbl = QLabel("⬡")
            hex_lbl.setStyleSheet(
                f"color:{C_ACCENT};font-size:28px;"
                f"text-shadow: 0 0 12px {C_ACCENT};")
            layout.addWidget(hex_lbl)

        # Brand
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand = QLabel("MORBION")
        brand.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        brand.setStyleSheet(
            f"color:{C_ACCENT};letter-spacing:6px;"
            f"text-shadow: 0 0 16px {C_ACCENT};")
        sub = QLabel("SCADA v2.0  ·  INDUSTRIAL CONTROL SYSTEM")
        sub.setStyleSheet(
            f"color:{C_MUTED};font-size:8px;letter-spacing:3px;")
        brand_col.addWidget(brand)
        brand_col.addWidget(sub)
        layout.addLayout(brand_col)
        layout.addStretch()

        # Live stats
        stats = QHBoxLayout()
        stats.setSpacing(24)

        self._lbl_processes = self._stat("4/4 ONLINE")
        self._lbl_alarms    = self._stat("0 ALARMS")
        self._lbl_unacked   = self._stat("0 UNACKED")
        self._lbl_poll      = self._stat("POLL #0")
        self._lbl_time      = self._stat("--:--:-- UTC")

        for w in (self._lbl_processes, self._lbl_alarms,
                  self._lbl_unacked, self._lbl_poll, self._lbl_time):
            stats.addWidget(w)

        # Connection indicator
        self._conn_dot = QLabel("●")
        self._conn_dot.setStyleSheet(
            f"color:{C_MUTED};font-size:14px;")
        self._conn_lbl = QLabel("CONNECTING")
        self._conn_lbl.setStyleSheet(
            f"color:{C_MUTED};font-size:9px;letter-spacing:2px;")
        stats.addWidget(self._conn_dot)
        stats.addWidget(self._conn_lbl)
        layout.addLayout(stats)

    def _stat(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C_TEXT2};font-size:9px;"
            f"letter-spacing:2px;font-family:'Courier New';")
        return lbl

    def paintEvent(self, event):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor("#020c16"))
        grad.setColorAt(1.0, QColor("#030f1a"))
        p.fillRect(self.rect(), grad)
        p.setPen(QColor("#0d2030"))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()
        super().paintEvent(event)

    def set_connected(self, connected: bool):
        if connected:
            self._conn_dot.setStyleSheet(
                f"color:{C_GREEN};font-size:14px;")
            self._conn_lbl.setText("LIVE")
            self._conn_lbl.setStyleSheet(
                f"color:{C_GREEN};font-size:9px;letter-spacing:2px;")
        else:
            self._conn_dot.setStyleSheet(
                f"color:{C_RED};font-size:14px;")
            self._conn_lbl.setText("RECONNECTING")
            self._conn_lbl.setStyleSheet(
                f"color:{C_RED};font-size:9px;letter-spacing:2px;")

    def update_plant(self, plant: dict, unacked_count: int = 0):
        online = sum(
            1 for k in ("pumping_station", "heat_exchanger",
                        "boiler", "pipeline")
            if plant.get(k, {}).get("online"))
        alarms  = plant.get("alarms", [])
        n_crit  = sum(1 for a in alarms if a.get("sev") == "CRIT")
        n_total = len(alarms)

        self._lbl_processes.setText(f"{online}/4 ONLINE")
        self._lbl_processes.setStyleSheet(
            f"color:{'#00ff88' if online == 4 else '#ff3333' if online == 0 else '#ffcc00'};"
            f"font-size:9px;letter-spacing:2px;font-family:'Courier New';")

        alarm_color = (C_RED if n_crit > 0
                       else C_YELLOW if n_total > 0
                       else C_TEXT2)
        self._lbl_alarms.setText(f"{n_total} ALARMS")
        self._lbl_alarms.setStyleSheet(
            f"color:{alarm_color};font-size:9px;"
            f"letter-spacing:2px;font-family:'Courier New';")

        unack_color = C_RED if unacked_count > 0 else C_TEXT2
        self._lbl_unacked.setText(f"{unacked_count} UNACKED")
        self._lbl_unacked.setStyleSheet(
            f"color:{unack_color};font-size:9px;"
            f"letter-spacing:2px;font-family:'Courier New';")

        self._lbl_poll.setText(f"POLL #{plant.get('poll_count', 0)}")
        ts = plant.get("server_time", "")
        self._lbl_time.setText(
            ts.split(" ")[1] if " " in ts else ts)


class MorbionMainWindow(QMainWindow):

    def __init__(self, config: dict):
        super().__init__()
        self._config       = config
        self._plant        = {}
        self._unacked      = 0

        ui  = config.get("ui",     {})
        srv = config.get("server", {})

        self.setWindowTitle(ui.get("window_title", "MORBION SCADA v2.0"))
        self.resize(
            ui.get("window_width",  1600),
            ui.get("window_height", 950),
        )
        self.setStyleSheet(STYLESHEET)

        # Background image
        self._bg_pixmap  = None
        self._bg_opacity = ui.get("background_opacity", 0.08)
        bg_path = ui.get("background_image_path", "")
        if bg_path and os.path.isfile(bg_path):
            self._bg_pixmap = QPixmap(bg_path)

        host = srv.get("host", "").strip()
        port = srv.get("port", 5000)

        # ── REST client ───────────────────────────────────────────────────────
        self._rest = RestClient(host, port) if host else None

        # ── Central widget ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = HeaderWidget(config)
        root.addWidget(self._header)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        root.addWidget(self._tabs, 1)

        # ── Views ─────────────────────────────────────────────────────────────
        self._ov_view       = OverviewView(self._rest)
        self._pump_view     = PumpingView(self._rest)
        self._hx_view       = HXView(self._rest)
        self._boiler_view   = BoilerView(self._rest)
        self._pipeline_view = PipelineView(self._rest)
        self._alarms_view   = AlarmsView(self._rest)
        self._plc_view      = PLCView(self._rest)
        self._trends_view   = TrendsView(self._rest)

        self._tabs.addTab(self._ov_view,       "OVERVIEW")
        self._tabs.addTab(self._pump_view,     "PUMPING STATION")
        self._tabs.addTab(self._hx_view,       "HEAT EXCHANGER")
        self._tabs.addTab(self._boiler_view,   "BOILER")
        self._tabs.addTab(self._pipeline_view, "PIPELINE")
        self._tabs.addTab(self._alarms_view,   "ALARMS")
        self._tabs.addTab(self._plc_view,      "PLC PROGRAMS")
        self._tabs.addTab(self._trends_view,   "TRENDS")

        # ── Command line ──────────────────────────────────────────────────────
        self._cmd = CommandLine()
        self._cmd.command_entered.connect(self._on_command)
        root.addWidget(self._cmd)

        # Status bar
        self._status = QStatusBar()
        self._status.showMessage(
            "MORBION SCADA v2.0  ·  Intelligence. Precision. Vigilance.")
        self.setStatusBar(self._status)

        # ── WebSocket thread ──────────────────────────────────────────────────
        if host:
            self._ws = WSThread(host=host, port=port, parent=self)
            self._ws.plantDataReceived.connect(self._on_plant_data)
            self._ws.connectionChanged.connect(self._on_connection)
            self._ws.start()
        else:
            self._ws = None
            self._status.showMessage(
                "⚠ Server host not configured — run installer.py")
            log.error("Server host not configured in config.json")

    # ── Plant data handler ────────────────────────────────────────────────────

    def _on_plant_data(self, plant: dict):
        self._plant = plant

        # Count unacknowledged alarms
        alarms        = plant.get("alarms", [])
        self._unacked = sum(1 for a in alarms if not a.get("acked", False))

        self._header.update_plant(plant, self._unacked)

        try:
            self._ov_view.update_data(plant)
            self._pump_view.update_data(
                plant.get("pumping_station", {"online": False}))
            self._hx_view.update_data(
                plant.get("heat_exchanger",  {"online": False}))
            self._boiler_view.update_data(
                plant.get("boiler",          {"online": False}))
            self._pipeline_view.update_data(
                plant.get("pipeline",        {"online": False}))
            self._alarms_view.update_data(plant)
            self._trends_view.update_data(plant)
        except Exception as e:
            log.error("View update error: %s", e)

        # Update alarms tab badge
        n_total  = len(alarms)
        unacked  = self._unacked
        if unacked > 0:
            tab_text = f"ALARMS ({unacked}⚠)"
        elif n_total > 0:
            tab_text = f"ALARMS ({n_total})"
        else:
            tab_text = "ALARMS"
        self._tabs.setTabText(5, tab_text)

    def _on_connection(self, connected: bool):
        self._header.set_connected(connected)
        if connected:
            self._status.showMessage(
                "● LIVE — Connected to MORBION SCADA Server")
        else:
            self._status.showMessage(
                "⚠ RECONNECTING — Lost connection to server...")

    # ── Command line handler ──────────────────────────────────────────────────

    def _on_command(self, cmd: dict):
        """
        Execute parsed command from CommandLine widget.
        Routes to correct handler based on command type.
        """
        cmd_type = cmd.get("type")

        if cmd_type == "control":
            # Modbus register write via REST
            if self._rest is None:
                self._cmd.print_result(
                    {"ok": False, "error": "Not connected to server"})
                return
            self._rest.write_register(
                process  = cmd["process"],
                register = cmd["register"],
                value    = cmd["value"],
                callback = self._cmd.print_result,
            )

        elif cmd_type == "alarm_ack":
            # Alarm acknowledgment via REST
            if self._rest is None:
                self._cmd.print_result(
                    {"ok": False, "error": "Not connected to server"})
                return
            target = cmd.get("target", "all")
            self._rest.ack_alarm(
                alarm_id = target,
                callback = self._cmd.print_result,
            )

        elif cmd_type == "plc":
            # PLC command — switch to PLC tab and show info
            self._tabs.setCurrentIndex(6)
            action  = cmd.get("action", "")
            process = cmd.get("process", "")
            if action == "reload" and process and self._rest:
                self._rest.plc_reload(process, self._cmd.print_result)
            elif action == "status":
                self._cmd.print_result(
                    {"ok": True,
                     "message": "PLC tab opened — select process to view status"})

        elif cmd_type == "query":
            field = cmd.get("field", "")
            if field == "alarms":
                alarms = self._plant.get("alarms", [])
                if not alarms:
                    self._cmd.print_result(
                        {"ok": True, "message": "No active alarms"})
                else:
                    for a in alarms:
                        ack = "✓" if a.get("acked") else "⚠"
                        self._cmd.print_result({
                            "ok": True,
                            "message": (f"{ack} [{a.get('sev')}] "
                                        f"{a.get('id')} — {a.get('desc')}")
                        })
            elif field == "status":
                proc = cmd.get("process", "all")
                if proc == "all":
                    for key in ("pumping_station", "heat_exchanger",
                                "boiler", "pipeline"):
                        data   = self._plant.get(key, {})
                        online = data.get("online", False)
                        fault  = data.get("fault_code", 0)
                        self._cmd.print_result({
                            "ok": True,
                            "message": (f"{key}: "
                                        f"{'ONLINE' if online else 'OFFLINE'} "
                                        f"fault={fault}")
                        })

        elif cmd_type == "system":
            action = cmd.get("action", "")
            if action == "connect":
                self._cmd.print_result({
                    "ok":     False,
                    "error":  "Use installer.py to change server host"
                })

    # ── Paint and close ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._bg_pixmap:
            p = QPainter(self)
            p.setOpacity(self._bg_opacity)
            scaled = self._bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(0, 0, scaled)
            p.end()
        super().paintEvent(event)

    def closeEvent(self, event):
        if self._ws:
            self._ws.stop()
            self._ws.wait(3000)
        super().closeEvent(event)
