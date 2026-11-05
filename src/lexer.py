from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List
from erros import ErroLexico
from interfaces import ILexico

class TokenType(Enum):
    IDENTIFIER     = auto()
    NUMBER         = auto()
    STRING_LITERAL = auto()
    BOOL_LITERAL   = auto()
    CLASS     = auto()
    EXTENDS   = auto()
    NEW       = auto()
    FUNC      = auto()
    VAR       = auto()
    IF        = auto()
    ELSE      = auto()
    WHILE     = auto()
    DO        = auto()
    FOR       = auto()
    IN        = auto()
    BREAK     = auto()
    CONTINUE  = auto()
    RETURN    = auto()
    SEQ       = auto()
    PAR       = auto()
    THIS      = auto()
    C_CHANNEL = auto()
    SEND      = auto()
    RECEIVE   = auto()
    INPUT     = auto()
    PRINT     = auto()
    MATRIX    = auto()
    TYPE      = auto()
    PLUS      = auto()
    MINUS     = auto()
    STAR      = auto()
    SLASH     = auto()
    MOD       = auto()
    ASSIGN    = auto()
    EQ        = auto()
    NEQ       = auto()
    NOT       = auto()
    AND       = auto()
    OR        = auto()
    LT        = auto()
    GT        = auto()
    LTE       = auto()
    GTE       = auto()
    LPAREN    = auto()
    RPAREN    = auto()
    LBRACE    = auto()
    RBRACE    = auto()
    LBRACKET  = auto()
    RBRACKET  = auto()
    DOT       = auto()
    SEMICOLON = auto()
    COMMA     = auto()
    END_OF_FILE = auto()
    UNKNOWN     = auto()

KEYWORDS: dict[str, TokenType] = {
    "class":     TokenType.CLASS,
    "extends":   TokenType.EXTENDS,
    "new":       TokenType.NEW,
    "seq":       TokenType.SEQ,
    "par":       TokenType.PAR,
    "if":        TokenType.IF,
    "else":      TokenType.ELSE,
    "while":     TokenType.WHILE,
    "do":        TokenType.DO,
    "for":       TokenType.FOR,
    "in":        TokenType.IN,
    "break":     TokenType.BREAK,
    "continue":  TokenType.CONTINUE,
    "return":    TokenType.RETURN,
    "func":      TokenType.FUNC,
    "var":       TokenType.VAR,
    "print":     TokenType.PRINT,
    "this":      TokenType.THIS,
    "c_channel": TokenType.C_CHANNEL,
    "send":      TokenType.SEND,
    "receive":   TokenType.RECEIVE,
    "input":     TokenType.INPUT,
    "matrix":    TokenType.MATRIX,
    "true":      TokenType.BOOL_LITERAL,
    "false":     TokenType.BOOL_LITERAL,
    "number":    TokenType.TYPE,
    "int":       TokenType.TYPE,
    "string":    TokenType.TYPE,
    "bool":      TokenType.TYPE,
    "void":      TokenType.TYPE,
    "list":      TokenType.TYPE,
    "dict":      TokenType.TYPE,
}

@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    col: int

