"""
lexer.py — IEC 61131-3 Structured Text Tokenizer
MORBION SCADA v02

Converts raw ST source text into a token stream for the parser.
Handles: keywords, identifiers, literals, operators, comments.
Block comments (* ... *) and line comments // both supported.
Case-insensitive — all identifiers uppercased on output.
"""

import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import List


class TT(Enum):
    """Token Types — every valid token in our ST subset."""
    # Literals
    NUMBER    = auto()
    STRING    = auto()
    BOOL_LIT  = auto()    # TRUE / FALSE

    # Identifiers and keywords
    IDENT     = auto()
    IF        = auto()
    THEN      = auto()
    ELSIF     = auto()
    ELSE      = auto()
    END_IF    = auto()
    WHILE     = auto()
    DO        = auto()
    END_WHILE = auto()
    FOR       = auto()
    TO        = auto()
    BY        = auto()
    END_FOR   = auto()
    RETURN    = auto()
    AND       = auto()
    OR        = auto()
    NOT       = auto()
    XOR       = auto()
    VAR       = auto()
    END_VAR   = auto()

    # Operators
    ASSIGN    = auto()    # :=
    EQ        = auto()    # =
    NEQ       = auto()    # <>
    LT        = auto()    # 
    GT        = auto()    # >
    LTE       = auto()    # <=
    GTE       = auto()    # >=
    PLUS      = auto()
    MINUS     = auto()
    STAR      = auto()
    SLASH     = auto()
    LPAREN    = auto()
    RPAREN    = auto()
    DOT       = auto()
    COMMA     = auto()
    SEMICOLON = auto()
    COLON     = auto()

    # Special
    EOF       = auto()


@dataclass
class Token:
    type:  TT
    value: str
    line:  int


KEYWORDS = {
    'IF':        TT.IF,
    'THEN':      TT.THEN,
    'ELSIF':     TT.ELSIF,
    'ELSE':      TT.ELSE,
    'END_IF':    TT.END_IF,
    'WHILE':     TT.WHILE,
    'DO':        TT.DO,
    'END_WHILE': TT.END_WHILE,
    'FOR':       TT.FOR,
    'TO':        TT.TO,
    'BY':        TT.BY,
    'END_FOR':   TT.END_FOR,
    'RETURN':    TT.RETURN,
    'AND':       TT.AND,
    'OR':        TT.OR,
    'NOT':       TT.NOT,
    'XOR':       TT.XOR,
    'TRUE':      TT.BOOL_LIT,
    'FALSE':     TT.BOOL_LIT,
    'VAR':       TT.VAR,
    'END_VAR':   TT.END_VAR,
}


class LexerError(Exception):
    pass


class Lexer:
    """
    Tokenizes IEC 61131-3 Structured Text source.
    One instance per parse. Not reusable.
    """

    def __init__(self, source: str):
        self._src    = source
        self._pos    = 0
        self._line   = 1
        self._tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        """
        Convert source to token list.
        Always terminates with EOF token.
        Raises LexerError on unrecognized characters.
        """
        while self._pos < len(self._src):
            self._skip_whitespace_and_comments()
            if self._pos >= len(self._src):
                break
            tok = self._next_token()
            if tok:
                self._tokens.append(tok)
        self._tokens.append(Token(TT.EOF, '', self._line))
        return self._tokens

    # ── Internal ──────────────────────────────────────────────────────────────

    def _skip_whitespace_and_comments(self):
        while self._pos < len(self._src):
            ch = self._src[self._pos]

            if ch in ' \t\r':
                self._pos += 1

            elif ch == '\n':
                self._pos += 1
                self._line += 1

            elif self._src[self._pos:self._pos + 2] == '(*':
                # Block comment (* ... *)
                end = self._src.find('*)', self._pos + 2)
                if end == -1:
                    raise LexerError(
                        f"Unclosed block comment at line {self._line}")
                self._line += self._src[self._pos:end + 2].count('\n')
                self._pos = end + 2

            elif self._src[self._pos:self._pos + 2] == '//':
                # Line comment
                end = self._src.find('\n', self._pos)
                if end == -1:
                    self._pos = len(self._src)
                else:
                    self._pos = end + 1
                    self._line += 1
            else:
                break

    def _next_token(self) -> Token:
        ch   = self._src[self._pos]
        line = self._line

        # Number literal
        if ch.isdigit() or (
            ch == '.' and
            self._pos + 1 < len(self._src) and
            self._src[self._pos + 1].isdigit()
        ):
            return self._read_number(line)

        # String literal
        if ch == "'":
            return self._read_string(line)

        # Identifier or keyword
        if ch.isalpha() or ch == '_':
            return self._read_ident(line)

        # Two-character operators — must check before single-char
        two = self._src[self._pos:self._pos + 2]
        if two == ':=':
            self._pos += 2
            return Token(TT.ASSIGN, ':=', line)
        if two == '<>':
            self._pos += 2
            return Token(TT.NEQ, '<>', line)
        if two == '<=':
            self._pos += 2
            return Token(TT.LTE, '<=', line)
        if two == '>=':
            self._pos += 2
            return Token(TT.GTE, '>=', line)

        # Single-character operators
        single = {
            '=': TT.EQ,
            '<': TT.LT,
            '>': TT.GT,
            '+': TT.PLUS,
            '-': TT.MINUS,
            '*': TT.STAR,
            '/': TT.SLASH,
            '(': TT.LPAREN,
            ')': TT.RPAREN,
            '.': TT.DOT,
            ',': TT.COMMA,
            ';': TT.SEMICOLON,
            ':': TT.COLON,
        }
        if ch in single:
            self._pos += 1
            return Token(single[ch], ch, line)

        raise LexerError(
            f"Unexpected character '{ch}' (ord {ord(ch)}) at line {line}")

    def _read_number(self, line: int) -> Token:
        start = self._pos
        has_dot = False
        while self._pos < len(self._src):
            c = self._src[self._pos]
            if c.isdigit():
                self._pos += 1
            elif c == '.' and not has_dot:
                has_dot = True
                self._pos += 1
            else:
                break
        return Token(TT.NUMBER, self._src[start:self._pos], line)

    def _read_string(self, line: int) -> Token:
        self._pos += 1   # skip opening '
        start = self._pos
        while self._pos < len(self._src) and self._src[self._pos] != "'":
            if self._src[self._pos] == '\n':
                self._line += 1
            self._pos += 1
        if self._pos >= len(self._src):
            raise LexerError(f"Unclosed string literal at line {line}")
        val = self._src[start:self._pos]
        self._pos += 1   # skip closing '
        return Token(TT.STRING, val, line)

    def _read_ident(self, line: int) -> Token:
        start = self._pos
        while self._pos < len(self._src) and (
            self._src[self._pos].isalnum() or self._src[self._pos] == '_'
        ):
            self._pos += 1
        name = self._src[start:self._pos].upper()
        tt   = KEYWORDS.get(name, TT.IDENT)
        return Token(tt, name, line)