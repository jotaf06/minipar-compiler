"""
Componente Controle do Compilador (C_Controle) - implementa IControle.

Coordena as fases na ordem correta, sempre atraves das interfaces:

    Fase 1  ILexico         codigo-fonte -> tokens
    Fase 2  ISintatico      tokens       -> AST
    Fase 3  ISemantico      AST          -> AST validada + tabela de simbolos
    Fase 4  IGeradorTAC     AST          -> codigo de tres enderecos
    Fase 5  IGeradorCpp     AST          -> codigo C++
    Fase 6  ICompiladorCpp  C++          -> executavel (g++ -O3)

O resultado de TODAS as fases executadas fica em um ResultadoCompilacao.
Se uma fase falhar, as seguintes nao sao executadas, mas o que ja foi
produzido (ex.: tokens e AST quando o erro e semantico) continua disponivel.
E isso que permite a interface didatica exibir cada fase separadamente.

Os componentes podem ser injetados no construtor (ex.: um lexico
alternativo), desde que implementem a interface correspondente.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from interfaces import (
    IControle, ILexico, ISintatico, ISemantico, IGeradorTAC, IGeradorCpp, ICompiladorCpp,
)
from erros import ErroCompilacao
from lexer import C_Lexico
from parser import C_Sintatico
from semantic import C_Semantico
from tac import C_GeradorTAC
from codegen import C_GeradorCpp
from compilador_gcc import C_CompiladorGcc


@dataclass
class ResultadoCompilacao:
    """Produto de cada fase da compilacao de um programa MiniPar."""
    nome: str
    sucesso: bool = False
    fase_erro: Optional[str] = None          # fase em que a compilacao parou
    erros: List[ErroCompilacao] = field(default_factory=list)
    tokens: List[Any] = field(default_factory=list)
    ast: Optional[Any] = None
    simbolos: List[Dict[str, Any]] = field(default_factory=list)
    tac: str = ""
    cpp: str = ""
    executavel: Optional[str] = None

    def para_dict(self) -> Dict[str, Any]:
        """Formato JSON para as interfaces web (a AST e serializada a parte)."""
        return {
            "nome": self.nome,
            "sucesso": self.sucesso,
            "fase_erro": self.fase_erro,
            "erros": [e.para_dict() for e in self.erros],
            "tokens": [
                {"tipo": t.type.name, "lexema": t.lexeme, "linha": t.line, "coluna": t.col}
                for t in self.tokens
            ],
            "simbolos": self.simbolos,
            "tac": self.tac,
            "cpp": self.cpp,
            "executavel": self.executavel,
        }


class C_Controle(IControle):
    def __init__(
        self,
        lexico: Optional[ILexico] = None,
        sintatico: Optional[ISintatico] = None,
        semantico_factory: Optional[Callable[[], ISemantico]] = None,
        gerador_tac: Optional[IGeradorTAC] = None,
        gerador_cpp: Optional[IGeradorCpp] = None,
        compilador: Optional[ICompiladorCpp] = None,
        pasta_saida: str = "output",
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.lexico: ILexico = lexico or C_Lexico()
        self.sintatico: ISintatico = sintatico or C_Sintatico()
        # O semantico guarda estado (escopos, erros): um objeto novo a cada compilacao
        self.semantico_factory = semantico_factory or C_Semantico
        self.gerador_tac: IGeradorTAC = gerador_tac or C_GeradorTAC()
        self.gerador_cpp: IGeradorCpp = gerador_cpp or C_GeradorCpp()
        self.compilador: ICompiladorCpp = compilador or C_CompiladorGcc(pasta_saida)
        self.pasta_saida = pasta_saida
        self._log = log or (lambda _msg: None)

    def compilar(self, codigo_fonte: str, nome_saida: str, gerar_executavel: bool = True) -> ResultadoCompilacao:
        r = ResultadoCompilacao(nome=nome_saida)
        fase = "LEXICO"
        try:
            self._log("[Fase 1] Analise Lexica...")
            r.tokens = self.lexico.analisar(codigo_fonte)

            fase = "SINTATICO"
            self._log("[Fase 2] Analise Sintatica (construcao da AST)...")
            r.ast = self.sintatico.analisar(r.tokens)

            fase = "SEMANTICO"
            self._log("[Fase 3] Analise Semantica e Tabela de Simbolos...")
            semantico = self.semantico_factory()
            valido = semantico.analisar(r.ast)
            r.simbolos = semantico.obter_tabela().exportar()
            if not valido:
                r.erros.extend(semantico.obter_erros())
                r.fase_erro = fase
                return r

            fase = "TAC"
            self._log("[Fase 4] Geracao de Codigo Intermediario (TAC - 3 enderecos)...")
            r.tac = self.gerador_tac.gerar(r.ast)
            self._salvar(f"{nome_saida}.tac", r.tac)

            fase = "CPP"
            self._log("[Fase 5] Geracao de Codigo C++...")
            r.cpp = self.gerador_cpp.gerar(r.ast)

            if gerar_executavel:
                fase = "GCC"
                self._log("[Fase 6] Compilacao com g++ -O3...")
                r.executavel = self.compilador.compilar(r.cpp, nome_saida)
            else:
                self._salvar(f"{nome_saida}.cpp", r.cpp)

            r.sucesso = True
        except ErroCompilacao as erro:
            r.erros.append(erro)
            r.fase_erro = fase
        return r

    def _salvar(self, nome_arquivo: str, conteudo: str) -> None:
        os.makedirs(self.pasta_saida, exist_ok=True)
        with open(os.path.join(self.pasta_saida, nome_arquivo), "w", encoding="utf-8") as f:
            f.write(conteudo)