class C_Lexico(ILexico):
    """Componente Analisador Lexico - implementa ILexico.

    Percorre o codigo caractere por caractere, ignorando espacos e
    comentarios (#), e agrupa os caracteres em tokens com linha e coluna.
    """

    def __init__(self, source_code: str = "") -> None:
        self._reset(source_code)

    def _reset(self, source_code: str) -> None:
        self._source = source_code
        self._pos = 0
        self._line = 1
        self._col = 1

    # ---- Interface ILexico ----
    def analisar(self, codigo_fonte: str) -> List[Token]:
        self._reset(codigo_fonte)
        return self.tokenize()

    def _peek(self) -> str:
        if self._pos >= len(self._source): return "\0"
        return self._source[self._pos]

    def _advance(self) -> str:
        ch = self._source[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else: self._col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < len(self._source):
            ch = self._peek()
            if ch.isspace(): self._advance()
            elif ch == "#":
                while self._peek() not in ("\n", "\0"): self._advance()
            else: break

    def _make_token(self, token_type: TokenType, lexeme: str, line: int, col: int) -> Token:
        return Token(token_type, lexeme, line, col)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self._pos < len(self._source):
            self._skip_whitespace_and_comments()
            if self._pos >= len(self._source): break

            ch = self._peek()
            start_line = self._line
            start_col = self._col

            if ch.isalpha() or ch == "_":
                ident = ""
                while self._peek().isalnum() or self._peek() == "_": ident += self._advance()
                ttype = KEYWORDS.get(ident, TokenType.IDENTIFIER)
                tokens.append(self._make_token(ttype, ident, start_line, start_col))
            elif ch.isdigit():
                num = ""
                while self._peek().isdigit(): num += self._advance()
                if self._peek() == ".":
                    num += self._advance()
                    while self._peek().isdigit(): num += self._advance()
                tokens.append(self._make_token(TokenType.NUMBER, num, start_line, start_col))
            elif ch == '"':
                self._advance()
                text = ""
                while self._peek() not in ('"', "\0"):
                    if self._peek() == "\\":
                        self._advance()
                        escaped = self._advance()
                        escape_map = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                        text += escape_map.get(escaped, escaped)
                    else: text += self._advance()
                if self._peek() != '"':
                    raise ErroLexico("String nao fechada (faltam as aspas finais)", start_line, start_col)
                self._advance()
                tokens.append(self._make_token(TokenType.STRING_LITERAL, text, start_line, start_col))
            else:
                op = self._advance()
                single_map = {"+": TokenType.PLUS, "-": TokenType.MINUS, "*": TokenType.STAR, "/": TokenType.SLASH, "%": TokenType.MOD, "{": TokenType.LBRACE, "}": TokenType.RBRACE, "(": TokenType.LPAREN, ")": TokenType.RPAREN, "[": TokenType.LBRACKET, "]": TokenType.RBRACKET, ";": TokenType.SEMICOLON, ",": TokenType.COMMA, ".": TokenType.DOT}
                if op == "=":
                    if self._peek() == "=":
                        self._advance()
                        tokens.append(self._make_token(TokenType.EQ, "==", start_line, start_col))
                    else: tokens.append(self._make_token(TokenType.ASSIGN, "=", start_line, start_col))
                elif op == "!":
                    if self._peek() == "=":
                        self._advance()
                        tokens.append(self._make_token(TokenType.NEQ, "!=", start_line, start_col))
                    else: tokens.append(self._make_token(TokenType.NOT, op, start_line, start_col))
                elif op == "&":
                    if self._peek() == "&":
                        self._advance()
                        tokens.append(self._make_token(TokenType.AND, "&&", start_line, start_col))
                    else:
                        raise ErroLexico("Caractere invalido: '&' (use '&&' para E logico)", start_line, start_col)
                elif op == "|":
                    if self._peek() == "|":
                        self._advance()
                        tokens.append(self._make_token(TokenType.OR, "||", start_line, start_col))
                    else:
                        raise ErroLexico("Caractere invalido: '|' (use '||' para OU logico)", start_line, start_col)
                elif op == "<":
                    if self._peek() == "=":
                        self._advance()
                        tokens.append(self._make_token(TokenType.LTE, "<=", start_line, start_col))
                    else: tokens.append(self._make_token(TokenType.LT, "<", start_line, start_col))
                elif op == ">":
                    if self._peek() == "=":
                        self._advance()
                        tokens.append(self._make_token(TokenType.GTE, ">=", start_line, start_col))
                    else: tokens.append(self._make_token(TokenType.GT, ">", start_line, start_col))
                elif op in single_map:
                    tokens.append(self._make_token(single_map[op], op, start_line, start_col))
                else:
                    raise ErroLexico(f"Caractere invalido: {op!r}", start_line, start_col)

        tokens.append(Token(TokenType.END_OF_FILE, "", self._line, self._col))
        return tokens


# Nome antigo mantido por compatibilidade
Lexer = C_Lexico
