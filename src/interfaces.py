"""
Interfaces dos Componentes de Software do Compilador MiniPar 2026.2.

Python nao possui a palavra-chave "interface" (como Java). Seguindo o material
"Elementos de Implementacao Utilizando Componentes", cada interface e
representada por uma CLASSE ABSTRATA (prefixo I), e cada componente (prefixo C_)
herda dela e fornece a implementacao do algoritmo correspondente.

Uso dos componentes sempre via interface, por exemplo:

    ilexico: ILexico = C_Lexico()
    tokens = ilexico.analisar(codigo_fonte)

Fluxo entre os componentes (cada seta e uma chamada atraves de uma interface):

    codigo ─► ILexico ─► tokens ─► ISintatico ─► AST ─► ISemantico (usa ITabelaSimbolos)
                                                         │
                          IGeradorTAC ◄─────── AST valida ┤
                          IGeradorCpp ◄──────────────────┘
                               │
                          codigo C++ ─► ICompiladorCpp (g++) ─► executavel

    IControle coordena toda a sequencia acima.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ILexico(ABC):
    """Analisador Lexico: transforma o codigo-fonte em uma lista de tokens."""

    @abstractmethod
    def analisar(self, codigo_fonte: str) -> List[Any]:
        """Retorna a lista de tokens. Lanca ErroLexico em caso de erro."""


class ISintatico(ABC):
    """Analisador Sintatico: valida a gramatica e constroi a AST."""

    @abstractmethod
    def analisar(self, tokens: List[Any]) -> Any:
        """Retorna a raiz da AST (Program). Lanca ErroSintatico em caso de erro."""


class ITabelaSimbolos(ABC):
    """Tabela de Simbolos com escopos aninhados (pilha de escopos)."""

    @abstractmethod
    def entrar_escopo(self, nome: str = "") -> None:
        """Empilha um novo escopo (bloco, funcao, classe...)."""

    @abstractmethod
    def sair_escopo(self) -> None:
        """Desempilha o escopo atual (o escopo global nunca e removido)."""

    @abstractmethod
    def definir(self, nome: str, tipo: str, linha: int, parametros: Optional[List[str]] = None) -> bool:
        """Declara um simbolo no escopo atual. Retorna False se ja existir nele."""

    @abstractmethod
    def buscar(self, nome: str) -> Optional[Any]:
        """Procura o simbolo do escopo mais interno para o mais externo."""

    @abstractmethod
    def nivel(self) -> int:
        """Profundidade do escopo atual (0 = global)."""

    @abstractmethod
    def exportar(self) -> List[Dict[str, Any]]:
        """Lista todos os simbolos ja declarados (para exibicao nas interfaces)."""


class ISemantico(ABC):
    """Analisador Semantico: escopos, tipos, declaracoes e chamadas."""

    @abstractmethod
    def analisar(self, programa: Any) -> bool:
        """Valida a AST. Retorna True se nao houver erros."""

    @abstractmethod
    def obter_erros(self) -> List[Any]:
        """Lista de ErroSemantico encontrados (a analise nao para no primeiro)."""

    @abstractmethod
    def obter_tabela(self) -> ITabelaSimbolos:
        """Tabela de simbolos preenchida durante a analise."""


class IGeradorTAC(ABC):
    """Gerador de Codigo Intermediario de Tres Enderecos (TAC)."""

    @abstractmethod
    def gerar(self, programa: Any) -> str:
        """Retorna o codigo TAC em texto."""


class IGeradorCpp(ABC):
    """Gerador de Codigo C++ a partir da AST."""

    @abstractmethod
    def gerar(self, programa: Any) -> str:
        """Retorna o codigo C++ completo (com o template de suporte)."""


class ICompiladorCpp(ABC):
    """Compilador do codigo C++ gerado (g++) para um executavel."""

    @abstractmethod
    def compilar(self, codigo_cpp: str, nome_saida: str) -> str:
        """Gera o executavel e retorna seu caminho. Lanca ErroGeracao se falhar."""


class IControle(ABC):
    """Controle do compilador: coordena todas as fases na ordem correta."""

    @abstractmethod
    def compilar(self, codigo_fonte: str, nome_saida: str, gerar_executavel: bool = True) -> Any:
        """Executa as fases e retorna um ResultadoCompilacao com o produto de cada uma."""
