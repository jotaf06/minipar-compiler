"""
Componente Tabela de Simbolos (C_TabelaSimbolos) - implementa ITabelaSimbolos.

Estrutura: PILHA DE ESCOPOS. Cada escopo e um dicionario nome -> Simbolo.
  - entrar_escopo(): empilha um escopo novo (bloco seq/par, funcao, classe, for)
  - sair_escopo():   desempilha (o escopo global, na base, nunca sai)
  - definir():       declara no escopo do TOPO; rejeita duplicata nesse escopo
  - buscar():        procura do TOPO para a BASE (o mais interno "esconde" o externo)

Exemplo:
    var x = 1;          # global: {x}
    func f(a) {         # escopo "funcao f": {a}
        var x = 2;      # declara outro x, que esconde o x global dentro de f
        print(x);       # buscar("x") encontra primeiro o x de f -> 2
    }

Alem da pilha (que muda durante a analise), o componente guarda um HISTORICO
de todos os simbolos declarados, com o escopo e a linha, para que as
interfaces possam exibir a tabela completa depois que a analise termina.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from interfaces import ITabelaSimbolos


@dataclass
class Simbolo:
    nome: str
    tipo: str
    linha: int = 0
    escopo: str = "global"
    parametros: List[str] = field(default_factory=list)
    atributos: Dict[str, str] = field(default_factory=dict)
    metodos: Dict[str, List[str]] = field(default_factory=dict)


class C_TabelaSimbolos(ITabelaSimbolos):
    def __init__(self) -> None:
        self._escopos: List[Dict[str, Simbolo]] = []
        self._nomes_escopos: List[str] = []
        self._historico: List[Simbolo] = []
        self.entrar_escopo("global")

    def entrar_escopo(self, nome: str = "bloco") -> None:
        self._escopos.append({})
        self._nomes_escopos.append(nome)

    def sair_escopo(self) -> None:
        if len(self._escopos) > 1:
            self._escopos.pop()
            self._nomes_escopos.pop()

    def escopo_atual(self) -> str:
        return self._nomes_escopos[-1]

    def nivel(self) -> int:
        """Profundidade do escopo atual (0 = global)."""
        return len(self._escopos) - 1

    def definir(self, nome: str, tipo: str, linha: int, parametros: Optional[List[str]] = None) -> bool:
        escopo = self._escopos[-1]
        if nome in escopo:
            return False
        simbolo = Simbolo(nome=nome, tipo=tipo, linha=linha, escopo=self.escopo_atual(),
                          parametros=list(parametros or []))
        escopo[nome] = simbolo
        self._historico.append(simbolo)
        return True

    def buscar(self, nome: str) -> Optional[Simbolo]:
        for escopo in reversed(self._escopos):
            if nome in escopo:
                return escopo[nome]
        return None

    def exportar(self) -> List[Dict[str, Any]]:
        return [
            {
                "nome": s.nome,
                "tipo": s.tipo,
                "escopo": s.escopo,
                "linha": s.linha,
                "parametros": s.parametros,
            }
            for s in self._historico
        ]
