"""
rest_client.py — Industrial REST Engine
MORBION SCADA v02 — REBOOT
"""
import httpx

class RestClient:
    def __init__(self, host, port):
        self.url = f"http://{host}:{port}"
        self.timeout = 5.0

    async def get_all(self):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.url}/data")
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    async def write_reg(self, process, reg, val):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {"process": process, "register": reg, "value": val}
                r = await client.post(f"{self.url}/control", json=payload)
                return r.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_plc(self, process):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.url}/plc/{process}/program")
                return r.json()
        except Exception:
            return None

    async def ack_alarm(self, alarm_id, operator):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {"alarm_id": alarm_id, "operator": operator}
                r = await client.post(f"{self.url}/alarms/ack", json=payload)
                return r.json()
        except Exception:
            return {"ok": False}
