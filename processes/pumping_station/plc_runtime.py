"""
plc_runtime.py — Pumping Station PLC Runtime
MORBION SCADA v02

Wraps the ST interpreter. Loads plc_program.st from disk.
Executes every scan cycle against ProcessState.
Supports hot reload via reload() method — no process restart needed.
Maps ST variables to ProcessState fields via plc_variables.yaml.

Thread safety: _lock protects interpreter swap during hot reload.
The scan loop holds the lock only for the duration of execute().
"""

import logging
import os
import threading
from typing import Optional

import yaml

from shared.st_runtime.interpreter import Interpreter
from shared.st_runtime.parser import parse_st, ParseError
from shared.st_runtime.lexer import LexerError

log = logging.getLogger("plc_runtime.pumping_station")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PROG_PATH  = os.path.join(BASE_DIR, "plc_program.st")
VARS_PATH  = os.path.join(BASE_DIR, "plc_variables.yaml")


class PLCRuntime:
    """
    PLC Runtime for pumping station.

    Lifecycle:
        runtime = PLCRuntime()          # loads program on construction
        runtime.scan(state)             # call every scan cycle
        runtime.reload()                # hot reload from file
        runtime.upload_program(source)  # upload new source, validate first
    """

    def __init__(self):
        self._lock         = threading.Lock()
        self._interpreter: Optional[Interpreter] = None
        self._var_map      = {}
        self._last_error   = ""
        self._scan_count   = 0
        self._load()

    # ── Load / Reload ─────────────────────────────────────────────────────────

    def _load(self):
        """Load program and variable map from files. Called on init and reload."""
        try:
            with open(VARS_PATH, 'r') as f:
                self._var_map = yaml.safe_load(f)

            with open(PROG_PATH, 'r') as f:
                source = f.read()

            program = parse_st(source)
            interp  = Interpreter(program)

            with self._lock:
                self._interpreter = interp
                self._last_error  = ""

            log.info("PLC program loaded: %s", PROG_PATH)

        except (LexerError, ParseError) as e:
            self._last_error = f"Parse error: {e}"
            log.error("PLC program parse error: %s", e)
        except FileNotFoundError as e:
            self._last_error = f"File not found: {e}"
            log.error("PLC program file not found: %s", e)
        except Exception as e:
            self._last_error = str(e)
            log.error("PLC program load error: %s", e)

    def reload(self):
        """Hot reload program from file. Safe to call from any thread."""
        log.info("Reloading PLC program...")
        self._load()

    def upload_program(self, source: str) -> bool:
        """
        Validate and upload new ST source.
        Writes to file then reloads. Returns True on success.
        """
        try:
            parse_st(source)   # validate before writing
            with open(PROG_PATH, 'w') as f:
                f.write(source)
            self._load()
            return self._interpreter is not None
        except (LexerError, ParseError) as e:
            self._last_error = f"Parse error: {e}"
            log.error("Program upload rejected — parse error: %s", e)
            return False
        except Exception as e:
            self._last_error = str(e)
            log.error("Program upload failed: %s", e)
            return False

    # ── Scan ──────────────────────────────────────────────────────────────────

    def scan(self, state, dt: float = 0.1) -> None:
        """
        Execute one PLC scan cycle.
        Reads inputs from ProcessState.
        Executes ST program.
        Writes outputs back to ProcessState.
        Never raises — all errors logged internally.
        """
        with self._lock:
            if self._interpreter is None:
                return
            interp = self._interpreter

        inputs     = self._var_map.get("inputs",     {})
        outputs    = self._var_map.get("outputs",    {})
        parameters = self._var_map.get("parameters", {})

        # Build variable dict from ProcessState
        variables = {}
        with state:
            for st_var, state_field in inputs.items():
                variables[st_var.upper()] = getattr(state, state_field, 0)
        for st_var, val in parameters.items():
            variables[st_var.upper()] = val

        # Execute ST program
        try:
            result = interp.execute(variables, dt)
            self._scan_count += 1
        except Exception as e:
            log.error("PLC scan execute error: %s", e)
            return

        # Write outputs back to ProcessState
        with state:
            for st_var, state_field in outputs.items():
                key = st_var.upper()
                if key in result:
                    try:
                        current = getattr(state, state_field, None)
                        val     = result[key]
                        # Preserve type — bool stays bool, float stays float
                        if isinstance(current, bool):
                            val = bool(val)
                        elif isinstance(current, float):
                            val = float(val)
                        elif isinstance(current, int):
                            val = int(val)
                        setattr(state, state_field, val)
                    except AttributeError:
                        pass

    # ── Status and introspection ──────────────────────────────────────────────

    @property
    def status(self) -> dict:
        return {
            "loaded":       self._interpreter is not None,
            "last_error":   self._last_error,
            "scan_count":   self._scan_count,
            "program_file": PROG_PATH,
        }

    @property
    def program_source(self) -> str:
        try:
            with open(PROG_PATH, 'r') as f:
                return f.read()
        except Exception:
            return ""

    @property
    def variables(self) -> dict:
        return dict(self._var_map)