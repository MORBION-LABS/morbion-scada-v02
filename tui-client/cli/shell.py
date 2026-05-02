"""
cli/shell.py — MORBION CLI Scripting Shell
MORBION SCADA v02

Full REPL with:
  - Tab completion (readline)
  - Arrow key history navigation
  - Live watch loop (Ctrl+C to stop)
  - Batch script runner
  - Snapshot command
  - All MSL verbs via Executor

Defensive programming throughout:
  - Every coroutine wrapped in try/except
  - All user input validated before execution
  - Ctrl+C and Ctrl+D handled cleanly at every level
  - Server disconnects handled — shell stays alive
"""

import asyncio
import os
import sys
import json
import datetime
from typing import Optional

# readline is Unix-only; on Windows use pyreadline3 or degrade gracefully
try:
    import readline
    _READLINE = True
except ImportError:
    _READLINE = False

from core.rest_client import RestClient
from core.ws_client import WSClient
from core.commands import (
    PROCESS_NAMES,
    TAG_MAP,
    get_completions,
    ALL_VERBS,
)
from core.executor import Executor, ExecutorResult
from core.history import CommandHistory
from cli.output import (
    console,
    print_result,
    print_banner,
    print_watch_line,
    print_error,
    print_info,
    print_success,
    print_warn,
    STYLE_MAP,
)


# ── Tab completer ──────────────────────────────────────────────────────────────

class _Completer:
    def __init__(self):
        self._matches = []

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            try:
                buf    = readline.get_line_buffer() if _READLINE else text
                tokens = buf.lstrip().split()
                # If buffer ends with space, start new token
                if buf and buf[-1] == " ":
                    tokens.append("")
                self._matches = get_completions(tokens)
            except Exception:
                self._matches = []
        try:
            return self._matches[state]
        except IndexError:
            return None


def _setup_readline(history: CommandHistory) -> None:
    """Configure readline for tab completion and history navigation."""
    if not _READLINE:
        return
    try:
        completer = _Completer()
        readline.set_completer(completer.complete)
        readline.set_completer_delims(" \t")
        readline.parse_and_bind("tab: complete")
        # Load existing history into readline buffer
        for entry in history.get_entries():
            try:
                readline.add_history(entry)
            except Exception:
                pass
    except Exception:
        pass  # Degrade gracefully — tab completion is a convenience


# ── Shell ──────────────────────────────────────────────────────────────────────

