"""
ws_client.py — MORBION SCADA TUI WebSocket Engine
MORBION SCADA v02

Continuous stream handler for live plant telemetry.
Includes industrial auto-reconnect logic.
"""

import asyncio
import json
import logging
import websockets

log = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, host: str, port: int, on_data_callback):
        self.uri = f"ws://{host}:{port}/ws"
        self.on_data = on_data_callback
        self.running = False
        self._retry_delay = 2.0

    async def start(self):
        """Initiates the persistent connection loop."""
        self.running = True
        asyncio.create_task(self._connect_loop())

    def stop(self):
        """Clean shutdown of the socket loop."""
        self.running = False

    async def _connect_loop(self):
        """Industrial reconnection logic with linear backoff."""
        while self.running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    log.info(f"Connected to telemetry stream: {self.uri}")
                    self._retry_delay = 2.0  # Reset delay on success
                    
                    while self.running:
                        message = await websocket.recv()
                        try:
                            data = json.loads(message)
                            if self.on_data:
                                await self.on_data(data)
                        except json.JSONDecodeError:
                            log.error("Received malformed JSON from WebSocket")
            
            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                if self.running:
                    log.warning(f"Telemetry lost. Retrying in {self._retry_delay}s... ({e})")
                    await asyncio.sleep(self._retry_delay)
                    # Cap retry at 10 seconds to maintain responsiveness
                    self._retry_delay = min(self._retry_delay + 2.0, 10.0)
            except Exception as e:
                log.error(f"Unexpected WebSocket error: {e}")
                await asyncio.sleep(self._retry_delay)
