"""
rest_client.py — MORBION SCADA Desktop REST Client
Surgical Rebuild v02 — Thread-Safe Logic
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("rest_client")

class RestClient:
    MAP = {
        "ps": "pumping_station", "hx": "heat_exchanger",
        "bl": "boiler",          "pl": "pipeline",
        "pumping_station": "pumping_station",
        "heat_exchanger":  "heat_exchanger",
        "boiler":          "boiler",
        "pipeline":        "pipeline"
    }

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _resolve(self, proc: str) -> str:
        return self.MAP.get(proc.lower(), proc)

    def _request(self, method: str, path: str, body: dict = None) -> Optional[dict]:
        url = f"{self._base}{path}"
        try:
            data = json.dumps(body).encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.error(f"REST {method} {path} Failed: {e}")
            return None

    def plc_get_program(self, p):   return self._request("GET", f"/plc/{self._resolve(p)}/program")
    def plc_get_status(self, p):    return self._request("GET", f"/plc/{self._resolve(p)}/status")
    def plc_get_variables(self, p): return self._request("GET", f"/plc/{self._resolve(p)}/variables")
    def plc_reload(self, p):        return self._request("POST", f"/plc/{self._resolve(p)}/program/reload", {})
    def plc_upload(self, p, src):   return self._request("POST", f"/plc/{self._resolve(p)}/program", {"source": src})
    def get_health(self):           return self._request("GET", "/health")
    def get_all(self):              return self._request("GET", "/data")
    def write_register(self, p, r, v): return self._request("POST", "/control", {"process": self._resolve(p), "register": r, "value": v})
