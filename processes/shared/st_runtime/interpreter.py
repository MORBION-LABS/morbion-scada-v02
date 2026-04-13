"""
interpreter.py — IEC 61131-3 ST Interpreter
MORBION SCADA v02 — CORRECTED

Key fixes from broken version:
  1. FB instances keyed by INSTANCE NAME not class name
     e.g. "DRY_RUN_TIMER" → TON instance
     This means two TON instances (dry_run_timer, startup_timer)
     are separate objects that accumulate independently.

  2. FBCall node handled separately from FunctionCall node
     FBCall → stateful instance, named or positional params
     FunctionCall → stateless stdlib, positional only

  3. DotAccess correctly resolves FB instance fields
     dry_run_timer.Q → looks up instance "DRY_RUN_TIMER", returns .Q

  4. dt injected by runtime infrastructure
     Interpreter._dt set at top of execute(), not smuggled through args

  5. Named parameter dispatch for FB calls
     TON_1(IN := x, PT := 10.0) → fb(IN=x, PT=10.0)
     Each FB class knows its parameter order for positional fallback

  6. Input/output image separation enforced by caller (main.py + plc_runtime.py)
     Interpreter only sees variables dict — does not touch ProcessState directly
"""

import logging
from typing import Any, Dict, Optional
from .parser import (
    Program, Assign, VarRef, DotAccess, BinOp, UnaryOp,
    Literal, IfStmt, WhileStmt, ForStmt, ReturnStmt,
    FBCall, FunctionCall, parse_st, FB_TYPE_NAMES
)
from .stdlib import STDLIB_FUNCTIONS, TON, TOF, CTU, SR, RS

log = logging.getLogger("st_interpreter")

MAX_LOOP_ITERATIONS = 10000

# Maps FB type name → class
FB_CLASSES = {
    'TON': TON,
    'TOF': TOF,
    'CTU': CTU,
    'SR':  SR,
    'RS':  RS,
}

# Named parameter order for each FB type
# Used when call is positional — maps position to param name
FB_PARAM_ORDER = {
    'TON': ['IN', 'PT'],
    'TOF': ['IN', 'PT'],
    'CTU': ['CU', 'R', 'PV'],
    'SR':  ['S1', 'R'],
    'RS':  ['S', 'R1'],
}


class _ReturnSignal(Exception):
    pass


class STRuntimeError(Exception):
    pass


