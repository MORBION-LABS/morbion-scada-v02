"""
ws_client.py — Persistence Telemetry Stream
MORBION SCADA v02 — REBOOT
"""
import asyncio
import json
import websockets

class WSClient:
    def __init__(self, host, port, state_callback):
        self.uri = f"ws://{host}:{port}/ws"
        self.callback = state_callback
        self.running = False

    async def start(self):
        self.running = True
        while self.running:
            try:
                async with websockets.connect(self.uri) as ws:
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        self.callback(data)
            except Exception:
                await asyncio.sleep(2.0)

    def stop(self):
        self.running = False
