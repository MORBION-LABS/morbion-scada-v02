"""
interpreter.py — IEC 61131-3 ST Interpreter
MORBION SCADA v02

Executes a compiled ST AST against a variable environment.
One Interpreter instance per PLC — persists function block state
across scan cycles. Variables are plain Python dicts (uppercase keys).

Execution model:
    variables = read_from_process_state()
    result    = interpreter.execute(variables, dt)
    write_to_process_state(result)

Safety limits:
    WHILE and FOR loops are guarded against infinite iteration.
    All runtime errors are caught and logged — never crash the scan loop.
"""

import logging
from typing import Any, Dict, Optional
from .parser import (
    Program, Assign, VarRef, DotAccess, BinOp, UnaryOp,
    Literal, IfStmt, WhileStmt, ForStmt, ReturnStmt,
    FunctionCall, parse_st
)
from .stdlib import STDLIB_FUNCTIONS, FB_CLASSES

log = logging.getLogger("st_interpreter")

MAX_LOOP_ITERATIONS = 10000   # hard guard against runaway loops


class _ReturnSignal(Exception):
    """Internal signal — not an error. Implements RETURN statement."""
    pass


class STRuntimeError(Exception):
    """Raised on ST execution errors that the caller should know about."""
    pass


class Interpreter:
    """
    Executes a compiled ST Program.

    fb_state: dict of function block instances, keyed by uppercase name.
              Persists across scan cycles so TON timers accumulate correctly.
    _dt:      current scan interval in seconds, set at start of each execute().
    _vars:    working copy of variables for the current scan.
    """

    def __init__(self, program: Program):
        self._program  = program
        self._fb_state: Dict[str, Any] = {}
        self._dt:       float = 0.1
        self._vars:     Dict[str, Any] = {}

    def execute(self, variables: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """
        Execute one PLC scan cycle.

        Args:
            variables: dict of ST_VAR_NAME (uppercase) → current value
                       read from ProcessState before calling.
            dt:        scan interval in seconds.

        Returns:
            Modified variables dict. Caller writes outputs back to
            ProcessState after this returns.

        Never raises. All errors are logged.
        """
        self._dt   = dt
        self._vars = dict(variables)   # work on a copy

        try:
            self._run_stmts(self._program.statements)
        except _ReturnSignal:
            pass   # clean RETURN from top-level — fine
        except STRuntimeError as e:
            log.error("ST runtime error: %s", e)
        except ZeroDivisionError:
            log.error("ST runtime: division by zero")
        except Exception as e:
            log.error("ST unexpected error: %s", e, exc_info=True)

        return self._vars

    # ── Statement execution ───────────────────────────────────────────────────

    def _run_stmts(self, stmts):
        for stmt in stmts:
            self._run_stmt(stmt)

    def _run_stmt(self, stmt):
        if isinstance(stmt, Assign):
            val = self._eval(stmt.value)
            self._set_var(stmt.target, val)

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
            self._vars[stmt.var.upper()] = start
            count = 0
            while True:
                cv = self._vars[stmt.var.upper()]
                if step > 0 and cv > stop:
                    break
                if step < 0 and cv < stop:
                    break
                self._run_stmts(stmt.body)
                self._vars[stmt.var.upper()] += step
                count += 1
                if count > MAX_LOOP_ITERATIONS:
                    raise STRuntimeError(
                        "FOR loop exceeded max iterations")

        elif isinstance(stmt, ReturnStmt):
            raise _ReturnSignal()

        elif isinstance(stmt, FunctionCall):
            # Statement-level call — result discarded
            self._call_function(stmt.name, stmt.args)

        # None statements (from VAR declarations) are silently skipped

    # ── Expression evaluation ─────────────────────────────────────────────────

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
            # FB instance field access: e.g. DRY_RUN_TIMER.Q
            key = f"{node.obj.upper()}.{node.field.upper()}"
            # Check if it's a FB instance field
            fb_name = node.obj.upper()
            if fb_name in self._fb_state:
                fb = self._fb_state[fb_name]
                field = node.field.upper()
                # Map common FB fields
                field_map = {
                    'Q': 'Q', 'Q1': 'Q1', 'ET': 'ET',
                    'CV': 'CV', 'IN': 'IN'
                }
                attr = field_map.get(field, field.lower())
                if hasattr(fb, attr):
                    return getattr(fb, attr)
            return self._vars.get(key, 0)

        if isinstance(node, BinOp):
            L = self._eval(node.left)
            R = self._eval(node.right)
            op = node.op
            if op == '+':    return L + R
            if op == '-':    return L - R
            if op == '*':    return L * R
            if op == '/':
                if R == 0:
                    log.warning("ST: division by zero — returning 0")
                    return 0
                return L / R
            if op == '=':    return L == R
            if op == '<>':   return L != R
            if op == '<':    return L < R
            if op == '>':    return L > R
            if op == '<=':   return L <= R
            if op == '>=':   return L >= R
            if op == 'AND':  return bool(L) and bool(R)
            if op == 'OR':   return bool(L) or bool(R)
            if op == 'XOR':  return bool(L) ^ bool(R)
            raise STRuntimeError(f"Unknown binary operator: {op}")

        if isinstance(node, UnaryOp):
            v = self._eval(node.operand)
            if node.op == '-':   return -v
            if node.op == 'NOT': return not bool(v)
            raise STRuntimeError(f"Unknown unary operator: {node.op}")

        if isinstance(node, FunctionCall):
            return self._call_function(node.name, node.args)

        raise STRuntimeError(f"Cannot evaluate node type: {type(node).__name__}")

    # ── Variable assignment ───────────────────────────────────────────────────

    def _set_var(self, target, value):
        if isinstance(target, VarRef):
            self._vars[target.name.upper()] = value
        elif isinstance(target, DotAccess):
            key = f"{target.obj.upper()}.{target.field.upper()}"
            self._vars[key] = value

    # ── Function and FB calls ─────────────────────────────────────────────────

    def _call_function(self, name: str, args: list) -> Any:
        uname = name.upper()

        # Stateless standard library functions
        if uname in STDLIB_FUNCTIONS:
            evaluated = [self._eval(a) for a in args]
            try:
                return STDLIB_FUNCTIONS[uname](*evaluated)
            except Exception as e:
                log.error("ST stdlib %s error: %s", uname, e)
                return 0

        # Stateful function blocks — instance persists across scans
        if uname in FB_CLASSES:
            if uname not in self._fb_state:
                self._fb_state[uname] = FB_CLASSES[uname]()
            fb = self._fb_state[uname]
            evaluated = [self._eval(a) for a in args]
            # Timer blocks need dt injected as last argument
            if uname in ('TON', 'TOF'):
                evaluated.append(self._dt)
            try:
                result = fb(*evaluated)
                return result
            except Exception as e:
                log.error("ST FB %s error: %s", uname, e)
                return 0

        log.warning("ST: unknown function '%s' — returning 0", name)
        return 0