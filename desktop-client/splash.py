"""
splash.py — MORBION SCADA Splash Screen
MORBION SCADA v02

Full black startup screen.
Connects to server via WebSocket.
Fades into main window on success.
Shows retry + IP input on timeout.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGraphicsOpacityEffect,
)
from PyQt6.QtCore    import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal,
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore    import QByteArray

import theme

log = logging.getLogger("splash")

_CONNECT_TIMEOUT_MS = 8000
_DOT_INTERVAL_MS    = 500


class SplashScreen(QWidget):

    def __init__(self, config: dict, save_config_fn):
        super().__init__()
        self._config      = config
        self._save_config = save_config_fn
        self._dot_count   = 0
        self._connected   = False

        self._setup_ui()
        self._start_connection()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("MORBION SCADA v02")
        self.setMinimumSize(800, 500)
        self.setStyleSheet(f"background-color: {theme.BG};")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setSpacing(0)
        root.setContentsMargins(60, 60, 60, 60)

       # Logo — PNG from config, SVG fallback
        from PyQt6.QtWidgets import QLabel as _QL
        logo_px  = theme.load_logo_pixmap(self._config, size=32)
        logo_lbl = _QL()
        logo_lbl.setPixmap(logo_px)
        logo_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(logo_lbl)

        root.addSpacing(24)

        # Title
        title = QLabel("MORBION SCADA v02")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {theme.ACCENT}; font-family: 'Courier New', monospace; "
            f"font-size: 28px; font-weight: bold; letter-spacing: 4px; "
            f"background: transparent;"
        )
        root.addWidget(title)

        sub = QLabel("INDUSTRIAL CONTROL SYSTEM")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; letter-spacing: 6px; background: transparent;"
        )
        root.addWidget(sub)

        root.addSpacing(48)

        # Status line
        self._status = QLabel("Initialising...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Courier New', monospace; "
            f"font-size: 13px; background: transparent;"
        )
        root.addWidget(self._status)

        root.addSpacing(8)

        # Tagline
        tagline = QLabel("Intelligence. Precision. Vigilance.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: 'Courier New', monospace; "
            f"font-size: 10px; letter-spacing: 2px; background: transparent;"
        )
        root.addWidget(tagline)

        root.addSpacing(32)

        # Retry panel — hidden until timeout
        self._retry_panel = QWidget()
        self._retry_panel.setStyleSheet("background: transparent;")
        retry_layout = QVBoxLayout(self._retry_panel)
        retry_layout.setContentsMargins(0, 0, 0, 0)
        retry_layout.setSpacing(12)

        ip_row = QHBoxLayout()
        ip_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip_label = QLabel("SERVER IP:PORT")
        ip_label.setStyleSheet(theme.STYLE_DIM)
        self._ip_input = QLineEdit()
        self._ip_input.setText(
            f"{self._config['server_host']}:{self._config['server_port']}"
        )
        self._ip_input.setFixedWidth(220)
        self._ip_input.setStyleSheet(
            f"background: {theme.SURFACE}; color: {theme.TEXT}; "
            f"border: 1px solid {theme.BORDER}; padding: 4px 8px; "
            f"font-family: 'Courier New', monospace;"
        )
        ip_row.addWidget(ip_label)
        ip_row.addSpacing(8)
        ip_row.addWidget(self._ip_input)
        retry_layout.addLayout(ip_row)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._retry_btn = QPushButton("RETRY CONNECTION")
        self._retry_btn.setFixedWidth(200)
        self._retry_btn.setStyleSheet(
            f"background: {theme.SURFACE}; color: {theme.ACCENT}; "
            f"border: 1px solid {theme.ACCENT}; padding: 8px; "
            f"font-family: 'Courier New', monospace; letter-spacing: 2px;"
        )
        self._retry_btn.clicked.connect(self._on_retry)
        btn_row.addWidget(self._retry_btn)
        retry_layout.addLayout(btn_row)

        self._retry_panel.setVisible(False)
        root.addWidget(self._retry_panel)

    # ── Connection ────────────────────────────────────────────────────────────

    def _start_connection(self):
        host = self._config["server_host"]
        port = self._config["server_port"]
        url  = f"ws://{host}:{port}/ws"

        self._set_status(f"Connecting to {host}:{port}")

        # Dot animation timer
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._tick_dots)
        self._dot_timer.start(_DOT_INTERVAL_MS)

        # Timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._timeout_timer.start(_CONNECT_TIMEOUT_MS)

        # WS thread
        from connection.ws_thread import WSThread
        self._ws = WSThread(
            url            = url,
            on_data        = self._on_ws_data,
            on_connect     = self._on_ws_connect,
            on_disconnect  = self._on_ws_disconnect,
        )
        self._ws.start()

    def _on_ws_connect(self):
        if not self._connected:
            self._connected = True
            QTimer.singleShot(0, self._launch_main)

    def _on_ws_data(self, data: dict):
        if not self._connected:
            self._connected = True
            QTimer.singleShot(0, self._launch_main)

    def _on_ws_disconnect(self):
        pass

    def _on_timeout(self):
        if self._connected:
            return
        self._dot_timer.stop()
        self._set_status(
            f"SERVER UNREACHABLE — {self._config['server_host']}:{self._config['server_port']}",
            color=theme.RED
        )
        self._retry_panel.setVisible(True)

    def _on_retry(self):
        raw = self._ip_input.text().strip()
        if ":" in raw:
            parts = raw.rsplit(":", 1)
            self._config["server_host"] = parts[0]
            try:
                self._config["server_port"] = int(parts[1])
            except ValueError:
                pass
        else:
            self._config["server_host"] = raw

        self._save_config(self._config)
        self._retry_panel.setVisible(False)
        self._connected = False

        if hasattr(self, "_ws"):
            self._ws.stop()

        self._start_connection()

    def _tick_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        host = self._config["server_host"]
        port = self._config["server_port"]
        dots = "." * self._dot_count
        self._set_status(f"Connecting to {host}:{port}{dots}")

    def _set_status(self, text: str, color: str = None):
        c = color or theme.TEXT
        self._status.setStyleSheet(
            f"color: {c}; font-family: 'Courier New', monospace; "
            f"font-size: 13px; background: transparent;"
        )
        self._status.setText(text)

    # ── Launch ────────────────────────────────────────────────────────────────

    def _launch_main(self):
        self._dot_timer.stop()
        self._timeout_timer.stop()

        from main_window import MainWindow
        from connection.rest_client import RestClient

        host = self._config["server_host"]
        port = self._config["server_port"]

        rest = RestClient(f"http://{host}:{port}")

        self._main = MainWindow(
            config   = self._config,
            rest     = rest,
            ws_thread= self._ws,
        )
        self._main.show()
        self.close()
