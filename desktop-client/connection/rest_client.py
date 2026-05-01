"""
rest_client.py — MORBION SCADA Desktop REST Client
MORBION SCADA v02 — REWRITTEN FOR ENCODING FIX
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("rest_client")

class RestClient:

    def __init__(self, base_url: str, timeout: float = 5.0):
        self._base    = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str) -> Optional[dict]:
        url = f"{self._base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as r:
                # FIX: Explicitly decode as utf-8 to handle ST file special characters
                raw_data = r.read().decode("utf-8")
                return json.loads(raw_data)
        except Exception as e:
            log.warning("GET %s failed: %s", path, e)
            return None

    def _post(self, path: str, body: dict) -> Optional[dict]:
        url     = f"{self._base}{path}"
        payload = json.dumps(body).encode("utf-8")
        req     = urllib.request.Request(
            url,
            data    = payload,
            method  = "POST",
            headers = {"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                # FIX: Explicitly decode as utf-8
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": str(e)}
        except Exception as e:
            log.warning("POST %s failed: %s", path, e)
            return None

    # ── Data ──────────────────────────────────────────────────────────────────

    def get_health(self) -> Optional[dict]:
        return self._get("/health")

    def get_all(self) -> Optional[dict]:
        return self._get("/data")

    def get_process(self, process: str) -> Optional[dict]:
        return self._get(f"/data/{process}")

    def get_alarms(self) -> Optional[list]:
        result = self._get("/data/alarms")
        return result if isinstance(result, list) else []

    def get_alarm_history(self) -> Optional[list]:
        result = self._get("/alarms/history")
        return result if isinstance(result, list) else []

    # ── Control ───────────────────────────────────────────────────────────────

    def write_register(self, process: str, register: int, value: int) -> dict:
        result = self._post("/control", {
            "process":  process,
            "register": register,
            "value":    value,
        })
        return result or {"ok": False, "error": "No response"}

    # ── Verify after write ────────────────────────────────────────────────────

    def read_register_value(self, process: str, register: int) -> Optional[int]:
        data = self.get_process(process)
        if not data:
            return None
        
        reg_field_map = {
            "pumping_station": {
                0: ("tank_level_pct", 10.0), 2: ("pump_speed_rpm", 1.0),
                7: ("pump_running", 1.0), 8: ("inlet_valve_pos_pct", 10.0),
                9: ("outlet_valve_pos_pct", 10.0), 14:("fault_code", 1.0),
            },
            "heat_exchanger": {
                12:("hot_pump_speed_rpm", 1.0), 13:("cold_pump_speed_rpm", 1.0),
                14:("hot_valve_pos_pct", 10.0), 15:("cold_valve_pos_pct", 10.0),
                16:("fault_code", 1.0),
            },
            "boiler": {
                6: ("burner_state", 1.0), 7: ("fw_pump_speed_rpm", 1.0),
                8: ("steam_valve_pos_pct", 10.0), 9: ("fw_valve_pos_pct", 10.0),
                10:("blowdown_valve_pos_pct", 10.0), 14:("fault_code", 1.0),
            },
            "pipeline": {
                3: ("duty_pump_speed_rpm", 1.0), 5: ("duty_pump_running", 1.0),
                7: ("standby_pump_running", 1.0), 8: ("inlet_valve_pos_pct", 10.0),
                9: ("outlet_valve_pos_pct", 10.0), 14:("fault_code", 1.0),
            },
        }
        mapping = reg_field_map.get(process, {})
        if register not in mapping:
            return None
        field, scale = mapping[register]
        val = data.get(field)
        if val is None:
            return None
        if isinstance(val, bool):
            return 1 if val else 0
        return int(round(float(val) * scale))

    # ── Alarm acknowledge ─────────────────────────────────────────────────────

    def ack_alarm(self, alarm_id: str, operator: str = "OPERATOR") -> dict:
        result = self._post("/alarms/ack", {
            "alarm_id": alarm_id,
            "operator": operator,
        })
        return result or {"ok": False, "error": "No response"}

    # ── PLC API ───────────────────────────────────────────────────────────────

    def _get_slow(self, path: str) -> Optional[dict]:
        """For PLC endpoints — longer timeout and explicit UTF-8."""
        url = f"{self._base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=12.0) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.warning("GET %s failed: %s", path, e)
            return None

    def plc_get_program(self, process: str) -> Optional[dict]:
        return self._get_slow(f"/plc/{process}/program")

    def plc_get_status(self, process: str) -> Optional[dict]:
        return self._get_slow(f"/plc/{process}/status")

    def plc_get_variables(self, process: str) -> Optional[dict]:
        return self._get_slow(f"/plc/{process}/variables")

    def plc_upload_program(self, process: str, source: str) -> dict:
        result = self._post(f"/plc/{process}/program", {"source": source})
        return result or {"ok": False, "error": "No response"}

    def plc_reload(self, process: str) -> dict:
        result = self._post(f"/plc/{process}/program/reload", {})
        return result or {"ok": False, "error": "No response"}
