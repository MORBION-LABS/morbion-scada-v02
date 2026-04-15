"""
rest_client.py — MORBION SCADA Desktop REST Client
MORBION SCADA v02

KEY FIXES FROM v01:
  - GC fix: ControlResult and ControlWorker held in _active_requests set
    until callback fires. v01 let them be garbage collected immediately
    after QThreadPool.start() which caused silent callback failures.
  - PLC API calls added: plc_reload(), plc_get_program(), plc_upload()
  - Alarm acknowledgment: ack_alarm()
  - All callbacks fire on UI thread via Qt signal mechanism

Architecture:
  Every request creates a ControlResult (QObject with signal) and
  a ControlWorker (QRunnable). The result is held in _active_requests
  until the finished signal fires, then removed. This prevents GC
  from destroying the QObject before the signal can be emitted.
"""

import httpx
import logging
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

log = logging.getLogger(__name__)


class _Result(QObject):
    """Carries HTTP response back to UI thread via signal."""
    finished = pyqtSignal(dict)


class _Worker(QRunnable):
    """Executes HTTP request in thread pool."""

    def __init__(self, method: str, url: str,
                 body: dict, result: _Result):
        super().__init__()
        self._method = method
        self._url    = url
        self._body   = body
        self._result = result

    def run(self):
        try:
            if self._method == "POST":
                resp = httpx.post(
                    self._url, json=self._body, timeout=5.0)
            else:
                resp = httpx.get(self._url, timeout=5.0)
            data = resp.json()
        except httpx.TimeoutException:
            data = {"ok": False, "error": "Request timeout"}
        except httpx.ConnectError:
            data = {"ok": False, "error": "Cannot reach server"}
        except Exception as e:
            data = {"ok": False, "error": str(e)}

        self._result.finished.emit(data)


class RestClient:
    """
    Non-blocking REST client for MORBION SCADA server.
    All methods return immediately.
    callback(result_dict) called on completion from UI thread.

    GC FIX: _active_requests holds strong references to Result objects
    until callbacks fire. Without this, Qt GC destroys the QObject
    before the signal is emitted, causing silent callback failures.
    """

    def __init__(self, host: str, port: int):
        self._base         = f"http://{host}:{port}"
        self._pool         = QThreadPool.globalInstance()
        self._active_requests: set = set()

    def _send(self, method: str, url: str,
              body: dict, callback):
        """Internal — create worker, hold reference, fire."""
        result = _Result()

        # Hold strong reference until callback fires
        self._active_requests.add(result)

        def on_done(data: dict):
            self._active_requests.discard(result)
            if callback:
                callback(data)

        result.finished.connect(on_done)
        worker = _Worker(method, url, body, result)
        self._pool.start(worker)

    # ── Control ───────────────────────────────────────────────────────────────

    def write_register(self, process: str, register: int,
                       value: int, callback):
        """
        POST /control — write a Modbus register.
        callback(result_dict) on completion.
        result_dict keys: ok, process, register, value, confirmed, error
        """
        self._send(
            method   = "POST",
            url      = f"{self._base}/control",
            body     = {
                "process":  process,
                "register": register,
                "value":    value,
            },
            callback = callback,
        )

    # ── Alarm acknowledgment ──────────────────────────────────────────────────

    def ack_alarm(self, alarm_id: str, callback,
                  operator: str = "OPERATOR"):
        """
        POST /alarms/ack — acknowledge one alarm or all.
        alarm_id: specific ID like "PS-001" or "all"
        """
        self._send(
            method   = "POST",
            url      = f"{self._base}/alarms/ack",
            body     = {
                "alarm_id": alarm_id,
                "operator": operator,
            },
            callback = callback,
        )

    # ── PLC API ───────────────────────────────────────────────────────────────

    def plc_reload(self, process: str, callback):
        """POST /plc/<process>/program/reload — hot reload ST program."""
        self._send(
            method   = "POST",
            url      = f"{self._base}/plc/{process}/program/reload",
            body     = {},
            callback = callback,
        )

    def plc_upload(self, process: str,
                   source: str, callback):
        """POST /plc/<process>/program — upload new ST source."""
        self._send(
            method   = "POST",
            url      = f"{self._base}/plc/{process}/program",
            body     = {"source": source},
            callback = callback,
        )

    def plc_get_status(self, process: str, callback):
        """GET /plc/<process>/status — get PLC runtime status."""
        self._send(
            method   = "GET",
            url      = f"{self._base}/plc/{process}/status",
            body     = {},
            callback = callback,
        )

    def plc_get_program(self, process: str, callback):
        """GET /plc/<process>/program — get ST source."""
        self._send(
            method   = "GET",
            url      = f"{self._base}/plc/{process}/program",
            body     = {},
            callback = callback,
        )

    def plc_get_variables(self, process: str, callback):
        """GET /plc/<process>/variables — get variable map."""
        self._send(
            method   = "GET",
            url      = f"{self._base}/plc/{process}/variables",
            body     = {},
            callback = callback,
        )

    # ── Data reads ────────────────────────────────────────────────────────────

    def get_alarm_history(self, callback):
        """GET /alarms/history — recent alarm history."""
        self._send(
            method   = "GET",
            url      = f"{self._base}/alarms/history",
            body     = {},
            callback = callback,
        )
