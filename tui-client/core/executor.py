"""
core/executor.py — MORBION Command Executor
MORBION SCADA v02

Executes all MSL commands against the REST API.
Uses the latest WS plant snapshot for read-back verification.
All methods are async. All return an ExecutorResult.
Never raises — defensive programming throughout.
"""

import asyncio
import json
import os
import difflib
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Any

from .rest_client import RestClient
from .commands import (
    TAG_MAP,
    PROCESS_NAMES,
    FAULT_CODES,
    COMMAND_HELP,
    ALL_VERBS,
    SPECIAL_NOTES,
    format_register_map,
    format_fault_table,
)


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class ExecutorResult:
    """
    Returned by every executor method.
    lines: list of (text, style) tuples.
    style values: "normal" "dim" "green" "red" "amber" "cyan" "white"
    ok: False means the command failed (not the PLC override — that is "amber")
    """
    lines: List[Tuple[str, str]] = field(default_factory=list)
    ok:    bool = True

    def add(self, text: str, style: str = "normal"):
        self.lines.append((text, style))

    def error(self, text: str):
        self.lines.append((f"ERROR: {text}", "red"))
        self.ok = False

    def success(self, text: str):
        self.lines.append((text, "green"))

    def warn(self, text: str):
        self.lines.append((text, "amber"))

    def dim(self, text: str):
        self.lines.append((text, "dim"))

    def cyan(self, text: str):
        self.lines.append((text, "cyan"))


# ── Executor ──────────────────────────────────────────────────────────────────

