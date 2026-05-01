"""
plc_http.py — Process PLC HTTP API Server
MORBION SCADA v02 — MULTI-THREADED REBOOT

This is the most critical fix. By using ThreadingHTTPServer, the process
can handle the "Program Source" request and the "Status" request 
simultaneously without deadlocking the socket.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

log = logging.getLogger("plc_http")

class _Handler(BaseHTTPRequestHandler):
    """Handles incoming requests from the SCADA Server proxy."""
    plc_runtime = None

    def log_message(self, fmt, *args):
        # Redirect server logs to the process logger
        log.debug("plc_http: " + fmt, *args)

    def _send_json(self, code: int, data: dict):
        """Helper to send JSON responses correctly."""
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            log.error(f"Failed to send JSON response: {e}")

    def _send_text(self, code: int, text: str):
        """Helper to send plain text (used for the .st source code)."""
        try:
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            log.error(f"Failed to send Text response: {e}")

    def do_GET(self):
        """Handle proxy GET requests."""
        plc = _Handler.plc_runtime
        if plc is None:
            self._send_json(503, {"error": "PLC runtime not available"})
            return

        path = self.path.rstrip("/")

        # Endpoint mapping
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
        """Handle program uploads and reloads."""
        plc = _Handler.plc_runtime
        path = self.path.rstrip("/")

        if path == "/plc/program":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
                source = body.get("source", "")
                if plc.upload_program(source):
                    self._send_json(200, {"ok": True, "status": plc.status})
                else:
                    self._send_json(400, {"ok": False, "error": "Compile failed"})
            except Exception as e:
                self._send_json(400, {"error": str(e)})

        elif path == "/plc/program/reload":
            plc.reload()
            self._send_json(200, {"ok": True, "status": plc.status})
        else:
            self._send_json(404, {"error": "Not Found"})

class PLCHttpServer:
    def __init__(self, plc_runtime, port: int):
        self._plc  = plc_runtime
        self._port = port
        self._server = None

    def start(self):
        _Handler.plc_runtime = self._plc
        # SURGICAL CHANGE: Use ThreadingHTTPServer instead of HTTPServer
        self._server = ThreadingHTTPServer(("0.0.0.0", self._port), _Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        log.info(f"MULTI-THREADED PLC HTTP API live on port {self._port}")

    def stop(self):
        if self._server:
            self._server.shutdown()
