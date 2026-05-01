"""
rest_client.py — MORBION SCADA Desktop REST Client
MORBION SCADA v02 — FULL RESTORATION

This file contains ALL methods required by the Scripting Engine and the PLC Tab.
Includes Alias Resolution and UTF-8 decoding for Windows.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("rest_client")

class RestClient:
    # Maps short names to long names for the server
    MAP = {
        "ps": "pumping_station", "hx": "heat_exchanger",
        "bl": "boiler",          "pl": "pipeline",
        "pumping_station": "pumping_station",
        "heat_exchanger":  "heat_exchanger",
        "boiler":          "boiler",
        "pipeline":        "pipeline"
    }

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base    = base_url.rstrip("/")
        self._timeout = timeout

    def _resolve(self, proc: str) -> str:
        return self.MAP.get(proc.lower(), proc)

    def _get(self, path: str) -> Optional[dict]:
        url = f"{self._base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.error(f"REST GET Failed: {url} -> {e}")
            return None

    def _post(self, path: str, body: dict) -> Optional[dict]:
        url = f"{self._base}{path}"
        try:
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.error(f"REST POST Failed: {url} -> {e}")
            return {"ok": False, "error": str(e)}

    # ── PLC API (Required by HMI and Terminal) ────────────────────────────────

    def plc_get_program(self, process: str):
        """Used by HMI to get source + status."""
        return self._get(f"/plc/{self._resolve(process)}/program")

    def plc_get_status(self, process: str):
        """Used by Terminal 'plc <proc> status'."""
        return self._get(f"/plc/{self._resolve(process)}/status")

    def plc_get_variables(self, process: str):
        """Used by HMI to populate IO Map."""
        return self._get(f"/plc/{self._resolve(process)}/variables")

    def plc_upload_program(self, process: str, source: str):
        return self._post(f"/plc/{self._resolve(process)}/program", {"source": source})

    def plc_reload(self, process: str):
        return self._post(f"/plc/{self._resolve(process)}/program/reload", {})

    # ── Standard Data ─────────────────────────────────────────────────────────

    def get_health(self): return self._get("/health")
    def get_all(self):    return self._get("/data")
    
    def get_process(self, process: str):
        return self._get(f"/data/{self._resolve(process)}")

    def write_register(self, process: str, register: int, value: int):
        return self._post("/control", {"process": self._resolve(process), "register": register, "value": value})

    def ack_alarm(self, alarm_id: str, operator: str = "OPERATOR"):
        return self._post("/alarms/ack", {"alarm_id": alarm_id, "operator": operator})

    def get_alarm_history(self):
        res = self._get("/alarms/history")
        return res if isinstance(res, list) else []
