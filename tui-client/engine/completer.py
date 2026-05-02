"""
completer.py — Tab-Completion Engine
MORBION SCADA v02 — REBOOT
"""
from prompt_toolkit.completion import Completer, Completion
from .msl_executor import MSLExecutor

class MSLCompleter(Completer):
    def __init__(self):
        self.verbs = ["read", "write", "inject", "watch", "unwatch", "mode", "plc", "clear"]
        self.procs = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]
        self.tags = MSLExecutor.TAG_MAP

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        tokens = text.split()
        
        if not tokens or (len(tokens) == 1 and not text.endswith(" ")):
            # Completing Verb
            word = tokens[0] if tokens else ""
            for v in self.verbs:
                if v.startswith(word):
                    yield Completion(v, start_position=-len(word))
        
        elif len(tokens) == 1 or (len(tokens) == 2 and not text.endswith(" ")):
            # Completing Process
            word = tokens[1] if len(tokens) > 1 else ""
            for p in self.procs:
                if p.startswith(word):
                    yield Completion(p, start_position=-len(word))

        elif len(tokens) == 2 or (len(tokens) == 3 and not text.endswith(" ")):
            # Completing Tag
            proc = tokens[1]
            word = tokens[2] if len(tokens) > 2 else ""
            if proc in self.tags:
                for t in self.tags[proc]:
                    if t.startswith(word):
                        yield Completion(t, start_position=-len(word))
