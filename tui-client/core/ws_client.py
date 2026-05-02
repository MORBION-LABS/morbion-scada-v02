"""
core/ws_client.py — MORBION SCADA WebSocket Client
MORBION SCADA v02

Async WebSocket client. Maintains a persistent connection.
Calls on_data(dict) for every plant snapshot received.
Auto-reconnects with exponential backoff.
Thread-safe: plant snapshot stored as class attribute,
readable from any coroutine via WSClient.latest.
"""

import asyncio
import json
import sys
import time
from typing import Callable, Optional, Any

try:
    import websockets
    from websockets.exceptions import (
        ConnectionClosed,
        WebSocketException,
        InvalidHandshake,
    )
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False


class WSClient:
    """
    Async WebSocket client for MORBION SCADA server.

    Usage:
        ws = WSClient(host, port, on_data=my_callback)
        await ws.run()   # blocks, auto-reconnects

    on_data(snapshot: dict) is called every push from server.
    latest property returns the most recent snapshot dict (thread-safe read).
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_data: Optional[Callable[[dict], Any]] = None,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ):
        if not _WS_AVAILABLE:
            raise RuntimeError(
                "websockets package not installed: pip install websockets"
            )
        self._url          = f"ws://{host}:{port}/ws"
        self._on_data      = on_data
        self._on_connect   = on_connect
        self._on_disconnect= on_disconnect
        self._running      = False
        self._connected    = False
        self._latest: dict = {}
        self._heartbeat    = 0   # increments each received message

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def latest(self) -> dict:
        """Most recent plant snapshot. Empty dict if not yet received."""
        return self._latest

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def heartbeat(self) -> int:
        """Increments each WS message. Use to detect stale connections."""
        return self._heartbeat

    def stop(self):
        self._running = False

    async def run(self):
        """
        Main loop. Connects, receives, reconnects on failure.
        Run this as an asyncio task.
        """
        if not _WS_AVAILABLE:
            return

        self._running = True
        delay = 1.0

        while self._running:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=8,
                ) as ws:
                    self._connected = True
                    delay = 1.0   # reset backoff on successful connect
                    if self._on_connect:
                        try:
                            await self._on_connect()
                        except Exception as e:
                            self._err(f"on_connect callback error: {e}")

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw)
                            self._latest   = data
                            self._heartbeat = (self._heartbeat + 1) % 10000
                            if self._on_data:
                                try:
                                    result = self._on_data(data)
                                    if asyncio.iscoroutine(result):
                                        await result
                                except Exception as e:
                                    self._err(f"on_data callback error: {e}")
                        except json.JSONDecodeError as e:
                            self._err(f"JSON decode error: {e}")

            except (ConnectionClosed, WebSocketException, InvalidHandshake) as e:
                self._err(f"WS error: {e}")
            except OSError as e:
                self._err(f"WS OS error: {e}")
            except Exception as e:
                self._err(f"WS unexpected error: {e}")
            finally:
                self._connected = False
                if self._on_disconnect:
                    try:
                        result = self._on_disconnect()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        self._err(f"on_disconnect callback error: {e}")

            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)   # exponential backoff, cap 30s

    @staticmethod
    def _err(msg: str):
        print(f"[WS ERROR] {msg}", file=sys.stderr)
