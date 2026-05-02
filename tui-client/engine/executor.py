"""
executor.py — MSL Command Execution Engine
MORBION SCADA v02

Handles the execution of parsed MSL commands.
Implements Rule 7: Mandatory Verify-After-Write.
"""

import asyncio
import logging
from engine.commands import TAG_MAP, COMMAND_HELP
from engine.parser import VALID_PROCESSES

log = logging.getLogger("executor")

class MSLExecutor:
    def __init__(self, rest_client, state_provider):
        """
        :param rest_client: Instance of connection.rest_client.RestClient
        :param state_provider: A callable or object that returns the latest plant_state dict
        """
        self.rest = rest_client
        self.get_state = state_provider

    async def execute(self, command: dict) -> str:
        """
        Executes a command and returns a string result for the terminal.
        """
        verb = command.get("verb")
        
        if verb == "read":
            return await self._execute_read(command["args"])
        elif verb in ("write", "inject"):
            return await self._execute_write(command["args"])
        elif verb == "fault":
            return await self._execute_fault(command)
        elif verb == "status":
            return await self._execute_status(command["args"])
        elif verb == "plc":
            return await self._execute_plc(command)
        elif verb == "help":
            return self._execute_help(command["args"])
        elif verb == "nop":
            return ""
        
        return f"Verb '{verb}' parsed but execution logic not yet linked."

    # ── Verified Write Logic (Rule 7) ────────────────────────────────────────

    async def _execute_write(self, args: list) -> str:
        process, tag, eng_value = args[0], args[1], float(args[2])
        reg_idx, scale = TAG_MAP[process][tag]
        
        # Calculate raw Modbus value
        raw_value = int(round(eng_value * scale))
        
        # Clamp to Modbus 16-bit unsigned range
        raw_value = max(0, min(65535, raw_value))

        # Perform the write via REST
        result = await self.rest.post_control(process, reg_idx, raw_value)
        if not result.get("ok"):
            return f"[bold red]WRITE FAILED:[/] {result.get('error')}"

        # Mandatory Verify-After-Write delay
        await asyncio.sleep(0.3)

        # Read back from the latest state (provided via WS loop in main app)
        state = self.get_state()
        actual_eng_value = state.get(process, {}).get(tag)

        if actual_eng_value is None:
            return f"[bold amber]UNVERIFIED:[/] Write accepted but tag '{tag}' not found in telemetry."

        # Allow ±2% tolerance for floating point sensor noise
        tolerance = abs(eng_value) * 0.02 + 0.1
        if abs(float(actual_eng_value) - eng_value) <= tolerance:
            return f"[bold green]CONFIRMED:[/] {process}.{tag} = {actual_eng_value}"
        else:
            return f"[bold amber]OVERRIDDEN:[/] Actual value is {actual_eng_value}. PLC interlock may be active."

    # ── Command Handlers ─────────────────────────────────────────────────────

    async def _execute_read(self, args: list) -> str:
        target = args[0]
        state = self.get_state()

        if target == "all":
            summary = []
            for proc in VALID_PROCESSES:
                p_data = state.get(proc, {})
                status = "[green]ONLINE[/]" if p_data.get("online") else "[red]OFFLINE[/]"
                summary.append(f"{proc:<16} : {status}")
            return "\n".join(summary)

        p_data = state.get(target, {})
        if not p_data:
            return f"[red]Error:[/] No data for {target}"

        if len(args) > 1:
            tag = args[1]
            val = p_data.get(tag, "NOT_FOUND")
            return f"{target}.{tag} = {val}"
        
        # Return all tags for the process
        lines = [f"--- {target.upper()} ---"]
        for k, v in p_data.items():
            if k not in ("process", "label", "location", "port"):
                lines.append(f"{k:<22} : {v}")
        return "\n".join(lines)

    async def _execute_fault(self, command: dict) -> str:
        sub = command["sub_verb"]
        target = command["args"][0]

        if sub == "clear":
            if target == "all":
                for proc in VALID_PROCESSES:
                    await self.rest.post_control(proc, 14, 0)
                return "[green]SENT:[/] Clear fault command sent to all processes."
            else:
                await self.rest.post_control(target, 14, 0)
                return f"[green]SENT:[/] Clear fault command sent to {target} (Reg 14)."
        
        elif sub == "status":
            state = self.get_state()
            code = state.get(target, {}).get("fault_code", 0)
            text = state.get(target, {}).get("fault_text", "OK")
            return f"[{target}] FAULT_CODE: {code} ({text})"

        return f"Fault {sub} not fully implemented."

    async def _execute_plc(self, command: dict) -> str:
        process = command["process"]
        sub = command["sub_verb"]

        if sub == "status":
            res = await self.rest.get_plc_program(process)
            status = res.get("status", {})
            return f"[{process}] LOADED: {status.get('loaded')} | SCANS: {status.get('scan_count')}"
        
        elif sub == "reload":
            res = await self.rest.reload_plc(process)
            return f"[green]PLC RELOAD SENT:[/] {process}"

        elif sub == "source":
            res = await self.rest.get_plc_program(process)
            return res.get("source", "(* No source available *)")

        return f"PLC {sub} not implemented."

    async def _execute_status(self, args: list) -> str:
        res = await self.rest.get_health()
        if not res.get("server"):
            return "[red]SERVER OFFLINE[/]"
        return f"[cyan]SERVER:[/] {res.get('server')} | [cyan]STATUS:[/] {res.get('status')}"

    def _execute_help(self, args: list) -> str:
        if not args:
            lines = ["Available Commands:"]
            for v in COMMAND_HELP:
                lines.append(f"  {v:<10} - {COMMAND_HELP[v]['desc']}")
            return "\n".join(lines)
        
        verb = args[0].lower()
        if verb in COMMAND_HELP:
            h = COMMAND_HELP[verb]
            return f"Syntax: {h['syntax']}\nDescription: {h['desc']}"
        return f"No help entry for '{verb}'"
