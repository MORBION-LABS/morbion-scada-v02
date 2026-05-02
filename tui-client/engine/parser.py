"""
parser.py — MSL Command Parser
MORBION SCADA v02

Tokenizes and validates terminal input against the MSL specification.
Enforces Rule 3 (Exact Identifiers).
"""

import shlex
from typing import Dict, Any, List, Optional
from engine.commands import TAG_MAP

VALID_PROCESSES = {"pumping_station", "heat_exchanger", "boiler", "pipeline"}

class MSLParserError(Exception):
    """Raised when command syntax or identifiers are invalid."""
    pass

class MSLParser:
    """
    Recursive descent style parser for MORBION Scripting Language.
    Returns a dictionary containing 'verb', 'args', and 'flags'.
    """

    @staticmethod
    def parse(raw_input: str) -> Dict[str, Any]:
        if not raw_input.strip():
            return {"verb": "nop", "args": [], "flags": {}}

        # Use shlex to handle quoted arguments (e.g. for paths in 'batch')
        try:
            tokens = shlex.split(raw_input)
        except ValueError as e:
            raise MSLParserError(f"Tokenization error: {e}")

        verb = tokens[0].lower()
        args = tokens[1:]
        flags = {}

        # ── Verb Dispatch ────────────────────────────────────────────────────
        
        if verb == "read":
            return MSLParser._parse_read(args)
        
        elif verb in ("write", "inject"):
            return MSLParser._parse_write(verb, args)
        
        elif verb == "fault":
            return MSLParser._parse_fault(args)
        
        elif verb == "watch":
            return MSLParser._parse_watch(args)
        
        elif verb == "plc":
            return MSLParser._parse_plc(args)
        
        elif verb == "modbus":
            return MSLParser._parse_modbus(args)
        
        elif verb == "alarms":
            return MSLParser._parse_alarms(args)

        # Simple Verbs (no complex arg parsing needed)
        elif verb in ("unwatch", "status", "connect", "batch", "history", "help", "cls"):
            return {"verb": verb, "args": args, "flags": {}}

        else:
            raise MSLParserError(f"Unknown verb: '{verb}'. Type 'help' for vocabulary.")

    # ── Internal Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_read(args: List[str]) -> Dict[str, Any]:
        if not args:
            raise MSLParserError("Syntax: read <process> [tag] or read all")
        
        target = args[0].lower()
        if target != "all" and target not in VALID_PROCESSES:
            raise MSLParserError(f"Invalid process: '{target}'. Use full name.")
        
        return {"verb": "read", "args": args, "flags": {}}

    @staticmethod
    def _parse_write(verb: str, args: List[str]) -> Dict[str, Any]:
        if len(args) < 3:
            raise MSLParserError(f"Syntax: {verb} <process> <tag> <value>")
        
        process, tag, value = args[0].lower(), args[1].lower(), args[2]
        
        if process not in VALID_PROCESSES:
            raise MSLParserError(f"Invalid process: '{process}'")
        
        if tag not in TAG_MAP[process]:
            raise MSLParserError(f"Invalid tag '{tag}' for process '{process}'")
        
        try:
            float(value)
        except ValueError:
            raise MSLParserError(f"Value '{value}' must be numeric.")
            
        return {"verb": "write", "args": [process, tag, value], "flags": {}}

    @staticmethod
    def _parse_fault(args: List[str]) -> Dict[str, Any]:
        if len(args) < 2:
            raise MSLParserError("Syntax: fault <clear|status|inject> <process|all> [code]")
        
        sub_verb = args[0].lower()
        target = args[1].lower()
        
        if sub_verb not in ("clear", "status", "inject"):
            raise MSLParserError(f"Invalid fault action: '{sub_verb}'")
            
        if target != "all" and target not in VALID_PROCESSES:
            raise MSLParserError(f"Invalid process: '{target}'")
            
        return {"verb": "fault", "sub_verb": sub_verb, "args": args[1:], "flags": {}}

    @staticmethod
    def _parse_watch(args: List[str]) -> Dict[str, Any]:
        if not args:
            raise MSLParserError("Syntax: watch <process|all> [tag] [--interval s]")
        
        clean_args = []
        flags = {"interval": 1.0}
        
        i = 0
        while i < len(args):
            if args[i] == "--interval" and i + 1 < len(args):
                flags["interval"] = float(args[i+1])
                i += 2
            else:
                clean_args.append(args[i])
                i += 1
                
        return {"verb": "watch", "args": clean_args, "flags": flags}

    @staticmethod
    def _parse_plc(args: List[str]) -> Dict[str, Any]:
        if len(args) < 2:
            raise MSLParserError("Syntax: plc <process> <status|source|reload|upload|download|validate>")
        
        process = args[0].lower()
        if process not in VALID_PROCESSES:
            raise MSLParserError(f"Invalid process: '{process}'")
            
        return {"verb": "plc", "process": process, "sub_verb": args[1].lower(), "args": args[2:], "flags": {}}

    @staticmethod
    def _parse_modbus(args: List[str]) -> Dict[str, Any]:
        if len(args) < 2:
            raise MSLParserError("Syntax: modbus <read|write|dump> <process> ...")
            
        process = args[1].lower()
        if process not in VALID_PROCESSES:
            raise MSLParserError(f"Invalid process: '{process}'")
            
        return {"verb": "modbus", "sub_verb": args[0].lower(), "process": process, "args": args[2:], "flags": {}}

    @staticmethod
    def _parse_alarms(args: List[str]) -> Dict[str, Any]:
        # 'alarms' on its own is valid (shows active)
        if not args:
            return {"verb": "alarms", "sub_verb": "active", "args": [], "flags": {}}
            
        return {"verb": "alarms", "sub_verb": args[0].lower(), "args": args[1:], "flags": {}}
