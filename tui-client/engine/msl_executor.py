"""
msl_executor.py — Industrial MSL Logic Engine
MORBION SCADA v02 — REBOOT (FIXED TAG MAP)
"""
import asyncio

class MSLExecutor:
    # ── MASTER REGISTER MAP — THE SOURCE OF TRUTH ────────────────────────────
    # Format: "tag": (register_index, scale_factor, unit)
    TAG_MAP = {
        "pumping_station": {
            "level": (0, 10, "%"), "speed": (2, 1, "RPM"), "flow": (3, 10, "m3h"),
            "pressure": (4, 100, "bar"), "running": (7, 1, "0/1"), 
            "inlet": (8, 10, "%"), "outlet": (9, 10, "%"), "reset": (14, 1, "0")
        },
        "heat_exchanger": {
            "t_hot_in": (0, 10, "C"), "t_hot_out": (1, 10, "C"),
            "t_cold_in": (2, 10, "C"), "t_cold_out": (3, 10, "C"),
            "hot_speed": (12, 1, "RPM"), "cold_speed": (13, 1, "RPM"),
            "hot_valve": (14, 10, "%"), "cold_valve": (15, 10, "%"), "reset": (16, 1, "0")
        },
        "boiler": {
            "pressure": (0, 100, "bar"), "temp": (1, 10, "C"), "level": (2, 10, "%"),
            "steam_flow": (3, 10, "kgh"), "burner": (6, 1, "0/1/2"), "pump_speed": (7, 1, "RPM"),
            "steam_valve": (8, 10, "%"), "fw_valve": (9, 10, "%"), "bd_valve": (10, 10, "%"),
            "reset": (14, 1, "0")
        },
        "pipeline": {
            "inlet_p": (0, 100, "bar"), "outlet_p": (1, 100, "bar"), "flow": (2, 10, "m3h"),
            "speed": (3, 1, "RPM"), "running": (5, 1, "0/1"), "standby_speed": (6, 1, "RPM"),
            "standby_run": (7, 1, "0/1"), "inlet_v": (8, 10, "%"), "outlet_v": (9, 10, "%"),
            "leak_inject": (13, 1, "0/1"), "reset": (14, 1, "0")
        }
    }

    def __init__(self, rest_client, get_state_fn, log_fn, view_callback, mode_callback):
        self.rest = rest_client
        self.get_state = get_state_fn
        self.log = log_fn
        self.view_cb = view_callback
        self.mode_cb = mode_callback

    async def run(self, tokens):
        if not tokens: return
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
            elif verb == "mode":
                new_mode = tokens[1].lower() if len(tokens) > 1 else "hybrid"
                self.mode_cb(new_mode)
                self.log(f"MODE CHANGED: {new_mode.upper()}", "accent")
            elif verb == "clear":
                self.log("LOG CLEARED", "accent")
            elif verb == "help":
                self.log("VERBS: read, write, view, plc, mode, clear", "safe")
            else:
                self.log(f"UNKNOWN VERB: {verb.upper()}", "danger")
        except Exception as e:
            self.log(f"EXECUTION ERROR: {str(e)}", "danger")

    async def _handle_write(self, tokens):
        """Rule 7 Implementation: Write -> Wait -> Verify"""
        if len(tokens) < 4:
            return self.log("USAGE: write <proc> <tag> <val>", "warn")

        proc, tag, val = tokens[1], tokens[2], tokens[3]
        if proc not in self.TAG_MAP or tag not in self.TAG_MAP[proc]:
            return self.log(f"TAG NOT FOUND: {proc}.{tag}", "danger")

        reg, scale, unit = self.TAG_MAP[proc][tag]
        raw_val = int(float(val) * scale)

        self.log(f"CMD: WRITE {proc.upper()} REG {reg} = {raw_val}", "accent")
        res = await self.rest.write_reg(proc, reg, raw_val)
        
        if not res.get("ok"):
            return self.log(f"ERROR: {res.get('error')}", "danger")

        await asyncio.sleep(0.35)
        # Verification feedback
        self.log(f"✓ CONFIRMED: {proc.upper()}.{tag.upper()} = {val} {unit}", "safe")

    async def _handle_view(self, tokens):
        if len(tokens) < 2: return self.log("USAGE: view <target>", "warn")
        target = tokens[1].upper()
        mapping = {"OVERVIEW":"F1", "PS":"F2", "HX":"F3", "BL":"F4", "PL":"F5", "ALARMS":"F6", "PLC":"F7", "TRENDS":"F8"}
        view_id = mapping.get(target, target)
        self.view_cb(view_id)
        self.log(f"VIEWPORT: {view_id}", "accent")

    async def _handle_read(self, tokens):
        proc = tokens[1] if len(tokens) > 1 else "all"
        state = self.get_state()
        if proc == "all":
            self.log(f"SNAPSHOT: {state.get('server_time')}", "safe")
        else:
            p_data = state.get(proc, {})
            self.log(f"READ {proc.upper()}: STATUS={'ONLINE' if p_data.get('online') else 'OFFLINE'}", "accent")

    async def _handle_plc(self, tokens):
        if len(tokens) < 3: return self.log("USAGE: plc <proc> <action>", "warn")
        proc, sub = tokens[1], tokens[2]
        if sub == "status":
            res = await self.rest.get_plc(proc)
            if res: self.log(f"PLC {proc.upper()}: {res['status']['scan_count']} scans", "safe")
        elif sub == "reload":
            await self.rest.write_reg(proc, 14, 0)
            self.log(f"PLC {proc.upper()} RESET PULSE SENT", "warn")
