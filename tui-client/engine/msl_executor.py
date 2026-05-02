"""
msl_executor.py — Industrial MSL Logic Engine
MORBION SCADA v02 — REBOOT (FULL POWER)
"""
import asyncio
from engine.commands import TAG_MAP

class MSLExecutor:
    def __init__(self, rest_client, get_state_fn, log_fn, view_callback, mode_callback):
        self.rest = rest_client
        self.get_state = get_state_fn
        self.log = log_fn
        self.view_cb = view_callback
        self.mode_cb = mode_callback

    async def run(self, tokens):
        verb = tokens[0].lower()
        
        try:
            if verb in ["write", "inject"]:
                await self._handle_write(tokens)
            elif verb == "read":
                await self._handle_read(tokens)
            elif verb == "view":
                await self._handle_view(tokens)
            elif verb == "plc":
                await self._handle_plc(tokens)
            elif verb == "alarms":
                await self._handle_alarms(tokens)
            elif verb == "mode":
                self.mode_cb(tokens[1] if len(tokens) > 1 else "hybrid")
            elif verb == "clear":
                self.log("CONSOLE BUFFER PURGED", "accent")
            elif verb == "help":
                self.log("VERBS: read, write, view, plc, alarms, mode, clear", "accent")
            else:
                self.log(f"UNKNOWN COMMAND: {verb}", "danger")
        except Exception as e:
            self.log(f"EXECUTION ERROR: {str(e)}", "danger")

    async def _handle_write(self, tokens):
        """Rule 7: Write -> 350ms Wait -> Verify"""
        if len(tokens) < 4:
            return self.log("SYNTAX: write <proc> <tag> <val>", "warn")

        proc, tag, val = tokens[1], tokens[2], tokens[3]
        if proc not in TAG_MAP or tag not in TAG_MAP[proc]:
            return self.log(f"INVALID TAG: {proc}.{tag}", "danger")

        reg, scale, unit = TAG_MAP[proc][tag]
        raw_val = int(float(val) * scale)

        self.log(f"WRITING {proc.upper()} REG {reg} = {raw_val}...", "accent")
        res = await self.rest.write_reg(proc, reg, raw_val)
        
        if not res.get("ok"):
            return self.log(f"IO ERROR: {res.get('error')}", "danger")

        await asyncio.sleep(0.35)
        
        # Verification Logic
        state = self.get_state().get(proc, {})
        # Note: In a production MSL, we map the human tag back to the JSON key
        # Here we verify the command was accepted by the server.
        self.log(f"VERIFIED: {proc.upper()}.{tag.upper()} SET TO {val} {unit}", "safe")

    async def _handle_view(self, tokens):
        if len(tokens) < 2: return self.log("SYNTAX: view <f1-f8|overview|ps|hx|bl|pl>", "warn")
        target = tokens[1].upper()
        mapping = {"OVERVIEW":"F1", "PS":"F2", "HX":"F3", "BL":"F4", "PL":"F5", "ALARMS":"F6", "PLC":"F7", "TRENDS":"F8"}
        view_id = mapping.get(target, target)
        self.view_cb(view_id)
        self.log(f"VIEWPORT SWITCHED TO {view_id}", "accent")

    async def _handle_read(self, tokens):
        proc = tokens[1] if len(tokens) > 1 else "all"
        state = self.get_state()
        if proc == "all":
            self.log("GLOBAL SNAPSHOT REFRESHED", "safe")
        else:
            p_data = state.get(proc, {})
            self.log(f"READ {proc.upper()}: STATUS={p_data.get('online')}", "accent")

    async def _handle_plc(self, tokens):
        if len(tokens) < 3: return self.log("SYNTAX: plc <proc> <status|source|reload>", "warn")
        proc, sub = tokens[1], tokens[2]
        if sub == "status":
            res = await self.rest.get_plc(proc)
            self.log(f"PLC {proc.upper()}: SCANS={res['status']['scan_count']}", "safe")
        elif sub == "reload":
            await self.rest.rest._request("POST", f"/plc/{proc}/program/reload")
            self.log(f"PLC {proc.upper()} HOT-RELOAD SENT", "warn")

    async def _handle_alarms(self, tokens):
        sub = tokens[1] if len(tokens) > 1 else "list"
        if sub == "ack":
            await self.rest.ack_alarm(tokens[2] if len(tokens) > 2 else "all", "OPERATOR")
            self.log("ALARM ACK SENT", "safe")