class Executor:
    """
    Executes MSL commands.

    Requires:
      - rest: RestClient (used as async context manager externally,
              passed in already-open)
      - get_plant: callable that returns the latest plant snapshot dict
                   (from WSClient.latest)
      - operator: operator name for alarm acks

    All public methods are async and return ExecutorResult.
    """

    def __init__(
        self,
        rest: RestClient,
        get_plant: callable,
        operator: str,
        verify_timeout_ms: int = 300,
    ):
        self._rest    = rest
        self._plant   = get_plant   # callable → dict
        self._op      = operator
        self._verify_ms = verify_timeout_ms

    # ── Utility ───────────────────────────────────────────────────────────────

    def _tag_info(self, process: str, tag: str):
        """Returns (register, scale, unit, writable) or None."""
        return TAG_MAP.get(process, {}).get(tag)

    def _eng_to_raw(self, value: float, scale: float) -> int:
        """Convert engineering-unit value to raw uint16."""
        raw = int(round(float(value) * scale))
        return max(0, min(65535, raw))

    def _raw_to_eng(self, raw: int, scale: float) -> float:
        """Convert raw uint16 to engineering-unit value."""
        if scale == 0:
            return 0.0
        return raw / scale

    def _plant_tag(self, process: str, tag: str) -> Optional[Any]:
        """Read tag from latest plant snapshot."""
        snapshot = self._plant()
        if not snapshot:
            return None
        return snapshot.get(process, {}).get(tag)

    # ── Verified write ────────────────────────────────────────────────────────

    async def _verified_write(
        self,
        result: ExecutorResult,
        process: str,
        register: int,
        raw_value: int,
        tag: str,
        expected_eng: float,
        scale: float,
    ):
        """
        Write register, wait verify_timeout_ms, read back from plant snapshot.
        Appends CONFIRMED / OVERRIDDEN / UNVERIFIED / WRITE FAILED to result.
        """
        write_result = await self._rest.write_register(process, register, raw_value)

        if write_result is None:
            result.error(f"WRITE FAILED — server did not respond")
            return

        if not write_result.get("ok"):
            err = write_result.get("error", "unknown")
            result.error(f"WRITE FAILED — {err}")
            return

        result.dim(f"  Wrote reg {register} = {raw_value} (raw) → waiting {self._verify_ms}ms...")

        await asyncio.sleep(self._verify_ms / 1000.0)

        actual_raw = self._plant_tag(process, tag)

        if actual_raw is None:
            result.warn("  UNVERIFIED — process data not yet in snapshot")
            return

        # Convert actual to engineering units for comparison
        try:
            actual_eng = float(actual_raw)
        except (TypeError, ValueError):
            result.warn(f"  UNVERIFIED — unexpected value type: {actual_raw!r}")
            return

        # Tolerance: 2% relative + 0.1 absolute (handles sensor noise)
        tolerance = abs(expected_eng) * 0.02 + 0.1

        if abs(actual_eng - expected_eng) <= tolerance:
            result.success(
                f"  ✓ CONFIRMED — {tag} = {actual_eng} {_unit(process, tag)}"
            )
        else:
            result.warn(
                f"  ⚠ OVERRIDDEN — expected {expected_eng}, "
                f"actual {actual_eng} {_unit(process, tag)}\n"
                f"    PLC may have rejected command (check fault_code)"
            )

    # ── Command handlers ──────────────────────────────────────────────────────

    async def cmd_read(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        if not args:
            r.error("Usage: read <process> [tag]  or  read all")
            return r

        target = args[0].lower()

        if target == "all":
            snapshot = self._plant()
            if not snapshot:
                snapshot = await self._rest.get_data()
            if not snapshot:
                r.error("No data — is the server online?")
                return r
            for proc in PROCESS_NAMES:
                d = snapshot.get(proc, {})
                online = d.get("online", False)
                badge  = "●ONLINE" if online else "○OFFLINE"
                style  = "green" if online else "red"
                r.add(f"  {proc:<25} {badge}", style)
                if online:
                    for key in ("fault_code", "fault_text"):
                        if key in d:
                            r.dim(f"    {key}: {d[key]}")
            return r

        if target not in PROCESS_NAMES:
            r.error(f"Unknown process: {target!r}. Valid: {', '.join(PROCESS_NAMES)}")
            return r

        # Single tag or all tags for process
        snapshot = self._plant()
        if not snapshot:
            snapshot = await self._rest.get_data()
        if not snapshot:
            r.error("No data — is the server online?")
            return r

        proc_data = snapshot.get(target, {})
        if not proc_data:
            r.error(f"No data for {target}")
            return r

        if len(args) >= 2:
            tag = args[1]
            val = proc_data.get(tag)
            if val is None:
                r.error(f"Tag {tag!r} not found in {target}")
                return r
            unit = _unit(target, tag)
            r.add(f"  {tag} = {val} {unit}", "white")
            # Show special note if exists
            note = SPECIAL_NOTES.get((target, tag))
            if note:
                r.dim(f"  Note: {note.splitlines()[0]}")
        else:
            online = proc_data.get("online", False)
            badge  = "●ONLINE" if online else "○OFFLINE"
            r.add(f"  {target}  {badge}", "green" if online else "red")
            r.dim("  " + "─" * 48)
            for key, val in proc_data.items():
                if key in ("online", "process", "label", "location", "port"):
                    continue
                unit = _unit(target, key)
                line = f"  {key:<35} {val}"
                if unit:
                    line += f" {unit}"
                style = _alarm_style(target, key, val)
                r.add(line, style)

        return r

    async def cmd_write(self, args: list, verb: str = "write") -> ExecutorResult:
        r = ExecutorResult()
        if len(args) < 3:
            r.error(f"Usage: {verb} <process> <tag> <value>")
            return r

        process, tag, value_str = args[0], args[1], args[2]

        if process not in PROCESS_NAMES:
            r.error(f"Unknown process: {process!r}")
            return r

        info = self._tag_info(process, tag)
        if info is None:
            r.error(f"Unknown tag {tag!r} for {process}. Use: help register {process}")
            return r

        register, scale, unit, writable = info

        if not writable:
            r.warn(f"Tag {tag!r} is read-only. Cannot write.")
            return r

        try:
            eng_value = float(value_str)
        except ValueError:
            r.error(f"Invalid value: {value_str!r} — must be a number")
            return r

        raw_value = self._eng_to_raw(eng_value, scale)

        r.cyan(f"  {verb} {process} {tag} = {eng_value} {unit}  (raw: {raw_value})")

        # Special note for inlet_valve_pos_pct
        if process == "pumping_station" and tag == "inlet_valve_pos_pct":
            action = "OPEN" if raw_value > 500 else "CLOSE"
            r.dim(f"  Inlet valve will {action} (raw {raw_value} {'>' if raw_value > 500 else '≤'} 500)")

        await self._verified_write(r, process, register, raw_value, tag, eng_value, scale)
        return r

    async def cmd_inject(self, args: list) -> ExecutorResult:
        """Semantically identical to write — signals fault injection intent."""
        r = ExecutorResult()
        if len(args) < 3:
            r.error("Usage: inject <process> <tag> <value>")
            return r
        r.dim("  [INJECT] Forcing sensor value — PLC physics will respond")
        write_result = await self.cmd_write(args, verb="inject")
        r.lines.extend(write_result.lines)
        r.ok = write_result.ok
        return r

    async def cmd_fault(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        if not args:
            r.error("Usage: fault <clear|status|inject> <process> [code]")
            return r

        sub = args[0].lower()

        if sub == "clear":
            targets = []
            if len(args) < 2:
                r.error("Usage: fault clear <process>  or  fault clear all")
                return r
            target = args[1].lower()
            if target == "all":
                targets = PROCESS_NAMES
            elif target in PROCESS_NAMES:
                targets = [target]
            else:
                r.error(f"Unknown process: {target!r}")
                return r

            for proc in targets:
                info = self._tag_info(proc, "fault_code")
                if info is None:
                    r.error(f"No fault_code tag for {proc}")
                    continue
                register, scale, unit, _ = info
                r.cyan(f"  Clearing fault on {proc}...")
                write_result = await self._rest.write_register(proc, register, 0)
                if write_result is None or not write_result.get("ok"):
                    r.error(f"  Write failed for {proc}")
                    continue
                await asyncio.sleep(self._verify_ms / 1000.0)
                actual = self._plant_tag(proc, "fault_code")
                if actual == 0 or actual == "0":
                    r.success(f"  ✓ {proc} fault cleared")
                else:
                    r.warn(
                        f"  ⚠ {proc} fault_code still = {actual}\n"
                        f"    Physical condition may not have recovered yet.\n"
                        f"    Use 'fault status {proc}' for details."
                    )
            return r

        if sub == "status":
            if len(args) < 2:
                r.error("Usage: fault status <process>")
                return r
            proc = args[1].lower()
            if proc not in PROCESS_NAMES:
                r.error(f"Unknown process: {proc!r}")
                return r
            val = self._plant_tag(proc, "fault_code")
            text = self._plant_tag(proc, "fault_text") or ""
            if val is None:
                r.error(f"No data for {proc} — is process online?")
                return r
            try:
                code = int(val)
            except (TypeError, ValueError):
                code = -1
            style = "green" if code == 0 else "red"
            r.add(f"  {proc} fault_code = {code}  ({text})", style)
            # Show full description
            desc = FAULT_CODES.get(proc, {}).get(code, "Unknown code")
            r.dim(f"  {desc}")
            if code != 0:
                r.dim("")
                for line in _reset_note_short():
                    r.dim(f"  {line}")
            return r

        if sub == "inject":
            if len(args) < 3:
                r.error("Usage: fault inject <process> <code>")
                return r
            proc = args[1].lower()
            if proc not in PROCESS_NAMES:
                r.error(f"Unknown process: {proc!r}")
                return r
            try:
                code = int(args[2])
            except ValueError:
                r.error(f"Invalid fault code: {args[2]!r}")
                return r
            info = self._tag_info(proc, "fault_code")
            if info is None:
                r.error(f"No fault_code tag for {proc}")
                return r
            register, _, _, _ = info
            write_result = await self._rest.write_register(proc, register, code)
            if write_result and write_result.get("ok"):
                r.warn(f"  [FAULT INJECT] {proc} fault_code forced to {code}")
            else:
                r.error(f"  Write failed")
            return r

        r.error(f"Unknown fault subcommand: {sub!r}. Use: clear, status, inject")
        return r

    async def cmd_watch(self, args: list) -> ExecutorResult:
        """
        Returns a result explaining that watch runs as a loop.
        Actual watch loop is implemented in the CLI shell / TUI separately,
        because it blocks and needs Ctrl+C handling.
        This method returns the watch config so the caller can start the loop.
        """
        r = ExecutorResult()
        if not args:
            r.error("Usage: watch <process> [tag] [--interval <sec>]")
            return r
        r.ok = True
        r.add("__WATCH__", "dim")   # sentinel — CLI shell handles this
        return r

    async def cmd_alarms(self, args: list) -> ExecutorResult:
        r = ExecutorResult()

        if not args or args[0].lower() not in ("history", "acknowledge", "filter"):
            # Show active alarms
            alarms = await self._rest.get_alarms()
            if alarms is None:
                r.error("Failed to fetch alarms")
                return r
            if not alarms:
                r.success("  No active alarms")
                return r
            r.add(f"  {'TIME':<10} {'ID':<10} {'SEV':<6} {'PROCESS':<22} {'DESCRIPTION'}", "dim")
            r.dim("  " + "─" * 80)
            for alarm in alarms:
                sev   = alarm.get("sev", "")
                style = {"CRIT": "red", "HIGH": "amber", "MED": "amber", "LOW": "normal"}.get(sev, "normal")
                acked = "✓" if alarm.get("acked") else " "
                r.add(
                    f"  {alarm.get('ts',''):<10} "
                    f"{alarm.get('id',''):<10} "
                    f"{sev:<6} "
                    f"{alarm.get('process',''):<22} "
                    f"{acked} {alarm.get('desc','')}",
                    style,
                )
            return r

        sub = args[0].lower()

        if sub == "history":
            history = await self._rest.get_alarm_history()
            if history is None:
                r.error("Failed to fetch alarm history")
                return r
            recent = history[-20:] if len(history) > 20 else history
            if not recent:
                r.dim("  No alarm history")
                return r
            r.add(f"  {'TIME':<10} {'ID':<10} {'SEV':<6} {'PROCESS':<22} {'DESCRIPTION'}", "dim")
            r.dim("  " + "─" * 80)
            for alarm in reversed(recent):
                sev   = alarm.get("sev", "")
                style = {"CRIT": "red", "HIGH": "amber"}.get(sev, "dim")
                r.add(
                    f"  {alarm.get('ts',''):<10} "
                    f"{alarm.get('id',''):<10} "
                    f"{sev:<6} "
                    f"{alarm.get('process',''):<22} "
                    f"{alarm.get('desc','')}",
                    style,
                )
            return r

        if sub == "acknowledge":
            if len(args) < 2:
                r.error("Usage: alarms acknowledge <alarm_id>  or  alarms acknowledge all")
                return r
            alarm_id = args[1]
            result = await self._rest.ack_alarm(alarm_id, self._op)
            if result is None:
                r.error("ACK request failed")
                return r
            if result.get("ok"):
                acked = result.get("acked", alarm_id)
                r.success(f"  ✓ Acknowledged: {acked}  (operator: {self._op})")
            else:
                r.error(f"  ACK failed: {result.get('error', 'unknown')}")
            return r

        if sub == "filter":
            if len(args) < 2:
                r.error("Usage: alarms filter <CRIT|HIGH|MED|LOW|process_name>")
                return r
            filt = args[1].upper()
            alarms = await self._rest.get_alarms()
            if alarms is None:
                r.error("Failed to fetch alarms")
                return r
            severity_values = {"CRIT", "HIGH", "MED", "LOW"}
            if filt in severity_values:
                filtered = [a for a in alarms if a.get("sev", "").upper() == filt]
            else:
                # Filter by process name
                proc = args[1].lower()
                filtered = [a for a in alarms if a.get("process", "").lower() == proc]

            if not filtered:
                r.dim(f"  No alarms matching {args[1]!r}")
                return r
            r.add(f"  {len(filtered)} alarm(s) matching {args[1]!r}", "dim")
            for alarm in filtered:
                sev   = alarm.get("sev", "")
                style = {"CRIT": "red", "HIGH": "amber"}.get(sev, "normal")
                r.add(f"  [{sev}] {alarm.get('id','')} — {alarm.get('desc','')}", style)
            return r

        return r

    async def cmd_plc(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        if len(args) < 2:
            r.error("Usage: plc <process> <status|source|reload|upload|validate|download|diff|variables>")
            return r

        process = args[0].lower()
        sub     = args[1].lower()

        if process not in PROCESS_NAMES:
            r.error(f"Unknown process: {process!r}")
            return r

        # ── status ────────────────────────────────────────────────────────────
        if sub == "status":
            data = await self._rest.plc_get_status(process)
            if data is None:
                r.error(f"Failed to get PLC status for {process}")
                return r
            loaded  = data.get("loaded", False)
            scans   = data.get("scan_count", 0)
            err     = data.get("last_error", "")
            pf      = data.get("program_file", "")
            r.add(f"  PLC Status — {process}", "cyan")
            r.dim("  " + "─" * 48)
            r.add(f"  Loaded:       {'YES' if loaded else 'NO'}", "green" if loaded else "red")
            r.add(f"  Scan count:   {scans}", "white")
            r.add(f"  Last error:   {err or 'none'}", "red" if err else "dim")
            r.add(f"  Program file: {pf}", "dim")
            return r

        # ── source ────────────────────────────────────────────────────────────
        if sub == "source":
            data = await self._rest.plc_get_program(process)
            if data is None:
                r.error(f"Failed to get PLC program for {process}")
                return r
            source = data.get("source", "")
            if not source:
                r.warn("  No source returned")
                return r
            r.add(f"  ST Source — {process}", "cyan")
            r.dim("  " + "─" * 48)
            for i, line in enumerate(source.splitlines(), 1):
                r.add(f"  {i:>4}  {line}", "normal")
            return r

        # ── variables ─────────────────────────────────────────────────────────
        if sub == "variables":
            data = await self._rest.plc_get_variables(process)
            if data is None:
                r.error(f"Failed to get variables for {process}")
                return r
            r.add(f"  PLC Variables — {process}", "cyan")
            r.dim("  " + "─" * 48)
            var_data = data.get("variables", data)
            for section in ("inputs", "outputs", "parameters"):
                items = var_data.get(section, {})
                if items:
                    r.add(f"  {section.upper()}:", "amber")
                    for k, v in items.items():
                        r.dim(f"    {k:<30} {v}")
            return r

        # ── reload ────────────────────────────────────────────────────────────
        if sub == "reload":
            result = await self._rest.plc_reload(process)
            if result is None:
                r.error(f"Reload request failed for {process}")
                return r
            if result.get("ok"):
                r.success(f"  ✓ {process} PLC program reloaded from disk")
                status = result.get("status", {})
                if status.get("last_error"):
                    r.warn(f"  Parse error after reload: {status['last_error']}")
                else:
                    r.dim(f"  Scan count: {status.get('scan_count', '?')}")
            else:
                r.error(f"  Reload failed: {result.get('error', 'unknown')}")
            return r

        # ── upload ────────────────────────────────────────────────────────────
        if sub == "upload":
            if len(args) < 3:
                r.error("Usage: plc <process> upload <filepath>")
                return r
            filepath = os.path.expanduser(args[2])
            if not os.path.exists(filepath):
                r.error(f"File not found: {filepath}")
                return r
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
            except OSError as e:
                r.error(f"Cannot read file: {e}")
                return r

            r.dim(f"  Uploading {filepath} ({len(source)} chars) to {process}...")
            result = await self._rest.plc_upload(process, source)
            if result is None:
                r.error("Upload request failed")
                return r
            if result.get("ok"):
                r.success(f"  ✓ Upload successful — {process} PLC program updated")
                status = result.get("status", {})
                if status.get("last_error"):
                    r.warn(f"  Warning: {status['last_error']}")
                else:
                    r.dim(f"  Scan count: {status.get('scan_count', '?')}")
            else:
                r.error(f"  Upload failed: {result.get('error', 'unknown')}")
            return r

        # ── validate ──────────────────────────────────────────────────────────
        if sub == "validate":
            if len(args) < 3:
                r.error("Usage: plc <process> validate <filepath>")
                return r
            filepath = os.path.expanduser(args[2])
            if not os.path.exists(filepath):
                r.error(f"File not found: {filepath}")
                return r
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
            except OSError as e:
                r.error(f"Cannot read file: {e}")
                return r

            r.dim(f"  Validating {filepath}...")
            # Server validates on upload — we upload to a validate endpoint
            # The server's POST /plc/<process>/program validates before applying.
            # We use the same endpoint — if ok=True the source was valid.
            # But we don't want to actually apply it here.
            # So we read back the current source after, to verify nothing changed.
            # Actually — the server always applies on upload.
            # Best we can do: attempt upload, note that it applied if valid.
            r.warn(
                "  Note: Server validates and applies simultaneously.\n"
                "  'validate' uploads the source. If valid, it becomes active.\n"
                "  Use 'plc <process> download <backup>' first to save current."
            )
            result = await self._rest.plc_upload(process, source)
            if result is None:
                r.error("Validation request failed")
                return r
            if result.get("ok"):
                r.success(f"  ✓ Valid — {process} PLC program updated")
            else:
                r.error(f"  ✗ Parse error: {result.get('error', 'unknown')}")
            return r

        # ── download ──────────────────────────────────────────────────────────
        if sub == "download":
            if len(args) < 3:
                r.error("Usage: plc <process> download <filepath>")
                return r
            filepath = os.path.expanduser(args[2])
            data = await self._rest.plc_get_program(process)
            if data is None:
                r.error(f"Failed to fetch program for {process}")
                return r
            source = data.get("source", "")
            if not source:
                r.warn("  No source returned from server")
                return r
            try:
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(source)
                r.success(f"  ✓ Saved {len(source)} chars to {filepath}")
            except OSError as e:
                r.error(f"Cannot write file: {e}")
            return r

        # ── diff ──────────────────────────────────────────────────────────────
        if sub == "diff":
            if len(args) < 3:
                r.error("Usage: plc <process> diff <filepath>")
                return r
            filepath = os.path.expanduser(args[2])
            if not os.path.exists(filepath):
                r.error(f"File not found: {filepath}")
                return r
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    local_source = f.read()
            except OSError as e:
                r.error(f"Cannot read file: {e}")
                return r

            data = await self._rest.plc_get_program(process)
            if data is None:
                r.error(f"Failed to fetch running program for {process}")
                return r
            running_source = data.get("source", "")

            if running_source == local_source:
                r.success(f"  ✓ No differences — running program matches {filepath}")
                return r

            diff = list(difflib.unified_diff(
                running_source.splitlines(keepends=True),
                local_source.splitlines(keepends=True),
                fromfile=f"running ({process})",
                tofile=filepath,
                lineterm="",
            ))

            if not diff:
                r.success("  ✓ No differences")
                return r

            r.warn(f"  Differences found ({len(diff)} lines):")
            r.dim("  " + "─" * 48)
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    r.add(f"  {line}", "green")
                elif line.startswith("-") and not line.startswith("---"):
                    r.add(f"  {line}", "red")
                elif line.startswith("@@"):
                    r.add(f"  {line}", "cyan")
                else:
                    r.dim(f"  {line}")
            return r

        r.error(f"Unknown PLC subcommand: {sub!r}")
        return r

    async def cmd_modbus(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        if not args:
            r.error("Usage: modbus <read|write|dump> <process> ...")
            return r

        sub = args[0].lower()

        if sub == "dump":
            if len(args) < 2:
                r.error("Usage: modbus dump <process>")
                return r
            process = args[1].lower()
            if process not in PROCESS_NAMES:
                r.error(f"Unknown process: {process!r}")
                return r
            snapshot = self._plant()
            if not snapshot:
                snapshot = await self._rest.get_data()
            if not snapshot:
                r.error("No data available")
                return r
            proc_data = snapshot.get(process, {})
            tag_map   = TAG_MAP.get(process, {})

            r.add(f"  Modbus dump — {process}", "cyan")
            r.add(f"  {'REG':<4} {'RAW':>6}  {'ENG VALUE':<20} {'UNIT':<10} {'TAG'}", "dim")
            r.dim("  " + "─" * 72)

            for tag, (reg, scale, unit, writable) in sorted(tag_map.items(), key=lambda x: x[1][0]):
                eng_val = proc_data.get(tag)
                if eng_val is None:
                    raw = "?"
                    eng_str = "N/A"
                else:
                    try:
                        raw = int(round(float(eng_val) * scale))
                        eng_str = str(eng_val)
                    except (TypeError, ValueError):
                        raw = "?"
                        eng_str = str(eng_val)
                w = "W" if writable else " "
                r.add(f"  {reg:<4} {str(raw):>6}  {eng_str:<20} {unit:<10} {w} {tag}", "normal")
            return r

        if sub == "read":
            if len(args) < 4:
                r.error("Usage: modbus read <process> <start_reg> <count>")
                return r
            process = args[1].lower()
            try:
                start = int(args[2])
                count = int(args[3])
            except ValueError:
                r.error("start_reg and count must be integers")
                return r
            r.warn("  Note: modbus read uses server /data endpoint (no direct Modbus).")
            r.warn("  For raw Modbus, connect directly to PLC port from another tool.")
            r.dim(f"  Showing registers {start}–{start+count-1} from {process}:")
            snapshot = self._plant()
            if not snapshot:
                snapshot = await self._rest.get_data()
            if not snapshot:
                r.error("No data")
                return r
            proc_data = snapshot.get(process, {})
            tag_map   = TAG_MAP.get(process, {})
            for tag, (reg, scale, unit, _) in sorted(tag_map.items(), key=lambda x: x[1][0]):
                if start <= reg < start + count:
                    val = proc_data.get(tag, "N/A")
                    try:
                        raw = int(round(float(val) * scale))
                    except (TypeError, ValueError):
                        raw = "?"
                    r.add(f"  {reg:<4} {str(raw):>6}  {val}  {unit}  ({tag})", "normal")
            return r

        if sub == "write":
            if len(args) < 4:
                r.error("Usage: modbus write <process> <register> <raw_value>")
                return r
            process = args[1].lower()
            if process not in PROCESS_NAMES:
                r.error(f"Unknown process: {process!r}")
                return r
            try:
                register  = int(args[2])
                raw_value = int(args[3])
            except ValueError:
                r.error("register and raw_value must be integers")
                return r
            if not (0 <= raw_value <= 65535):
                r.error(f"raw_value {raw_value} out of range 0-65535")
                return r
            r.warn(f"  [RAW MODBUS] writing reg {register} = {raw_value} to {process}")
            result = await self._rest.write_register(process, register, raw_value)
            if result and result.get("ok"):
                r.success(f"  ✓ Write confirmed by server")
            else:
                r.error(f"  Write failed: {result}")
            return r

        r.error(f"Unknown modbus subcommand: {sub!r}. Use: read, write, dump")
        return r

    async def cmd_snapshot(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        snapshot = self._plant()
        if not snapshot:
            snapshot = await self._rest.get_data()
        if not snapshot:
            r.error("No data — is the server online?")
            return r

        filepath = None
        if "--file" in args:
            idx = args.index("--file")
            if idx + 1 < len(args):
                filepath = os.path.expanduser(args[idx + 1])

        if filepath:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2)
                r.success(f"  ✓ Snapshot saved to {filepath}")
                r.dim(f"  Server time: {snapshot.get('server_time', '?')}")
                r.dim(f"  Poll count:  {snapshot.get('poll_count', '?')}")
            except OSError as e:
                r.error(f"Cannot write file: {e}")
        else:
            r.add("  Plant Snapshot", "cyan")
            r.dim("  " + "─" * 48)
            text = json.dumps(snapshot, indent=2)
            for line in text.splitlines():
                r.add(f"  {line}", "normal")

        return r

    async def cmd_status(self, args: list) -> ExecutorResult:
        r = ExecutorResult()
        health = await self._rest.get_health()
        if health is None:
            r.error("Server unreachable")
            return r

        r.add(f"  Server: {health.get('server', '?')}", "cyan")
        r.add(f"  Status: {health.get('status', '?')}", "green")
        r.dim(f"  Poll rate: {health.get('poll_rate_ms', '?')} ms")

        if args and args[0].lower() in PROCESS_NAMES:
            return await self.cmd_read([args[0]])

        snapshot = self._plant()
        if not snapshot:
            snapshot = await self._rest.get_data()
        if snapshot:
            r.dim("")
            for proc in PROCESS_NAMES:
                d = snapshot.get(proc, {})
                online = d.get("online", False)
                fault  = d.get("fault_code", 0)
                badge  = "●ONLINE" if online else "○OFFLINE"
                style  = "green" if online and fault == 0 else ("amber" if fault else "red")
                r.add(
                    f"  {proc:<25} {badge:<10} fault={fault}",
                    style,
                )
        return r

    async def cmd_help(self, args: list) -> ExecutorResult:
        r = ExecutorResult()

        if not args:
            r.add("  MORBION Scripting Language — Command Reference", "cyan")
            r.dim("  " + "═" * 52)
            for verb, text in COMMAND_HELP.items():
                first_line = text.splitlines()[0]
                r.add(f"  {verb:<12} {first_line}", "normal")
            r.dim("")
            r.dim("  Type 'help <verb>' for detailed usage.")
            r.dim("  Type 'help register <process>' for register map.")
            r.dim("  Type 'help faults <process>' for fault code table.")
            return r

        sub = args[0].lower()

        if sub == "register":
            if len(args) < 2:
                r.error("Usage: help register <process>")
                return r
            proc = args[1].lower()
            if proc not in PROCESS_NAMES:
                r.error(f"Unknown process: {proc!r}")
                return r
            for line in format_register_map(proc).splitlines():
                r.add(f"  {line}", "normal")
            return r

        if sub == "faults":
            if len(args) < 2:
                r.error("Usage: help faults <process>")
                return r
            proc = args[1].lower()
            if proc not in PROCESS_NAMES:
                r.error(f"Unknown process: {proc!r}")
                return r
            for line in format_fault_table(proc).splitlines():
                r.add(f"  {line}", "normal")
            return r

        if sub in COMMAND_HELP:
            r.add(f"  {sub}", "cyan")
            r.dim("  " + "─" * 48)
            for line in COMMAND_HELP[sub].splitlines():
                r.add(f"  {line}", "normal")
            return r

        r.error(f"Unknown verb: {sub!r}. Type 'help' for command list.")
        return r

    async def cmd_connect(self, args: list) -> ExecutorResult:
        """Returns result with new host/port — caller must reconnect."""
        r = ExecutorResult()
        if not args:
            r.error("Usage: connect <ip>:<port>")
            return r
        raw = args[0].strip()
        if ":" not in raw:
            r.error(f"Invalid format: {raw!r}. Use: connect <ip>:<port>")
            return r
        parts = raw.rsplit(":", 1)
        host  = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            r.error(f"Invalid port: {parts[1]!r}")
            return r
        r.add(f"__CONNECT__{host}:{port}", "dim")   # sentinel for shell
        return r


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unit(process: str, tag: str) -> str:
    info = TAG_MAP.get(process, {}).get(tag)
    if info:
        return info[2]
    return ""


def _alarm_style(process: str, tag: str, value) -> str:
    """Return style based on known alarm thresholds."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "normal"

    thresholds = {
        ("pumping_station", "tank_level_pct"):      ("hi", 90.0, "lo", 10.0),
        ("pumping_station", "discharge_pressure_bar"): ("hi", 8.0, None, None),
        ("heat_exchanger",  "T_cold_out_C"):         ("hi", 95.0, None, None),
        ("heat_exchanger",  "efficiency_pct"):        (None, None, "lo", 45.0),
        ("boiler",          "drum_pressure_bar"):     ("hi", 10.0, "lo", 6.0),
        ("boiler",          "drum_level_pct"):        ("hi", 80.0, "lo", 20.0),
        ("pipeline",        "outlet_pressure_bar"):   ("hi", 55.0, "lo", 30.0),
    }
    t = thresholds.get((process, tag))
    if not t:
        return "white"
    _, hi, _, lo = t
    if hi is not None and v >= hi:
        return "red"
    if lo is not None and v <= lo:
        return "amber"
    return "white"


def _reset_note_short() -> list:
    return [
        "To clear: resolve physical condition FIRST, then:",
        "  fault clear <process>  (writes 0 to reg 14)",
        "Latched faults only clear when BOTH conditions met.",
    ]
