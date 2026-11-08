"""
Funcoes de apoio compartilhadas pelos testes de unidade e de integracao.

Cada funcao executa o compilador ate uma fase, sempre atraves dos componentes
C_* (como o C_Controle faz), para que cada teste exercite um componente isolado.
"""
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(RAIZ, "src")
PASTA_TESTES = os.path.join(RAIZ, "tests")
for caminho in (RAIZ, SRC):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

from lexer import C_Lexico, TokenType          # noqa: E402,F401
from parser import C_Sintatico                 # noqa: E402
from semantic import C_Semantico               # noqa: E402
from tac import C_GeradorTAC                   # noqa: E402
from codegen import C_GeradorCpp               # noqa: E402


def tokens(codigo):
    return C_Lexico().analisar(codigo)


def tipos(codigo):
    """Tipos dos tokens, sem o END_OF_FILE final."""
    return [t.type for t in tokens(codigo)[:-1]]


def ast(codigo):
    return C_Sintatico().analisar(tokens(codigo))


def semantico(codigo):
    """Retorna (valido, semantico, ast) - o semantico guarda erros, avisos e tabela."""
    programa = ast(codigo)
    sem = C_Semantico()
    valido = sem.analisar(programa)
    return valido, sem, programa


def mensagens_erro(codigo):
    _, sem, _ = semantico(codigo)
    return [e.mensagem for e in sem.obter_erros()]


def mensagens_aviso(codigo):
    _, sem, _ = semantico(codigo)
    return [a.mensagem for a in sem.obter_avisos()]


def programa_valido(codigo):
    """AST ja validada (o semantico preenche informacoes usadas pelos geradores)."""
    valido, sem, programa = semantico(codigo)
    if not valido:
        raise AssertionError("Programa de teste invalido: " + "; ".join(map(str, sem.obter_erros())))
    return programa


def tac(codigo):
    return C_GeradorTAC().gerar(programa_valido(codigo))


def tac_linhas(codigo):
    return [l.strip() for l in tac(codigo).splitlines() if l.strip()]


def cpp(codigo):
    return C_GeradorCpp().gerar(programa_valido(codigo))


MARCA_CODIGO_USUARIO = "// ===== Codigo gerado a partir do programa MiniPar ====="
MARCA_SUPORTE_REMOTO = "// ----- Suporte ao fork remoto"


def cpp_usuario(codigo):
    """Somente a parte do C++ gerada a partir do programa (sem o template de suporte)."""
    texto = cpp(codigo)
    inicio = texto.index(MARCA_CODIGO_USUARIO)
    return texto[inicio:texto.index(MARCA_SUPORTE_REMOTO, inicio)]


def cpp_remoto(codigo):
    """Trecho final do C++: assinatura, globais do trabalhador e tabela de despacho."""
    texto = cpp(codigo)
    return texto[texto.index(MARCA_SUPORTE_REMOTO):]
