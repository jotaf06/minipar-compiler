"""
Serializacao da AST para JSON (usada pelas interfaces web).

Cada no vira um dicionario no formato consumido pela arvore grafica:

    {
      "tipo":      "BinaryExpr",          # classe do no
      "categoria": "expressao",           # declaracao | comando | bloco | expressao | paralelo
      "rotulo":    "+",                   # texto curto exibido no no
      "linha":     3,                     # linha no codigo-fonte (para destacar no editor)
      "papel":     "condicao",            # nome do campo no no pai (ex.: condicao, corpo)
      "info":      {"op": "+"},           # demais atributos simples (inclui anotacoes do semantico)
      "filhos":    [ ... ]
    }

A conversao e generica (percorre os campos das dataclasses), entao novos nos da
AST aparecem automaticamente; o rotulo e a categoria tem regras por tipo.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional

from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign,
    NewExpr, ThisExpr, CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr,
    IndexExpr, IndexAssign, ForkStmt, JoinStmt, JoinExpr,
)

CATEGORIAS = {
    "declaracao": (Program, VarDecl, FuncDecl, ClassDecl),
    "bloco": (SeqBlock,),
    "paralelo": (ParBlock, ForkStmt, JoinStmt, JoinExpr, CChannelExpr, SendStmt, ReceiveExpr),
    "comando": (Assignment, PropertyAssign, IndexAssign, PrintStmt, IfStmt, WhileStmt,
                DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, ReturnStmt),
}

# Campos que nao entram em "info" (posicao ja vai em "linha"; filhos vao em "filhos")
_IGNORAR = {"line"}

# Papel de cada filho em portugues, para a arvore didatica (ex.: "condicao" de um if)
PAPEIS = {
    "statements": "comandos", "body": "corpo", "condition": "condicao",
    "then_branch": "entao", "else_branch": "senao", "left": "esquerda", "right": "direita",
    "operand": "operando", "value": "valor", "init_value": "valor inicial",
    "arguments": "argumentos", "elements": "elementos", "object": "objeto", "index": "indice",
    "target": "alvo", "call": "chamada", "core": "nucleo", "host": "computador", "porta": "porta",
    "initializer": "inicio", "increment": "incremento", "iterable": "colecao",
    "attributes": "atributos", "methods": "metodos", "rows": "linhas", "cols": "colunas",
    "channel": "canal", "message": "mensagem", "prompt": "mensagem", "ip": "endereco", "port": "porta",
}


def _categoria(no: ASTNode) -> str:
    for nome, tipos in CATEGORIAS.items():
        if isinstance(no, tipos):
            return nome
    return "expressao"


def _texto(valor: str, limite: int = 24) -> str:
    valor = valor.replace("\n", "\\n")
    return valor if len(valor) <= limite else valor[: limite - 1] + "…"


def rotulo(no: ASTNode) -> str:
    """Texto curto e didatico para o no (o que um iniciante leria na arvore)."""
    if isinstance(no, Program): return "programa"
    if isinstance(no, NumberExpr): return no.value
    if isinstance(no, StringExpr): return f'"{_texto(no.value)}"'
    if isinstance(no, BoolExpr): return "true" if no.value else "false"
    if isinstance(no, IdentifierExpr): return no.name
    if isinstance(no, BinaryExpr): return no.op
    if isinstance(no, UnaryExpr): return no.op
    if isinstance(no, VarDecl): return f"var {no.name}"
    if isinstance(no, Assignment): return f"{no.name} ="
    if isinstance(no, PropertyAssign): return f".{no.property_name} ="
    if isinstance(no, IndexAssign): return "[ ] ="
    if isinstance(no, PrintStmt): return "print"
    if isinstance(no, SeqBlock): return "seq"
    if isinstance(no, ParBlock): return "par"
    if isinstance(no, IfStmt): return "if"
    if isinstance(no, WhileStmt): return "while"
    if isinstance(no, DoWhileStmt): return "do-while"
    if isinstance(no, ForStmt): return f"for {no.iterator_name} in" if no.iterator_name else "for"
    if isinstance(no, BreakStmt): return "break"
    if isinstance(no, ContinueStmt): return "continue"
    if isinstance(no, ReturnStmt): return "return"
    if isinstance(no, FuncDecl): return f"func {no.name}({', '.join(no.params)})"
    if isinstance(no, ClassDecl):
        return f"class {no.name}" + (f" extends {no.superclass}" if no.superclass else "")
    if isinstance(no, MethodCall): return f".{no.method_name}( )"
    if isinstance(no, FuncCallExpr): return f"{no.name}( )"
    if isinstance(no, PropertyAccess): return f".{no.property_name}"
    if isinstance(no, NewExpr): return f"new {no.class_name}"
    if isinstance(no, ThisExpr): return "this"
    if isinstance(no, InputExpr): return "input"
    if isinstance(no, CChannelExpr): return "c_channel"
    if isinstance(no, SendStmt): return "send"
    if isinstance(no, ReceiveExpr): return "receive"
    if isinstance(no, ListLiteral): return "[ lista ]"
    if isinstance(no, MatrixCreateExpr): return "matrix"
    if isinstance(no, IndexExpr): return "[ ]"
    if isinstance(no, ForkStmt):
        destino = " on core" if no.core is not None else (" on host" if no.host is not None else "")
        return f"fork {no.handle}{destino}"
    if isinstance(no, JoinStmt):
        return "join " + ", ".join(no.handles) if no.handles else "join"
    if isinstance(no, JoinExpr): return f"join {no.handle}"
    return type(no).__name__


def _vazio(valor: Any) -> bool:
    """Valores padrao omitidos de "info" (comparacao por tipo: 0 nao e False)."""
    return valor is None or valor is False or valor == "" or (type(valor) is int and valor == -1)


def _simples(valor: Any) -> bool:
    return valor is None or isinstance(valor, (str, int, float, bool))


def ast_para_dict(no: Optional[ASTNode], papel: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Converte um no (e seus descendentes) para dicionario serializavel em JSON."""
    if no is None:
        return None
    filhos: List[Dict[str, Any]] = []
    info: Dict[str, Any] = {}
    for campo in dataclasses.fields(no):
        if campo.name in _IGNORAR:
            continue
        valor = getattr(no, campo.name)
        if isinstance(valor, ASTNode):
            filhos.append(ast_para_dict(valor, PAPEIS.get(campo.name, campo.name)))
        elif isinstance(valor, list) and any(isinstance(v, ASTNode) for v in valor):
            for item in valor:
                if isinstance(item, ASTNode):
                    filhos.append(ast_para_dict(item, PAPEIS.get(campo.name, campo.name)))
        elif isinstance(valor, list) and all(_simples(v) for v in valor):
            if valor:
                info[campo.name] = valor
        elif _simples(valor) and not _vazio(valor):
            info[campo.name] = valor
    return {
        "tipo": type(no).__name__,
        "categoria": _categoria(no),
        "rotulo": rotulo(no),
        "linha": getattr(no, "line", None),
        "papel": papel,
        "info": info,
        "filhos": filhos,
    }
