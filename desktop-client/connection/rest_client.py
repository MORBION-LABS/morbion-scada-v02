"""
rest_client.py — MORBION SCADA Desktop REST Client
MORBION SCADA v02 — SURGICAL REPAIR (ALIAS RESOLUTION)
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("rest_client")

class RestClient:
    # Global map to ensure UI short-codes match Server full-names
    MAP = {
        "ps": "pumping_station", "hx": "heat_exchanger",
        "bl": "boiler",          "pl": "pipeline",
        "pumping_station": "pumping_station",
        "heat_exchanger":  "heat_exchanger",
        "boiler":          "boiler",
        "pipeline":        "pipeline"
    }

    def __init__(self, base_url: str, timeout: float = 5.0):
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
            log.warning("GET %s failed: %s", url, e)
            return None

    def _post(self, path: str, body: dict) -> Optional[dict]:
        url     = f"{self._base}{path}"
        payload = json.dumps(body).encode("utf-8")
        req     = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.warning("POST %s failed: %s", url, e)
            return {"ok": False, "error": str(e)}

    # ── Data ──────────────────────────────────────────────────────────────────

    def get_health(self): return self._get("/health")
    def get_all(self):    return self._get("/data")
    def get_process(self, process: str): 
        return self._get(f"/data/{self._resolve(process)}")

    def get_alarms(self):
        res = self._get("/data/alarms")
        return res if isinstance(res, list) else []

    def get_alarm_history(self):
        res = self._get("/alarms/history")
        return res if isinstance(res, list) else []

    # ── Control ───────────────────────────────────────────────────────────────

    def write_register(self, process: str, register: int, value: int):
        return self._post("/control", {
            "process":  self._resolve(process),
            "register": register,
            "value":    value,
        })

    def read_register_value(self, process: str, register: int) -> Optional[int]:
        p_resolved = self._resolve(process)
        data = self.get_process(p_resolved)
        if not data: return None
        
        # Mapping table for readback verification
        m = {
            "pumping_station": {0:("tank_level_pct",10), 7:("pump_running",1), 8:("inlet_valve_pos_pct",10)},
            "heat_exchanger":  {12:("hot_pump_speed_rpm",1), 14:("hot_valve_pos_pct",10)},
            "boiler":          {6:("burner_state",1), 8:("steam_valve_pos_pct",10)},
            "pipeline":        {3:("duty_pump_speed_rpm",1), 5:("duty_pump_running",1)}
        }
        proc_m = m.get(p_resolved, {})
        if register not in proc_m: return None
        field, scale = proc_m[register]
        val = data.get(field)
        if val is None: return None
        return int(round(float(val) * scale)) if not isinstance(val, bool) else (1 if val else 0)

    # ── PLC API ───────────────────────────────────────────────────────────────

    def plc_get_program(self, process: str):
        return self._get(f"/plc/{self._resolve(process)}/program")

    def plc_get_status(self, process: str):
        return self._get(f"/plc/{self._resolve(process)}/status")

    def plc_get_variables(self, process: str):
        return self._get(f"/plc/{self._resolve(process)}/variables")

    def plc_upload_program(self, process: str, source: str):
        return self._post(f"/plc/{self._resolve(process)}/program", {"source": source})

    def plc_reload(self, process: str):
        return self._post(f"/plc/{self._resolve(process)}/program/reload", {})

    def ack_alarm(self, alarm_id: str, operator: str = "OPERATOR"):
        return self._post("/alarms/ack", {"alarm_id": alarm_id, "operator": operator})
