"""
MORBION SCADA Desktop — WebSocket Thread
QThread that maintains WS connection to server.
Emits plantDataReceived(dict) on every push.
Emits connectionChanged(bool) on connect/disconnect.
Auto-reconnects on any failure.
"""
"""
ws_thread.py — MORBION SCADA WebSocket Thread
MORBION SCADA v02
"""

import json
import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("ws_thread")

try:
    import websocket
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False
    log.error("websocket-client not installed: pip install websocket-client")


class WSThread(threading.Thread):
    """
    Background thread maintaining WebSocket connection to SCADA server.
    Calls on_data(dict) for every message received.
    Calls on_connect() and on_disconnect() on state changes.
    Auto-reconnects on failure.
    """

    def __init__(self,
                 url: str,
                 on_data: Callable[[dict], None],
                 on_connect: Optional[Callable] = None,
                 on_disconnect: Optional[Callable] = None,
                 reconnect_interval: float = 3.0):
        super().__init__(daemon=True, name="MorbionWS")
        self._url                = url
        self._on_data            = on_data
        self._on_connect         = on_connect
        self._on_disconnect      = on_disconnect
        self._reconnect_interval = reconnect_interval
        self._running            = False
        self._ws: Optional[websocket.WebSocketApp] = None
        self.connected           = False

    def run(self):
        if not _WS_AVAILABLE:
            log.error("websocket-client not available — WS thread cannot start")
            return

        self._running = True
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self._url,
                    on_open    = self._handle_open,
                    on_message = self._handle_message,
                    on_error   = self._handle_error,
                    on_close   = self._handle_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                log.error("WS error: %s", e)

            if self._running:
                self.connected = False
                if self._on_disconnect:
                    try:
                        self._on_disconnect()
                    except Exception:
                        pass
                log.info("WS reconnecting in %.1fs", self._reconnect_interval)
                time.sleep(self._reconnect_interval)

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _handle_open(self, ws):
        self.connected = True
        log.info("WS connected: %s", self._url)
        if self._on_connect:
            try:
                self._on_connect()
            except Exception:
                pass

    def _handle_message(self, ws, message: str):
        try:
            data = json.loads(message)
            self._on_data(data)
        except Exception as e:
            log.error("WS message parse error: %s", e)

    def _handle_error(self, ws, error):
        log.warning("WS error: %s", error)

    def _handle_close(self, ws, code, msg):
        self.connected = False
        log.info("WS closed: code=%s msg=%s", code, msg)
        if self._on_disconnect:
            try:
                self._on_disconnect()
            except Exception:
                pass
