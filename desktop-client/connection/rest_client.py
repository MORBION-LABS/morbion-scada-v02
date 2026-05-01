"""
rest_client.py — Industrial REST Engine
Surgical Overhaul v06 — Full Names Only
"""
import json, logging, urllib.request
log = logging.getLogger("rest_client")

class RestClient:
    MAP = {"pumping_station":"pumping_station", "heat_exchanger":"heat_exchanger", "boiler":"boiler", "pipeline":"pipeline"}

    def __init__(self, base_url: str, timeout: float = 12.0):
        self._base = base_url.rstrip("/"); self._timeout = timeout

    def _resolve(self, p): return self.MAP.get(p.lower(), p)

    def _req(self, method, path, body=None):
        url = f"{self._base}{path}"
        try:
            data = json.dumps(body).encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.error(f"Error {url}: {e}"); return None

    def plc_get_program(self, p):   return self._req("GET", f"/plc/{self._resolve(p)}/program")
    def plc_get_variables(self, p): return self._req("GET", f"/plc/{self._resolve(p)}/variables")
    def plc_get_status(self, p):    return self._req("GET", f"/plc/{self._resolve(p)}/status")
    def plc_reload(self, p):        return self._req("POST", f"/plc/{self._resolve(p)}/program/reload", {})
    def plc_upload(self, p, src):   return self._req("POST", f"/plc/{self._resolve(p)}/program", {"source": src})
    def get_health(self):           return self._req("GET", "/health")
    def get_all(self):              return self._req("GET", "/data")
    def write_register(self, p, r, v): return self._req("POST", "/control", {"process": self._resolve(p), "register": r, "value": v})