class Interpreter:
    """
    Executes a compiled ST Program.

    _fb_instances: dict of instance_name → FB object
                   Keyed by the VAR-declared name, not the type.
                   Persists across scan cycles — timers accumulate correctly.

    _fb_types:     dict of instance_name → type_name
                   Copied from Program.fb_instances at construction.
                   Used to know which class to instantiate on first call.

    _dt:           Current scan interval. Set at top of execute().
                   Injected into timer FB calls by the runtime.
                   Never passed through ST argument lists.
    """

    def __init__(self, program: Program):
        self._program     = program
        self._fb_instances: Dict[str, Any] = {}
        self._fb_types:     Dict[str, str] = dict(program.fb_instances)
        self._dt:           float = 0.1
        self._vars:         Dict[str, Any] = {}

        # Pre-instantiate all declared FB instances
        for inst_name, type_name in self._fb_types.items():
            cls = FB_CLASSES.get(type_name)
            if cls is not None:
                self._fb_instances[inst_name] = cls()
                log.debug("FB instance created: %s (%s)", inst_name, type_name)
            else:
                log.warning("Unknown FB type in VAR block: %s", type_name)

    def execute(self, variables: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """
        Execute one PLC scan cycle.

        Args:
            variables: uppercase ST variable names → current values
                       Built from ProcessState input image by plc_runtime.
            dt:        Scan interval in seconds. Injected into timer FBs.

        Returns:
            Modified variables dict — the output image.
            plc_runtime writes outputs back to ProcessState after this returns.

        Never raises. All errors caught and logged.
        """
        self._dt   = dt
        self._vars = dict(variables)

        try:
            self._run_stmts(self._program.statements)
        except _ReturnSignal:
            pass
        except STRuntimeError as e:
            log.error("ST runtime error: %s", e)
        except ZeroDivisionError:
            log.error("ST runtime: division by zero")
        except Exception as e:
            log.error("ST unexpected error: %s", e, exc_info=True)

        return self._vars

    # ── Statement execution ────────────────────────────────────────────────────

    def _run_stmts(self, stmts):
        for stmt in stmts:
            self._run_stmt(stmt)

    def _run_stmt(self, stmt):
        if isinstance(stmt, Assign):
            val = self._eval(stmt.value)
            self._set_var(stmt.target, val)

        elif isinstance(stmt, FBCall):
            # Statement-level FB call — result (Q) discarded
            # FB state updated internally, accessible via dot notation
            self._call_fb(stmt)

        elif isinstance(stmt, FunctionCall):
            # Statement-level stdlib call — result discarded
            self._call_stdlib(stmt.name, stmt.args)

        elif isinstance(stmt, IfStmt):
            if self._eval(stmt.condition):
                self._run_stmts(stmt.then_body)
            else:
                executed = False
                for ec, eb in stmt.elsif_list:
                    if self._eval(ec):
                        self._run_stmts(eb)
                        executed = True
                        break
                if not executed and stmt.else_body:
                    self._run_stmts(stmt.else_body)

        elif isinstance(stmt, WhileStmt):
            count = 0
            while self._eval(stmt.condition):
                self._run_stmts(stmt.body)
                count += 1
                if count > MAX_LOOP_ITERATIONS:
                    raise STRuntimeError(
                        "WHILE loop exceeded max iterations — "
                        "possible infinite loop in ST program")

        elif isinstance(stmt, ForStmt):
            start = self._eval(stmt.start)
            stop  = self._eval(stmt.stop)
            step  = self._eval(stmt.step)
            if step == 0:
                raise STRuntimeError("FOR loop step cannot be zero")
            self._vars[stmt.var] = start
            count = 0
            while True:
                cv = self._vars[stmt.var]
                if step > 0 and cv > stop:
                    break
                if step < 0 and cv < stop:
                    break
                self._run_stmts(stmt.body)
                self._vars[stmt.var] += step
                count += 1
                if count > MAX_LOOP_ITERATIONS:
                    raise STRuntimeError("FOR loop exceeded max iterations")

        elif isinstance(stmt, ReturnStmt):
            raise _ReturnSignal()

        # None (from VAR blocks) silently skipped

    # ── Expression evaluation ──────────────────────────────────────────────────

    def _eval(self, node) -> Any:
        if isinstance(node, Literal):
            return node.value

        if isinstance(node, VarRef):
            name = node.name.upper()
            if name == 'TRUE':
                return True
            if name == 'FALSE':
                return False
            if name not in self._vars:
                log.warning("ST: undefined variable '%s' — returning 0", name)
                return 0
            return self._vars[name]

        if isinstance(node, DotAccess):
            # FB instance field access: dry_run_timer.Q
            inst_name = node.obj.upper()
            field     = node.field.upper()
            if inst_name in self._fb_instances:
                fb = self._fb_instances[inst_name]
                # Standard FB output fields
                field_map = {
                    'Q':  'Q',   # TON, TOF, SR, RS
                    'Q1': 'Q1',  # SR, RS alternate
                    'ET': 'ET',  # TON, TOF elapsed time
                    'CV': 'CV',  # CTU current value
                    'IN': 'IN',
                    'PT': 'PT',
                }
                attr = field_map.get(field, field.lower())
                if hasattr(fb, attr):
                    return getattr(fb, attr)
                log.warning("ST: FB '%s' has no field '%s'", inst_name, field)
                return 0
            # Fall through to variable lookup
            key = f"{inst_name}.{field}"
            return self._vars.get(key, 0)

        if isinstance(node, BinOp):
            L  = self._eval(node.left)
            R  = self._eval(node.right)
            op = node.op
            if op == '+':   return L + R
            if op == '-':   return L - R
            if op == '*':   return L * R
            if op == '/':
                if R == 0:
                    log.warning("ST: division by zero — returning 0")
                    return 0
                return L / R
            if op == '=':   return L == R
            if op == '<>':  return L != R
            if op == '<':   return L < R
            if op == '>':   return L > R
            if op == '<=':  return L <= R
            if op == '>=':  return L >= R
            if op == 'AND': return bool(L) and bool(R)
            if op == 'OR':  return bool(L) or bool(R)
            if op == 'XOR': return bool(L) ^ bool(R)
            raise STRuntimeError(f"Unknown binary operator: {op}")

        if isinstance(node, UnaryOp):
            v = self._eval(node.operand)
            if node.op == '-':   return -v
            if node.op == 'NOT': return not bool(v)
            raise STRuntimeError(f"Unknown unary operator: {node.op}")

        if isinstance(node, FBCall):
            # Inline FB call used as expression — returns Q output
            return self._call_fb(node)

        if isinstance(node, FunctionCall):
            return self._call_stdlib(node.name, node.args)

        raise STRuntimeError(
            f"Cannot evaluate node type: {type(node).__name__}")

    # ── Variable assignment ────────────────────────────────────────────────────

    def _set_var(self, target, value):
        if isinstance(target, VarRef):
            self._vars[target.name.upper()] = value
        elif isinstance(target, DotAccess):
            inst_name = target.obj.upper()
            field     = target.field.upper()
            if inst_name in self._fb_instances:
                fb   = self._fb_instances[inst_name]
                attr = field.lower()
                if hasattr(fb, attr):
                    setattr(fb, attr, value)
                    return
            key = f"{inst_name}.{field}"
            self._vars[key] = value

    # ── FB call dispatch ───────────────────────────────────────────────────────

    def _call_fb(self, node: FBCall) -> Any:
        """
        Call a stateful function block instance.
        Instance is keyed by declared name — persists across scans.
        dt injected by runtime for timer blocks. Never in ST argument list.
        Returns the primary output (Q for most blocks).
        """
        inst_name = node.instance_name.upper()

        if inst_name not in self._fb_instances:
            log.warning("ST: FB instance '%s' not declared in VAR block", inst_name)
            return 0

        fb        = self._fb_instances[inst_name]
        type_name = self._fb_types.get(inst_name, '')

        # Build kwargs from named or positional args
        if node.named_args:
            kwargs = {k: self._eval(v) for k, v in node.named_args.items()}
        else:
            param_order = FB_PARAM_ORDER.get(type_name, [])
            evaluated   = [self._eval(a) for a in node.positional_args]
            kwargs      = dict(zip(param_order, evaluated))

        # Call the FB with correct signature
        try:
            if type_name in ('TON', 'TOF'):
                # Timers need dt — injected here, never from ST
                IN = kwargs.get('IN', False)
                PT = kwargs.get('PT', 0.0)
                result = fb(IN=IN, PT=PT, dt=self._dt)
            elif type_name == 'CTU':
                CU = kwargs.get('CU', False)
                R  = kwargs.get('R',  False)
                PV = kwargs.get('PV', 0)
                result = fb(CU=CU, R=R, PV=PV)
            elif type_name == 'SR':
                S1 = kwargs.get('S1', False)
                R  = kwargs.get('R',  False)
                result = fb(S1=S1, R=R)
            elif type_name == 'RS':
                S  = kwargs.get('S',  False)
                R1 = kwargs.get('R1', False)
                result = fb(S=S, R1=R1)
            else:
                result = 0
        except Exception as e:
            log.error("ST: FB '%s' call error: %s", inst_name, e)
            result = 0

        return result

    # ── Stdlib call dispatch ───────────────────────────────────────────────────

    def _call_stdlib(self, name: str, args: list) -> Any:
        """
        Call a stateless standard library function.
        Always positional. No instance. No state.
        """
        uname = name.upper()
        if uname not in STDLIB_FUNCTIONS:
            log.warning("ST: unknown function '%s' — returning 0", name)
            return 0
        evaluated = [self._eval(a) for a in args]
        try:
            return STDLIB_FUNCTIONS[uname](*evaluated)
        except Exception as e:
            log.error("ST: stdlib %s error: %s", uname, e)
            return 0
