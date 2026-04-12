"""
parser.py — IEC 61131-3 Structured Text Parser
MORBION SCADA v02

Recursive descent parser. Converts token stream into AST.
Handles: assignments, if/elsif/else, while, for, function calls,
         dot access (FB.field), all arithmetic and boolean operators.
Operator precedence (low to high):
    OR, XOR → AND → NOT → comparison → add/sub → mul/div → unary → primary
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Tuple
from .lexer import Token, TT, Lexer, LexerError


# ── AST Node Definitions ──────────────────────────────────────────────────────

@dataclass
class Program:
    statements: List[Any]

@dataclass
class Assign:
    target: Any       # VarRef or DotAccess
    value:  Any

@dataclass
class VarRef:
    name: str

@dataclass
class DotAccess:
    obj:   str
    field: str

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
    value: Any        # int, float, bool, str

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
class FunctionCall:
    name: str
    args: List[Any]


# ── Parser ────────────────────────────────────────────────────────────────────

class ParseError(Exception):
    pass


class Parser:
    """
    Recursive descent parser for our ST subset.
    One instance per parse. Not reusable.
    """

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos    = 0

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

    # ── Top level ─────────────────────────────────────────────────────────────

    def parse(self) -> Program:
        stmts = self._parse_statement_list()
        self._eat(TT.EOF)
        return Program(stmts)

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
            self._parse_var_decl()
            return None
        if tt == TT.IDENT:
            return self._parse_assign_or_call()

        raise ParseError(
            f"Line {self._cur.line}: unexpected token "
            f"{tt.name} ({self._cur.value!r})")

    # ── Control flow ──────────────────────────────────────────────────────────

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
        var = self._eat(TT.IDENT).value
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

    def _parse_var_decl(self):
        """Skip VAR...END_VAR blocks — declarations only, no execution."""
        self._eat(TT.VAR)
        while self._cur.type not in (TT.END_VAR, TT.EOF):
            self._pos += 1
        self._eat(TT.END_VAR)

    # ── Assignment and calls ──────────────────────────────────────────────────

    def _parse_assign_or_call(self) -> Any:
        name = self._eat(TT.IDENT).value

        # Function call statement: NAME(...)
        if self._cur.type == TT.LPAREN:
            call = self._parse_call_args(name)
            self._eat(TT.SEMICOLON)
            return call

        # Dot access assignment: NAME.field :=
        if self._cur.type == TT.DOT:
            self._eat(TT.DOT)
            field  = self._eat(TT.IDENT).value
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

    def _parse_call_args(self, name: str) -> FunctionCall:
        self._eat(TT.LPAREN)
        args = []
        while self._cur.type != TT.RPAREN:
            args.append(self._parse_expr())
            if self._cur.type == TT.COMMA:
                self._eat(TT.COMMA)
        self._eat(TT.RPAREN)
        return FunctionCall(name, args)

    # ── Expression parsing — precedence climbing ──────────────────────────────

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
            TT.EQ:  '=',
            TT.NEQ: '<>',
            TT.LT:  '<',
            TT.GT:  '>',
            TT.LTE: '<=',
            TT.GTE: '>=',
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
            name = self._cur.value
            self._pos += 1

            # Inline function call as expression: NAME(...)
            if self._cur.type == TT.LPAREN:
                return self._parse_call_args(name)

            # Dot access as expression: NAME.field
            if self._cur.type == TT.DOT:
                self._eat(TT.DOT)
                field = self._eat(TT.IDENT).value
                return DotAccess(name, field)

            return VarRef(name)

        if tt == TT.LPAREN:
            self._eat(TT.LPAREN)
            expr = self._parse_expr()
            self._eat(TT.RPAREN)
            return expr

        raise ParseError(
            f"Line {self._cur.line}: unexpected token in expression: "
            f"{tt.name} ({self._cur.value!r})")


# ── Public entry point ────────────────────────────────────────────────────────

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