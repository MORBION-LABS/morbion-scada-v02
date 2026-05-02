"""
rest_client.py — MORBION SCADA TUI REST Engine
MORBION SCADA v02

Asynchronous HTTP client for control commands and management.
"""

import httpx
import logging
import asyncio

log = logging.getLogger("rest_client")

class RestClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout

    async def _request(self, method: str, endpoint: str, json_data: dict = None):
        """Internal helper for industrial error handling."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url)
                elif method.upper() == "POST":
                    response = await client.post(url, json=json_data)
                else:
                    return {"ok": False, "error": f"Unsupported method: {method}"}
                
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP Error {e.response.status_code} for {url}")
            return {"ok": False, "error": f"Server returned {e.response.status_code}"}
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            log.error(f"Connection failure to {url}: {e}")
            return {"ok": False, "error": "Server unreachable or timeout"}
        except Exception as e:
            log.error(f"Unexpected REST error: {e}")
            return {"ok": False, "error": str(e)}

    async def get_health(self):
        return await self._request("GET", "/health")

    async def get_plant_data(self):
        return await self._request("GET", "/data")

    async def post_control(self, process: str, register: int, value: int):
        """Primary control write primitive."""
        payload = {"process": process, "register": register, "value": value}
        return await self._request("POST", "/control", json_data=payload)

    async def ack_alarm(self, alarm_id: str, operator: str):
        payload = {"alarm_id": alarm_id, "operator": operator}
        return await self._request("POST", "/alarms/ack", json_data=payload)

    async def get_plc_program(self, process: str):
        return await self._request("GET", f"/plc/{process}/program")

    async def post_plc_program(self, process: str, source: str):
        payload = {"source": source}
        return await self._request("POST", f"/plc/{process}/program", json_data=payload)

    async def reload_plc(self, process: str):
        return await self._request("POST", f"/plc/{process}/program/reload")
