"""
plc_http.py — Process PLC HTTP API Server
MORBION SCADA v02

Secondary HTTP server running inside each process.
Exposes PLC runtime over HTTP so the SCADA server can proxy
PLC program read/upload/reload/status/variables.

Runs in a daemon thread. Does not affect scan loop timing.
Uses only stdlib — no Flask dependency in processes.

Ports:
    pumping_station: 5020
    heat_exchanger:  5060
    boiler:          5070
    pipeline:        5080

Endpoints:
    GET  /plc/program        — ST source text
    POST /plc/program        — upload new ST source {source: str}
    POST /plc/program/reload — hot reload from file
    GET  /plc/status         — runtime status dict
    GET  /plc/variables      — variable map dict
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

log = logging.getLogger("plc_http")


class _Handler(BaseHTTPRequestHandler):

    # Injected by PLCHttpServer before starting
    plc_runtime = None

    def log_message(self, fmt, *args):
        log.debug("plc_http: " + fmt, *args)

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, code: int, text: str):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length)
        return b""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        plc = _Handler.plc_runtime
        if plc is None:
            self._send_json(503, {"error": "PLC runtime not available"})
            return

        path = self.path.rstrip("/")

        if path == "/plc/program":
            self._send_text(200, plc.program_source)

        elif path == "/plc/status":
            self._send_json(200, plc.status)

        elif path == "/plc/variables":
            self._send_json(200, plc.variables)

        elif path == "/health":
            self._send_json(200, {"ok": True})

        else:
            self._send_json(404, {"error": f"Unknown endpoint: {self.path}"})

    def do_POST(self):
        plc = _Handler.plc_runtime
        if plc is None:
            self._send_json(503, {"error": "PLC runtime not available"})
            return

        path = self.path.rstrip("/")

        if path == "/plc/program":
            raw = self._read_body()
            try:
                body = json.loads(raw)
            except Exception:
                self._send_json(400, {"error": "Invalid JSON body"})
                return

            source = body.get("source", "")
            if not source:
                self._send_json(400, {"error": "source field required"})
                return

            success = plc.upload_program(source)
            if success:
                self._send_json(200, {
                    "ok":     True,
                    "status": plc.status,
                })
            else:
                self._send_json(400, {
                    "ok":    False,
                    "error": plc.status.get("last_error", "Upload failed"),
                    "status": plc.status,
                })

        elif path == "/plc/program/reload":
            plc.reload()
            self._send_json(200, {
                "ok":     True,
                "status": plc.status,
            })

        else:
            self._send_json(404, {"error": f"Unknown endpoint: {self.path}"})


class PLCHttpServer:
    """
    Secondary HTTP server for PLC API.
    One instance per process. Runs in a daemon thread.
    Does not block the scan loop.

    Usage:
        plc_http = PLCHttpServer(plc_runtime, port=5070)
        plc_http.start()
        # ... in shutdown:
        plc_http.stop()
    """

    def __init__(self, plc_runtime, port: int):
        self._plc     = plc_runtime
        self._port    = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        # Inject runtime into handler class before server starts
        _Handler.plc_runtime = self._plc

        self._server = HTTPServer(("0.0.0.0", self._port), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"PLCHttp:{self._port}",
            daemon=True,
        )
        self._thread.start()
        log.info("PLC HTTP API listening on port %d", self._port)

    def stop(self):
        if self._server:
            self._server.shutdown()
            log.info("PLC HTTP API stopped (port %d)", self._port)
