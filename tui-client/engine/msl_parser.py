"""
msl_parser.py — MSL Lexical Analysis
MORBION SCADA v02 — REBOOT
"""
import shlex

class MSLParser:
    VALID_VERBS = ["read", "write", "inject", "watch", "unwatch", "mode", "plc", "clear", "help"]
    VALID_PROCS = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]

    @staticmethod
    def parse(cmd_line: str):
        """Split command into Verb, Process, Tag, Value."""
        try:
            tokens = shlex.split(cmd_line.lower())
        except ValueError:
            return None
        
        if not tokens:
            return None
            
        verb = tokens[0]
        if verb not in MSLParser.VALID_VERBS:
            raise ValueError(f"Unknown verb: {verb}")
            
        return tokens
