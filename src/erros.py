"""
Erros do Compilador MiniPar 2026.2.

Cada fase do compilador sinaliza problemas lancando uma excecao derivada de
ErroCompilacao, em vez de encerrar o processo com sys.exit(). Assim, quem
chamou a fase (o terminal, a IDE web ou a interface didatica) decide como
exibir o erro, e o servidor web continua rodando apos um erro do usuario.

Hierarquia:
    ErroCompilacao
    ├── ErroLexico     (fase 1 - caractere invalido, string nao fechada)
    ├── ErroSintatico  (fase 2 - estrutura fora da gramatica BNF)
    ├── ErroSemantico  (fase 3 - escopo, tipos, declaracoes)
    └── ErroGeracao    (fases 4/5 - geracao de codigo ou compilacao pelo g++)
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ErroCompilacao(Exception):
    """Erro generico do compilador, com a fase e a posicao no codigo-fonte."""

    fase: str = "COMPILACAO"

    def __init__(self, mensagem: str, linha: Optional[int] = None, coluna: Optional[int] = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna

    def __str__(self) -> str:
        posicao = ""
        if self.linha is not None:
            posicao = f" Linha {self.linha}"
            if self.coluna is not None:
                posicao += f", coluna {self.coluna}"
            posicao += ":"
        return f"[ERRO {self.fase}]{posicao} {self.mensagem}"

    def para_dict(self) -> Dict[str, Any]:
        """Formato usado pelas interfaces web (JSON)."""
        return {
            "fase": self.fase,
            "mensagem": self.mensagem,
            "linha": self.linha,
            "coluna": self.coluna,
        }


class ErroLexico(ErroCompilacao):
    fase = "LEXICO"


class ErroSintatico(ErroCompilacao):
    fase = "SINTATICO"


class ErroSemantico(ErroCompilacao):
    fase = "SEMANTICO"


class ErroGeracao(ErroCompilacao):
    fase = "GERACAO"


class Aviso(ErroCompilacao):
    """Problema que nao impede a compilacao, mas merece atencao (ex.: fork que
    altera variavel global compartilhada entre subtarefas)."""
    fase = "AVISO"

    def __str__(self) -> str:
        posicao = f" Linha {self.linha}:" if self.linha is not None else ""
        return f"[AVISO]{posicao} {self.mensagem}"
