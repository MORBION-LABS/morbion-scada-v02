"""
MORBION SCADA Desktop — WebSocket Thread
QThread that maintains WS connection to server.
Emits plantDataReceived(dict) on every push.
Emits connectionChanged(bool) on connect/disconnect.
Auto-reconnects on any failure.
"""

import json
import time
import logging
import asyncio
import websockets
from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)


class WSThread(QThread):

    plantDataReceived  = pyqtSignal(dict)
    connectionChanged  = pyqtSignal(bool)

    RECONNECT_DELAY_S = 3.0

    def __init__(self, host: str, port: int, parent=None):
        super().__init__(parent)
        self._url     = f"ws://{host}:{port}/ws"
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        """Main thread loop — asyncio event loop inside QThread."""
        asyncio.run(self._connect_loop())

    async def _connect_loop(self):
        while self._running:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=5,
                ) as ws:
                    self.connectionChanged.emit(True)
                    log.info("WS connected: %s", self._url)

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self.plantDataReceived.emit(data)
                        except json.JSONDecodeError:
                            log.warning("WS received non-JSON message")

            except Exception as e:
                log.warning("WS disconnected: %s", e)

            self.connectionChanged.emit(False)

            if self._running:
                await asyncio.sleep(self.RECONNECT_DELAY_S)