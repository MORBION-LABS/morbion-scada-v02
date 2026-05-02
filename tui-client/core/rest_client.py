"""
core/rest_client.py — MORBION SCADA REST Client
MORBION SCADA v02

Async httpx-based REST client.
All methods return parsed JSON dicts or None on failure.
Never raises — all exceptions caught and logged to stderr.
"""

import httpx
import json
import sys
from typing import Optional, Any


class RestClient:
    """
    Async REST client for MORBION SCADA server.
    Base URL: http://<host>:<port>
    Timeout: 10s per request (generous for PLC proxy calls).
    """

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        if not host:
            raise ValueError("host must not be empty")
        self._base    = f"http://{host}:{port}"
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is None:
            raise RuntimeError(
                "RestClient must be used as async context manager: "
                "async with RestClient(...) as client:"
            )

    async def _get(self, path: str) -> Optional[Any]:
        self._ensure_client()
        try:
            r = await self._client.get(path)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            self._err(f"GET {path} HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except httpx.RequestError as e:
            self._err(f"GET {path} connection error: {e}")
            return None
        except Exception as e:
            self._err(f"GET {path} unexpected: {e}")
            return None

    async def _post(self, path: str, body: dict) -> Optional[Any]:
        self._ensure_client()
        try:
            r = await self._client.post(path, json=body)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            self._err(f"POST {path} HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except httpx.RequestError as e:
            self._err(f"POST {path} connection error: {e}")
            return None
        except Exception as e:
            self._err(f"POST {path} unexpected: {e}")
            return None

    @staticmethod
    def _err(msg: str):
        print(f"[REST ERROR] {msg}", file=sys.stderr)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_health(self) -> Optional[dict]:
        """GET /health"""
        return await self._get("/health")

    async def get_data(self) -> Optional[dict]:
        """GET /data — full plant snapshot"""
        return await self._get("/data")

    async def get_alarms(self) -> Optional[list]:
        """GET /data/alarms — active alarms"""
        result = await self._get("/data/alarms")
        if isinstance(result, list):
            return result
        return []

    async def get_alarm_history(self) -> Optional[list]:
        """GET /alarms/history — last 200 events"""
        result = await self._get("/alarms/history")
        if isinstance(result, list):
            return result
        return []

    async def write_register(
        self, process: str, register: int, value: int
    ) -> Optional[dict]:
        """POST /control — write Modbus register"""
        if not isinstance(value, int) or value < 0 or value > 65535:
            self._err(f"write_register: value {value} out of range 0-65535")
            return None
        return await self._post("/control", {
            "process":  process,
            "register": register,
            "value":    value,
        })

    async def ack_alarm(self, alarm_id: str, operator: str) -> Optional[dict]:
        """POST /alarms/ack"""
        return await self._post("/alarms/ack", {
            "alarm_id": alarm_id,
            "operator": operator,
        })

    # ── PLC API ───────────────────────────────────────────────────────────────

    async def plc_get_program(self, process: str) -> Optional[dict]:
        """GET /plc/<process>/program — source + status + variables"""
        return await self._get(f"/plc/{process}/program")

    async def plc_get_status(self, process: str) -> Optional[dict]:
        """GET /plc/<process>/status"""
        return await self._get(f"/plc/{process}/status")

    async def plc_get_variables(self, process: str) -> Optional[dict]:
        """GET /plc/<process>/variables"""
        return await self._get(f"/plc/{process}/variables")

    async def plc_upload(self, process: str, source: str) -> Optional[dict]:
        """POST /plc/<process>/program — upload new ST source"""
        return await self._post(f"/plc/{process}/program", {"source": source})

    async def plc_reload(self, process: str) -> Optional[dict]:
        """POST /plc/<process>/program/reload — hot reload from file"""
        return await self._post(f"/plc/{process}/program/reload", {})

    # ── Convenience ───────────────────────────────────────────────────────────

    async def is_online(self) -> bool:
        """Returns True if server responds to /health."""
        h = await self.get_health()
        return h is not None

    async def processes_online(self) -> int:
        """Returns number of processes currently online."""
        data = await self.get_data()
        if not data:
            return 0
        count = 0
        for proc in ("pumping_station", "heat_exchanger", "boiler", "pipeline"):
            if data.get(proc, {}).get("online"):
                count += 1
        return count
