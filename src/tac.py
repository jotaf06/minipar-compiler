from __future__ import annotations
from typing import Optional
from interfaces import IGeradorTAC
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign,
    ForkStmt, JoinStmt, JoinExpr
)

class C_GeradorTAC(IGeradorTAC):
    """Componente Gerador de Codigo Intermediario (TAC) - implementa IGeradorTAC.

    Quebra expressoes em instrucoes de no maximo 3 enderecos usando
    temporarios (t0, t1, ...) e traduz o fluxo de controle em rotulos e
    desvios (goto / ifFalse ... goto).
    """

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self.lines: list[str] = []
        self.temp_count = 0
        self.label_count = 0
        self.break_stack: list[str] = []
        self.continue_stack: list[str] = []

    def _temp(self) -> str:
        name = f"t{self.temp_count}"
        self.temp_count += 1
        return name

    def _label(self, prefix: str) -> str:
        name = f"{prefix}_{self.label_count}"
        self.label_count += 1
        return name

    def _emit(self, line: str = "") -> None:
        self.lines.append(line)

    def _expr(self, node: Optional[ASTNode]) -> str:
        if node is None: return "0"
        if isinstance(node, NumberExpr): return node.value
        if isinstance(node, StringExpr): return f'"{node.value}"'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, UnaryExpr):
            value = self._expr(node.operand)
            tmp = self._temp()
            self._emit(f"{tmp} = {node.op}{value}")
            return tmp
        if isinstance(node, BinaryExpr):
            left = self._expr(node.left)
            right = self._expr(node.right)
            tmp = self._temp()
            self._emit(f"{tmp} = {left} {node.op} {right}")
            return tmp
        if isinstance(node, ListLiteral):
            tmp = self._temp()
            values = ", ".join(self._expr(e) for e in node.elements)
            self._emit(f"{tmp} = [{values}]")
            return tmp
        if isinstance(node, MatrixCreateExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = matrix({self._expr(node.rows)}, {self._expr(node.cols)}, {self._expr(node.init_value)})")
            return tmp
        if isinstance(node, IndexExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}[{self._expr(node.index)}]")
            return tmp
        if isinstance(node, PropertyAccess):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}.{node.property_name}")
            return tmp
        if isinstance(node, (FuncCallExpr, MethodCall)):
            args = node.arguments
            name = node.name if isinstance(node, FuncCallExpr) else f"{self._expr(node.object)}.{node.method_name}"
            for arg in args:
                self._emit(f"param {self._expr(arg)}")
            tmp = self._temp()
            self._emit(f"{tmp} = call {name}, {len(args)}")
            return tmp
        if isinstance(node, NewExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = new {node.class_name}")
            return tmp
        if isinstance(node, CChannelExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = c_channel({self._expr(node.ip)}, {self._expr(node.port)})")
            return tmp
        if isinstance(node, ReceiveExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = receive {self._expr(node.channel)}")
            return tmp
        if isinstance(node, InputExpr):
            tmp = self._temp()
            if node.prompt:
                self._emit(f"{tmp} = input({self._expr(node.prompt)})")
            else:
                self._emit(f"{tmp} = input()")
            return tmp
        if isinstance(node, JoinExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = join {node.handle}")
            return tmp
        return "?"

    def _stmt(self, node: Optional[ASTNode]) -> None:
        if node is None: return
        if isinstance(node, VarDecl):
            self._emit(f"{node.name} = {self._expr(node.init_value)}")
        elif isinstance(node, Assignment):
            self._emit(f"{node.name} = {self._expr(node.value)}")
        elif isinstance(node, PropertyAssign):
            self._emit(f"{self._expr(node.object)}.{node.property_name} = {self._expr(node.value)}")
        elif isinstance(node, IndexAssign):
            self._emit(f"{self._expr(node.target.object)}[{self._expr(node.target.index)}] = {self._expr(node.value)}")
        elif isinstance(node, PrintStmt):
            for arg in node.arguments:
                self._emit(f"print {self._expr(arg)}")
        elif isinstance(node, SendStmt):
            self._emit(f"send {self._expr(node.channel)}, {self._expr(node.message)}")
        elif isinstance(node, ForkStmt):
            # Mesmo formato de "call", mas a chamada vira uma subtarefa paralela
            args = node.call.arguments
            nome = node.call.name if isinstance(node.call, FuncCallExpr) \
                else f"{self._expr(node.call.object)}.{node.call.method_name}"
            for arg in args:
                self._emit(f"param {self._expr(arg)}")
            destino = f", core {self._expr(node.core)}" if node.core is not None else ""
            if node.host is not None:
                destino = f", host {self._expr(node.host)}:{self._expr(node.porta)}"
            self._emit(f"{node.handle} = fork {nome}, {len(args)}{destino}")
        elif isinstance(node, JoinStmt):
            for h in node.handles_resolvidos:
                self._emit(f"join {h}")
        elif isinstance(node, (SeqBlock, ParBlock)):
            for stmt in node.statements: self._stmt(stmt)
        elif isinstance(node, IfStmt):
            end = self._label("ENDIF")
            else_label = self._label("ELSE") if node.else_branch else end
            self._emit(f"ifFalse {self._expr(node.condition)} goto {else_label}")
            self._stmt(node.then_branch)
            if node.else_branch:
                self._emit(f"goto {end}")
                self._emit(f"{else_label}:")
                self._stmt(node.else_branch)
            self._emit(f"{end}:")
        elif isinstance(node, WhileStmt):
            start, end = self._label("WHILE"), self._label("ENDWHILE")
            self.break_stack.append(end); self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, DoWhileStmt):
            start, end = self._label("DO"), self._label("ENDDO")
            self.break_stack.append(end); self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._stmt(node.body)
            self._emit(f"if {self._expr(node.condition)} goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, ForStmt):
            if node.iterator_name:
                self._emit(f"# for {node.iterator_name} in {self._expr(node.iterable)}")
                self._stmt(node.body)
                return
            start, step, end = self._label("FOR"), self._label("FOR_STEP"), self._label("ENDFOR")
            self._stmt(node.initializer)
            self.break_stack.append(end); self.continue_stack.append(step)
            self._emit(f"{start}:")
            if node.condition:
                self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"{step}:")
            self._stmt(node.increment)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, BreakStmt):
            self._emit(f"goto {self.break_stack[-1] if self.break_stack else 'END'}")
        elif isinstance(node, ContinueStmt):
            self._emit(f"goto {self.continue_stack[-1] if self.continue_stack else 'CONTINUE'}")
        elif isinstance(node, ReturnStmt):
            self._emit(f"return {self._expr(node.value)}" if node.value else "return")
        elif isinstance(node, (FuncCallExpr, MethodCall)):
            self._expr(node)
        elif isinstance(node, ClassDecl):
            self._emit(f"# class {node.name}")
            for method in node.methods: self._stmt(method)
        elif isinstance(node, FuncDecl):
            self._emit(f"func {node.name}:")
            self._stmt(node.body)
            self._emit(f"endfunc {node.name}")

    # ---- Interface IGeradorTAC ----
    def gerar(self, programa: Program) -> str:
        self._reset()
        return self.generate_text(programa)

    def generate_text(self, program: Program) -> str:
        for stmt in program.statements:
            self._stmt(stmt)
        return "\n".join(self.lines) + ("\n" if self.lines else "")
