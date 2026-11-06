from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

class ASTNode:
    line: int = 1

@dataclass
class NumberExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class StringExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class BoolExpr(ASTNode):
    value: bool
    line: int = 1

@dataclass
class IdentifierExpr(ASTNode):
    name: str
    line: int = 1

@dataclass
class BinaryExpr(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode
    line: int = 1

@dataclass
class UnaryExpr(ASTNode):
    op: str
    operand: ASTNode
    line: int = 1

@dataclass
class VarDecl(ASTNode):
    name: str
    init_value: Optional[ASTNode] = None
    type: str = "var"
    line: int = 1
    # Preenchido pelo semantico: a variavel comeca inteira, mas recebe um valor real
    # em alguma atribuicao (ex.: soma = 0; soma = soma + 0.5). O gerador C++ a declara
    # como double desde o inicio, como o Python faria.
    promover_double: bool = False
    # Preenchidos pelo semantico para variaveis declaradas no topo do programa
    # (fora de blocos): viram variaveis globais no C++, visiveis nas funcoes.
    escopo_global: bool = False
    tipo_cpp: Optional[str] = None

@dataclass
class Assignment(ASTNode):
    name: str
    value: ASTNode = None
    line: int = 1

@dataclass
class PrintStmt(ASTNode):
    arguments: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class SeqBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class ParBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None
    line: int = 1

@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode
    line: int = 1

@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode
    condition: ASTNode
    line: int = 1

@dataclass
class ForStmt(ASTNode):
    initializer: Optional[ASTNode]
    condition: Optional[ASTNode]
    increment: Optional[ASTNode]
    body: ASTNode
    iterator_name: Optional[str] = None
    iterable: Optional[ASTNode] = None
    line: int = 1

@dataclass
class BreakStmt(ASTNode):
    line: int = 1

@dataclass
class ContinueStmt(ASTNode):
    line: int = 1

@dataclass
class ClassDecl(ASTNode):
    name: str
    superclass: Optional[str]
    attributes: List[VarDecl]
    methods: List[FuncDecl]
    line: int = 1

@dataclass
class FuncDecl(ASTNode):
    name: str
    params: List[str]
    body: ASTNode
    line: int = 1
    # Preenchido pelo semantico: algum return devolve um valor real (C++ retorna double)
    retorno_real: bool = False

@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode]
    line: int = 1

@dataclass
class MethodCall(ASTNode):
    object: ASTNode
    method_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class FuncCallExpr(ASTNode):
    name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class PropertyAccess(ASTNode):
    object: ASTNode
    property_name: str
    line: int = 1

@dataclass
class PropertyAssign(ASTNode):
    object: ASTNode
    property_name: str
    value: ASTNode
    line: int = 1

@dataclass
class NewExpr(ASTNode):
    class_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class ThisExpr(ASTNode):
    line: int = 1

@dataclass
class CChannelExpr(ASTNode):
    ip: ASTNode
    port: ASTNode
    line: int = 1

@dataclass
class SendStmt(ASTNode):
    channel: ASTNode
    message: ASTNode
    line: int = 1

@dataclass
class ReceiveExpr(ASTNode):
    channel: ASTNode
    line: int = 1

@dataclass
class InputExpr(ASTNode):
    prompt: Optional[ASTNode] = None
    line: int = 1

@dataclass
class ListLiteral(ASTNode):
    elements: List[ASTNode]
    line: int = 1
    # Tipo C++ dos elementos, preenchido pelo semantico ("long long", "double",
    # "std::string", ...). None: o proprio C++ deduz a partir dos elementos.
    tipo_elemento: Optional[str] = None

@dataclass
class MatrixCreateExpr(ASTNode):
    rows: ASTNode
    cols: ASTNode
    init_value: ASTNode
    line: int = 1
    # Preenchido pelo semantico: matriz criada com inteiro que recebe valores reais
    promover_double: bool = False

@dataclass
class IndexExpr(ASTNode):
    object: ASTNode
    index: ASTNode
    line: int = 1

@dataclass
class IndexAssign(ASTNode):
    target: ASTNode
    value: ASTNode
    line: int = 1

@dataclass
class Program(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1


# ---------------------------------------------------------------------------
# Fork / Join (MiniPar 2026.2)
# ---------------------------------------------------------------------------
@dataclass
class ForkStmt(ASTNode):
    """fork t = chamada(...) [on core n];  -> dispara a chamada como subtarefa paralela."""
    handle: str
    call: ASTNode                    # FuncCallExpr ou MethodCall
    core: Optional[ASTNode] = None   # nucleo da CPU (None: escolhido pelo sistema)
    line: int = 1
    host: Optional[ASTNode] = None   # on host "ip":porta -> subtarefa em outro computador
    porta: Optional[ASTNode] = None
    # Preenchidos pelo semantico para fork remoto: tipos C++ dos argumentos (o computador
    # remoto precisa deles para reconstruir os valores) e numero do fork no programa
    tipos_args: List[str] = field(default_factory=list)
    id_remoto: int = -1

@dataclass
class JoinStmt(ASTNode):
    """join t1, t2;  ou  join;  -> espera as subtarefas terminarem."""
    handles: List[str] = field(default_factory=list)
    line: int = 1
    # Preenchido pelo semantico quando "join;" (sem nomes): todas as tarefas visiveis
    handles_resolvidos: List[str] = field(default_factory=list)

@dataclass
class JoinExpr(ASTNode):
    """join t  (em expressao) -> espera a subtarefa e devolve o valor que ela retornou."""
    handle: str
    line: int = 1
