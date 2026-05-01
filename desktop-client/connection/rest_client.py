"""
rest_client.py — MORBION SCADA Desktop REST Client
MORBION SCADA v02 — SURGICAL REBOOT (ALIAS + UTF8)

Standardizes all calls. Ensures Windows doesn't crash on ST file characters.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("rest_client")

class RestClient:
    # THE ALIAS MAP: Translates UI short-codes to Server full-names
    MAP = {
        "ps": "pumping_station", "hx": "heat_exchanger",
        "bl": "boiler",          "pl": "pipeline",
        "pumping_station": "pumping_station",
        "heat_exchanger":  "heat_exchanger",
        "boiler":          "boiler",
        "pipeline":        "pipeline"
    }

    def __init__(self, base_url: str, timeout: float = 8.0):
        self._base    = base_url.rstrip("/")
        self._timeout = timeout

    def _resolve(self, proc: str) -> str:
        """Ensures 'ps' becomes 'pumping_station'."""
        return self.MAP.get(proc.lower(), proc)

    def _get(self, path: str) -> Optional[dict]:
        url = f"{self._base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as r:
                # CRITICAL: Force UTF-8 for Windows compatibility
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"GET failed {url}: {e}")
            return None

    def plc_get_program(self, process: str):
        # Automatically resolve aliases like 'bl' -> 'boiler'
        return self._get(f"/plc/{self._resolve(process)}/program")

    def plc_get_variables(self, process: str):
        return self._get(f"/plc/{self._resolve(process)}/variables")

    def plc_reload(self, process: str):
        return self._post(f"/plc/{self._resolve(process)}/program/reload", {})

    def plc_upload_program(self, process: str, source: str):
        return self._post(f"/plc/{self._resolve(process)}/program", {"source": source})

    def get_health(self): return self._get("/health")
    def get_all(self):    return self._get("/data")
    
    def write_register(self, process: str, register: int, value: int):
        return self._post("/control", {"process": self._resolve(process), "register": register, "value": value})

    def _post(self, path: str, body: dict) -> Optional[dict]:
        url = f"{self._base}{path}"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": str(e)}