class CLIShell:
    """
    MORBION CLI REPL shell.

    run() is the blocking entry point. Returns when user types 'exit'.
    Internally uses asyncio.run() for each command — keeps it simple
    and avoids persistent event loop complexity.
    """

    PROMPT = "\n[#00d4ff]morbion ›[/#00d4ff] "

    def __init__(self, config: dict):
        self._config  = config
        self._host    = config.get("server_host", "")
        self._port    = int(config.get("server_port", 5000))
        self._op      = config.get("operator", "OPERATOR")
        self._verify  = int(config.get("verify_timeout_ms", 300))
        self._history = CommandHistory(config.get("history_file", "~/.morbion_history"))

        # Latest plant snapshot — updated by background WS task
        self._plant: dict = {}
        self._ws_connected = False

        # Watch stop flag
        self._watching = False

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Start the CLI shell. Blocks until user exits.
        Sets up WS background feed, then enters REPL loop.
        """
        if not self._host:
            print_error("No server configured. Run: python installer.py")
            return

        asyncio.run(self._run_async())

    # ── Async runtime ─────────────────────────────────────────────────────────

    async def _run_async(self) -> None:
        """Main async runtime: start WS feed, print banner, enter REPL."""
        async with RestClient(self._host, self._port) as rest:
            self._rest = rest
            self._executor = Executor(
                rest       = rest,
                get_plant  = lambda: self._plant,
                operator   = self._op,
                verify_timeout_ms = self._verify,
            )

            # Start WS background task
            ws = WSClient(
                host          = self._host,
                port          = self._port,
                on_data       = self._on_ws_data,
                on_connect    = self._on_ws_connect,
                on_disconnect = self._on_ws_disconnect,
            )
            ws_task = asyncio.create_task(ws.run())

            # Wait briefly for first WS data
            for _ in range(16):   # up to 1.6s
                if self._plant:
                    break
                await asyncio.sleep(0.1)

            # Determine online status for banner
            online  = ws.connected
            n_online = sum(
                1 for p in PROCESS_NAMES
                if self._plant.get(p, {}).get("online")
            )

            _setup_readline(self._history)
            print_banner(self._host, self._port, online, n_online)

            try:
                await self._repl_loop()
            finally:
                ws.stop()
                ws_task.cancel()
                try:
                    await ws_task
                except (asyncio.CancelledError, Exception):
                    pass

    def _on_ws_data(self, data: dict) -> None:
        """Called on every WS push. Update local plant snapshot."""
        if isinstance(data, dict):
            self._plant = data
            self._ws_connected = True

    async def _on_ws_connect(self) -> None:
        self._ws_connected = True

    async def _on_ws_disconnect(self) -> None:
        self._ws_connected = False

    # ── REPL loop ─────────────────────────────────────────────────────────────

    async def _repl_loop(self) -> None:
        """Main input loop. Returns on 'exit' or Ctrl+D."""
        while True:
            try:
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, self._prompt_input
                )
            except EOFError:
                # Ctrl+D
                print_info("\nExiting CLI...")
                break
            except KeyboardInterrupt:
                # Ctrl+C at prompt — clear line, continue
                console.print()
                continue
            except Exception as e:
                print_error(f"Input error: {e}")
                continue

            if raw is None:
                continue

            line = raw.strip()
            if not line:
                continue

            # Record in history
            self._history.append(line)

            # Dispatch
            should_exit = await self._dispatch(line)
            if should_exit:
                break

    def _prompt_input(self) -> Optional[str]:
        """Synchronous input with Rich prompt. Returns None on empty."""
        try:
            console.print(self.PROMPT, end="")
            return input()
        except EOFError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception:
            return None

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, line: str) -> bool:
        """
        Parse and execute one command line.
        Returns True if shell should exit.
        Defensive: catches all exceptions per command.
        """
        tokens = line.split()
        if not tokens:
            return False

        verb = tokens[0].lower()
        args = tokens[1:]

        # Exit
        if verb in ("exit", "quit", "q"):
            print_info("Returning to main menu...")
            return True

        # Clear
        if verb in ("cls", "clear"):
            os.system("clear" if os.name != "nt" else "cls")
            return False

        # History
        if verb == "history":
            self._cmd_history(args)
            return False

        # Connect
        if verb == "connect":
            await self._cmd_connect(args)
            return False

        # Batch
        if verb == "batch":
            await self._cmd_batch(args)
            return False

        # Snapshot
        if verb == "snapshot":
            result = await self._executor.cmd_snapshot(args)
            print_result(result)
            return False

        # Watch
        if verb == "watch":
            await self._cmd_watch(args)
            return False

        # Unwatch (no-op in sync shell — watch is blocking)
        if verb == "unwatch":
            print_info("No active watch monitors.")
            return False

        # Diff (top-level shortcut)
        if verb == "diff":
            if args:
                result = await self._executor.cmd_plc([args[0], "diff"] + args[1:])
                print_result(result)
            else:
                print_error("Usage: diff <process> <filepath>")
            return False

        # Route to executor
        handler_map = {
            "read":     self._executor.cmd_read,
            "write":    lambda a: self._executor.cmd_write(a, "write"),
            "inject":   self._executor.cmd_inject,
            "fault":    self._executor.cmd_fault,
            "alarms":   self._executor.cmd_alarms,
            "plc":      self._executor.cmd_plc,
            "modbus":   self._executor.cmd_modbus,
            "status":   self._executor.cmd_status,
            "help":     self._executor.cmd_help,
        }

        handler = handler_map.get(verb)
        if handler:
            try:
                result = await handler(args)
                print_result(result)
                # Check for connect sentinel
                if result and result.lines:
                    for text, _ in result.lines:
                        if isinstance(text, str) and text.startswith("__CONNECT__"):
                            addr = text.replace("__CONNECT__", "")
                            await self._cmd_connect([addr])
            except Exception as e:
                print_error(f"Command error ({verb}): {e}")
        else:
            print_error(
                f"Unknown command: {verb!r}. "
                f"Type 'help' for command list."
            )

        return False

    # ── Watch loop ────────────────────────────────────────────────────────────

    async def _cmd_watch(self, args: list) -> None:
        """
        Live watch loop. Ctrl+C to stop.
        Defensive: validates args, handles KeyboardInterrupt cleanly.
        """
        if not args:
            print_error("Usage: watch <process> [tag] [--interval <sec>]")
            return

        # Parse --interval flag
        interval = 1.0
        clean_args = []
        i = 0
        while i < len(args):
            if args[i] == "--interval" and i + 1 < len(args):
                try:
                    interval = float(args[i + 1])
                    if interval <= 0:
                        raise ValueError
                except ValueError:
                    print_error(f"Invalid interval: {args[i+1]!r}. Must be > 0.")
                    return
                i += 2
            else:
                clean_args.append(args[i])
                i += 1

        if not clean_args:
            print_error("Usage: watch <process> [tag] [--interval <sec>]")
            return

        target = clean_args[0].lower()

        # Determine what to watch
        if target == "all":
            watch_specs = [
                (proc, "tank_level_pct"     if proc == "pumping_station" else
                       "drum_pressure_bar"   if proc == "boiler" else
                       "outlet_pressure_bar" if proc == "pipeline" else
                       "efficiency_pct")
                for proc in PROCESS_NAMES
            ]
        elif target in PROCESS_NAMES:
            if len(clean_args) >= 2:
                tag = clean_args[1]
                if tag not in TAG_MAP.get(target, {}):
                    print_error(
                        f"Unknown tag {tag!r} for {target}. "
                        f"Use: help register {target}"
                    )
                    return
                watch_specs = [(target, tag)]
            else:
                # Watch key tags for this process
                key_tags = {
                    "pumping_station": ["tank_level_pct", "pump_flow_m3hr", "fault_code"],
                    "heat_exchanger":  ["efficiency_pct", "T_cold_out_C", "fault_code"],
                    "boiler":          ["drum_pressure_bar", "drum_level_pct", "fault_code"],
                    "pipeline":        ["outlet_pressure_bar", "flow_rate_m3hr", "fault_code"],
                }
                watch_specs = [(target, t) for t in key_tags.get(target, ["fault_code"])]
        else:
            print_error(
                f"Unknown process: {target!r}. "
                f"Valid: {', '.join(PROCESS_NAMES)} or 'all'"
            )
            return

        specs_str = ", ".join(f"{p}.{t}" for p, t in watch_specs)
        print_info(f"Watching {specs_str} every {interval}s — Ctrl+C to stop")
        print_info("─" * 60)

        self._watching = True
        try:
            while self._watching:
                now = datetime.datetime.now().strftime("%H:%M:%S")
                for proc, tag in watch_specs:
                    try:
                        val  = self._plant.get(proc, {}).get(tag)
                        unit = TAG_MAP.get(proc, {}).get(tag, ("", 1, "", False))[2]
                        print_watch_line(now, proc, tag, val, unit)
                    except Exception:
                        print_watch_line(now, proc, tag, "ERROR", "")
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            print_info("\nWatch stopped.")
        finally:
            self._watching = False

    # ── Batch runner ──────────────────────────────────────────────────────────

    async def _cmd_batch(self, args: list) -> None:
        """
        Run a .morbion batch script file.
        Defensive: file existence, read errors, per-line exceptions.
        """
        if not args:
            print_error("Usage: batch <filepath>")
            return

        filepath = os.path.expanduser(args[0])
        if not os.path.exists(filepath):
            print_error(f"File not found: {filepath}")
            return
        if not os.path.isfile(filepath):
            print_error(f"Not a file: {filepath}")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            print_error(f"Cannot read file: {e}")
            return

        print_info(f"Running batch: {filepath} ({len(lines)} lines)")
        print_info("─" * 60)

        errors = 0
        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            print_info(f"  [{line_num:>3}] {line}")
            try:
                should_exit = await self._dispatch(line)
                if should_exit:
                    print_info("  batch: 'exit' encountered — stopping batch")
                    break
            except Exception as e:
                print_error(f"  Line {line_num}: {e}")
                errors += 1
                # Continue on error — do not abort batch

        if errors:
            print_warn(f"Batch complete with {errors} error(s).")
        else:
            print_success("Batch complete — no errors.")

    # ── History display ───────────────────────────────────────────────────────

    def _cmd_history(self, args: list) -> None:
        """Display command history."""
        if args and args[0].lower() == "search" and len(args) >= 2:
            term    = " ".join(args[1:])
            results = self._history.search_entries(term)
            if not results:
                print_info(f"No history entries matching {term!r}")
                return
            for i, entry in enumerate(results, 1):
                console.print(f"  [#4a7a8c]{i:>4}[/#4a7a8c]  [#d0e8f0]{entry}[/#d0e8f0]")
            return

        try:
            n = int(args[0]) if args else 50
        except ValueError:
            n = 50

        entries = self._history.get_entries(n)
        if not entries:
            print_info("No history yet.")
            return
        for i, entry in enumerate(entries, 1):
            console.print(f"  [#4a7a8c]{i:>4}[/#4a7a8c]  [#d0e8f0]{entry}[/#d0e8f0]")

    # ── Connect ───────────────────────────────────────────────────────────────

    async def _cmd_connect(self, args: list) -> None:
        """
        Change server connection.
        Defensive: validates format, saves config, warns about restart needed.
        """
        if not args:
            print_error("Usage: connect <ip>:<port>")
            return

        raw = args[0].strip()
        if ":" not in raw:
            print_error(f"Invalid format: {raw!r}. Use ip:port")
            return

        parts = raw.rsplit(":", 1)
        host  = parts[0].strip()
        if not host:
            print_error("Host cannot be empty")
            return
        try:
            port = int(parts[1])
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            print_error(f"Invalid port: {parts[1]!r}. Must be 1-65535")
            return

        # Save to config
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "config.json"
        )
        config_path = os.path.normpath(config_path)
        try:
            existing = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    existing = json.load(f)
            existing["server_host"] = host
            existing["server_port"] = port
            with open(config_path, "w") as f:
                json.dump(existing, f, indent=2)
        except OSError as e:
            print_warn(f"Could not save config: {e}")

        print_success(f"  ✓ Server address updated: {host}:{port}")
        print_info("  Restart CLI to connect to new server.")
