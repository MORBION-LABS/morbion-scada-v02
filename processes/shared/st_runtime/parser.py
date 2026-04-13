"""
parser.py — IEC 61131-3 Structured Text Parser
MORBION SCADA v02 — CORRECTED

Recursive descent parser. Converts token stream into AST.

Changes from broken version:
  - VAR...END_VAR blocks now parsed and stored as instance declarations
  - Function block calls support named parameters: TON_1(IN := x, PT := 10.0)
  - Dot notation in expressions: timer.Q, counter.CV
  - FB instance names tracked so interpreter can key instances correctly
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Tuple, Dict
from .lexer import Token, TT, Lexer, LexerError


# ── AST Nodes ──────────────────────────────────────────────────────────────────

@dataclass
class Program:
    statements:   List[Any]
    fb_instances: Dict[str, str]   # instance_name → type_name (e.g. "DRY_RUN_TIMER" → "TON")

@dataclass
class Assign:
    target: Any
    value:  Any

@dataclass
class VarRef:
    name: str

@dataclass
class DotAccess:
    obj:   str    # instance name, e.g. "DRY_RUN_TIMER"
    field: str    # field name,    e.g. "Q"

@dataclass
class BinOp:
    op:    str
    left:  Any
    right: Any

@dataclass
class UnaryOp:
    op:      str
    operand: Any

@dataclass
class Literal:
    value: Any

@dataclass
class IfStmt:
    condition:  Any
    then_body:  List[Any]
    elsif_list: List[Tuple[Any, List[Any]]]
    else_body:  List[Any]

@dataclass
class WhileStmt:
    condition: Any
    body:      List[Any]

@dataclass
class ForStmt:
    var:   str
    start: Any
    stop:  Any
    step:  Any
    body:  List[Any]

@dataclass
class ReturnStmt:
    pass

@dataclass
class FBCall:
    """
    Function block instance call.
    instance_name: the declared variable name, e.g. DRY_RUN_TIMER
    named_args:    dict of param_name → value_node
    positional_args: list of value_nodes (if no named params used)
    """
    instance_name:   str
    named_args:      Dict[str, Any]
    positional_args: List[Any]

@dataclass
class FunctionCall:
    """
    Stateless standard library function call.
    e.g. LIMIT(0.0, x, 100.0), ABS(error), SQRT(x)
    Always positional. Never stateful.
    """
    name: str
    args: List[Any]


# ── Parser ─────────────────────────────────────────────────────────────────────

class ParseError(Exception):
    pass

# Standard library functions — stateless, no instance needed
STDLIB_NAMES = {
    'LIMIT', 'ABS', 'MAX', 'MIN', 'SQRT', 'INT', 'REAL', 'BOOL'
}

# Function block types — stateful, require declared instance
FB_TYPE_NAMES = {
    'TON', 'TOF', 'CTU', 'SR', 'RS'
}


class Parser:

    def __init__(self, tokens: List[Token]):
        self._tokens      = tokens
        self._pos         = 0
        self._fb_instances: Dict[str, str] = {}   # name → type

    @property
    def _cur(self) -> Token:
        return self._tokens[self._pos]

    def _eat(self, tt: TT) -> Token:
        if self._cur.type != tt:
            raise ParseError(
                f"Line {self._cur.line}: expected {tt.name}, "
                f"got {self._cur.type.name} ({self._cur.value!r})")
        tok = self._cur
        self._pos += 1
        return tok

    def _match(self, *types: TT) -> bool:
        return self._cur.type in types

    # ── Top level ──────────────────────────────────────────────────────────────

    def parse(self) -> Program:
        stmts = self._parse_statement_list()
        self._eat(TT.EOF)
        return Program(stmts, dict(self._fb_instances))

    def _parse_statement_list(self) -> List[Any]:
        stop = {TT.EOF, TT.ELSE, TT.ELSIF, TT.END_IF,
                TT.END_WHILE, TT.END_FOR}
        stmts = []
        while self._cur.type not in stop:
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _parse_statement(self) -> Any:
        tt = self._cur.type

        if tt == TT.IF:
            return self._parse_if()
        if tt == TT.WHILE:
            return self._parse_while()
        if tt == TT.FOR:
            return self._parse_for()
        if tt == TT.RETURN:
            self._eat(TT.RETURN)
            self._eat(TT.SEMICOLON)
            return ReturnStmt()
        if tt == TT.VAR:
            self._parse_var_block()
            return None
        if tt == TT.IDENT:
            return self._parse_ident_statement()

        raise ParseError(
            f"Line {self._cur.line}: unexpected token "
            f"{tt.name} ({self._cur.value!r})")

    # ── VAR block ──────────────────────────────────────────────────────────────

    def _parse_var_block(self):
        """
        Parse VAR...END_VAR block.
        Extracts FB instance declarations.
        Example:
            VAR
                dry_run_timer : TON;
                counter       : CTU;
                x             : REAL;
            END_VAR
        """
        self._eat(TT.VAR)
        while self._cur.type not in (TT.END_VAR, TT.EOF):
            if self._cur.type == TT.IDENT:
                var_name = self._eat(TT.IDENT).value.upper()
                self._eat(TT.COLON)
                type_name = self._eat(TT.IDENT).value.upper()
                self._eat(TT.SEMICOLON)
                # Track FB instance declarations
                if type_name in FB_TYPE_NAMES:
                    self._fb_instances[var_name] = type_name
            else:
                self._pos += 1   # skip anything unexpected
        self._eat(TT.END_VAR)

    # ── Identifier statements ──────────────────────────────────────────────────

    def _parse_ident_statement(self) -> Any:
        """
        Handles three cases:
          1. FB instance call:    dry_run_timer(IN := x, PT := 10.0);
          2. Simple assignment:   fault_code := 4;
          3. Dot assignment:      timer.field := value;  (rare but valid)
        """
        name = self._eat(TT.IDENT).value.upper()

        # FB instance call — instance name known from VAR block
        if self._cur.type == TT.LPAREN and name in self._fb_instances:
            call = self._parse_fb_call(name)
            self._eat(TT.SEMICOLON)
            return call

        # Stdlib function call as statement (result discarded)
        if self._cur.type == TT.LPAREN and name in STDLIB_NAMES:
            args = self._parse_positional_args()
            self._eat(TT.SEMICOLON)
            return FunctionCall(name, args)

        # Dot assignment: NAME.field :=
        if self._cur.type == TT.DOT:
            self._eat(TT.DOT)
            field  = self._eat(TT.IDENT).value.upper()
            target = DotAccess(name, field)
            self._eat(TT.ASSIGN)
            value  = self._parse_expr()
            self._eat(TT.SEMICOLON)
            return Assign(target, value)

        # Simple assignment: NAME :=
        self._eat(TT.ASSIGN)
        value = self._parse_expr()
        self._eat(TT.SEMICOLON)
        return Assign(VarRef(name), value)

    def _parse_fb_call(self, instance_name: str) -> FBCall:
        """
        Parse FB call with named or positional parameters.
        Named:      instance(IN := expr, PT := expr)
        Positional: instance(expr, expr)
        Mixed not supported — must be all named or all positional.
        """
        self._eat(TT.LPAREN)
        named_args      = {}
        positional_args = []

        if self._cur.type != TT.RPAREN:
            # Peek: if next two tokens are IDENT ASSIGN it's named params
            if (self._cur.type == TT.IDENT and
                    self._pos + 1 < len(self._tokens) and
                    self._tokens[self._pos + 1].type == TT.ASSIGN):
                # Named parameters
                while self._cur.type != TT.RPAREN:
                    param = self._eat(TT.IDENT).value.upper()
                    self._eat(TT.ASSIGN)
                    val = self._parse_expr()
                    named_args[param] = val
                    if self._cur.type == TT.COMMA:
                        self._eat(TT.COMMA)
            else:
                # Positional parameters
                while self._cur.type != TT.RPAREN:
                    positional_args.append(self._parse_expr())
                    if self._cur.type == TT.COMMA:
                        self._eat(TT.COMMA)

        self._eat(TT.RPAREN)
        return FBCall(instance_name, named_args, positional_args)

    def _parse_positional_args(self) -> List[Any]:
        self._eat(TT.LPAREN)
        args = []
        while self._cur.type != TT.RPAREN:
            args.append(self._parse_expr())
            if self._cur.type == TT.COMMA:
                self._eat(TT.COMMA)
        self._eat(TT.RPAREN)
        return args

    # ── Control flow ───────────────────────────────────────────────────────────

    def _parse_if(self) -> IfStmt:
        self._eat(TT.IF)
        cond = self._parse_expr()
        self._eat(TT.THEN)
        then_body = self._parse_statement_list()

        elsif_list = []
        while self._cur.type == TT.ELSIF:
            self._eat(TT.ELSIF)
            ec = self._parse_expr()
            self._eat(TT.THEN)
            eb = self._parse_statement_list()
            elsif_list.append((ec, eb))

        else_body = []
        if self._cur.type == TT.ELSE:
            self._eat(TT.ELSE)
            else_body = self._parse_statement_list()

        self._eat(TT.END_IF)
        self._eat(TT.SEMICOLON)
        return IfStmt(cond, then_body, elsif_list, else_body)

    def _parse_while(self) -> WhileStmt:
        self._eat(TT.WHILE)
        cond = self._parse_expr()
        self._eat(TT.DO)
        body = self._parse_statement_list()
        self._eat(TT.END_WHILE)
        self._eat(TT.SEMICOLON)
        return WhileStmt(cond, body)

    def _parse_for(self) -> ForStmt:
        self._eat(TT.FOR)
        var = self._eat(TT.IDENT).value.upper()
        self._eat(TT.ASSIGN)
        start = self._parse_expr()
        self._eat(TT.TO)
        stop  = self._parse_expr()
        step  = Literal(1)
        if self._cur.type == TT.BY:
            self._eat(TT.BY)
            step = self._parse_expr()
        self._eat(TT.DO)
        body = self._parse_statement_list()
        self._eat(TT.END_FOR)
        self._eat(TT.SEMICOLON)
        return ForStmt(var, start, stop, step, body)

    # ── Expressions ────────────────────────────────────────────────────────────

    def _parse_expr(self) -> Any:
        return self._parse_or()

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while self._cur.type in (TT.OR, TT.XOR):
            op = self._cur.value
            self._pos += 1
            left = BinOp(op, left, self._parse_and())
        return left

    def _parse_and(self) -> Any:
        left = self._parse_not()
        while self._cur.type == TT.AND:
            self._pos += 1
            left = BinOp('AND', left, self._parse_not())
        return left

    def _parse_not(self) -> Any:
        if self._cur.type == TT.NOT:
            self._pos += 1
            return UnaryOp('NOT', self._parse_not())
        return self._parse_compare()

    def _parse_compare(self) -> Any:
        left = self._parse_add()
        ops  = {
            TT.EQ: '=', TT.NEQ: '<>',
            TT.LT: '<', TT.GT:  '>',
            TT.LTE: '<=', TT.GTE: '>=',
        }
        while self._cur.type in ops:
            op = ops[self._cur.type]
            self._pos += 1
            left = BinOp(op, left, self._parse_add())
        return left

    def _parse_add(self) -> Any:
        left = self._parse_mul()
        while self._cur.type in (TT.PLUS, TT.MINUS):
            op = self._cur.value
            self._pos += 1
            left = BinOp(op, left, self._parse_mul())
        return left

    def _parse_mul(self) -> Any:
        left = self._parse_unary()
        while self._cur.type in (TT.STAR, TT.SLASH):
            op = self._cur.value
            self._pos += 1
            left = BinOp(op, left, self._parse_unary())
        return left

    def _parse_unary(self) -> Any:
        if self._cur.type == TT.MINUS:
            self._pos += 1
            return UnaryOp('-', self._parse_primary())
        return self._parse_primary()

    def _parse_primary(self) -> Any:
        tt = self._cur.type

        if tt == TT.NUMBER:
            v = self._cur.value
            self._pos += 1
            return Literal(float(v) if '.' in v else int(v))

        if tt == TT.BOOL_LIT:
            v = self._cur.value == 'TRUE'
            self._pos += 1
            return Literal(v)

        if tt == TT.STRING:
            v = self._cur.value
            self._pos += 1
            return Literal(v)

        if tt == TT.IDENT:
            name = self._cur.value.upper()
            self._pos += 1

            # Dot access in expression: instance.Q, timer.ET etc
            if self._cur.type == TT.DOT:
                self._eat(TT.DOT)
                field = self._eat(TT.IDENT).value.upper()
                return DotAccess(name, field)

            # Inline FB call in expression (instance known)
            if self._cur.type == TT.LPAREN and name in self._fb_instances:
                call = self._parse_fb_call(name)
                return call

            # Stdlib function in expression
            if self._cur.type == TT.LPAREN and name in STDLIB_NAMES:
                args = self._parse_positional_args()
                return FunctionCall(name, args)

            return VarRef(name)

        if tt == TT.LPAREN:
            self._eat(TT.LPAREN)
            expr = self._parse_expr()
            self._eat(TT.RPAREN)
            return expr

        raise ParseError(
            f"Line {self._cur.line}: unexpected token in expression: "
            f"{tt.name} ({self._cur.value!r})")


# ── Public entry point ─────────────────────────────────────────────────────────

def parse_st(source: str) -> Program:
    """
    Parse ST source string into AST.
    Raises LexerError on tokenization failure.
    Raises ParseError on syntax errors.
    """
    lexer  = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()
