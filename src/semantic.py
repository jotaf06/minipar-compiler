from __future__ import annotations
from typing import Dict, List, Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, IdentifierExpr, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, SeqBlock, ParBlock, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)
from erros import ErroSemantico
from interfaces import ISemantico, ITabelaSimbolos
from tabela_simbolos import C_TabelaSimbolos, Simbolo


class C_Semantico(ISemantico):
    """Componente Analisador Semantico - implementa ISemantico.

    Percorre a AST em duas passadas:
      1. coleta as declaracoes globais de classes e funcoes (permite usar
         uma funcao antes do ponto em que ela foi declarada);
      2. valida cada no: escopo, tipos, aridade de chamadas, break/continue.
    Os escopos e simbolos ficam no componente Tabela de Simbolos, acessado
    somente pela interface ITabelaSimbolos.
    """

    def __init__(self, tabela: Optional[ITabelaSimbolos] = None) -> None:
        self._tabela: ITabelaSimbolos = tabela or C_TabelaSimbolos()
        # Erros acumulados: a analise continua apos um erro para reportar todos de uma vez
        self.erros: List[ErroSemantico] = []
        self._current_function: Optional[str] = None
        self._current_class: Optional[str] = None
        self._classes: Dict[str, Simbolo] = {}
        self._functions: Dict[str, Simbolo] = {}
        self._loop_depth = 0
        self._class_attr_decls: Dict[str, Dict[str, VarDecl]] = {}
        self._promocoes = 0
        # (classe ou None, funcao) -> indices dos parametros que recebem valor real em
        # alguma chamada. Persiste entre as rodadas da analise (ver analyze()).
        self._params_reais: Dict[tuple, set] = {}

    # ---- Interface ISemantico ----
    def analisar(self, programa: Program) -> bool:
        return self.analyze(programa)

    def obter_erros(self) -> List[ErroSemantico]:
        return list(self.erros)

    def obter_tabela(self) -> ITabelaSimbolos:
        return self._tabela

    # ---- Escopos: delegados a Tabela de Simbolos ----
    def _enter_scope(self, nome: str = "bloco") -> None: self._tabela.entrar_escopo(nome)
    def _exit_scope(self) -> None: self._tabela.sair_escopo()

    def _get_context(self) -> str:
        if not self._current_function:
            return ""
        if self._current_class:
            return f" (Metodo: {self._current_class}.{self._current_function})"
        return f" (Funcao: {self._current_function})"

    def _define_symbol(self, name: str, type_: str, line: int, params: Optional[List[str]] = None) -> None:
        if not self._tabela.definir(name, type_, line, params):
            self._report(line, f"Variavel '{name}' ja declarada.")

    def _lookup(self, name: str) -> Optional[Simbolo]:
        return self._tabela.buscar(name)

    def _report(self, line: int, message: str) -> None:
        self.erros.append(ErroSemantico(f"{message}{self._get_context()}", line))

    def _infer_type(self, node: Optional[ASTNode]) -> str:
        if node is None: return "unknown"
        if isinstance(node, NumberExpr): return "number"
        if isinstance(node, StringExpr): return "string"
        if isinstance(node, BoolExpr): return "bool"
        if isinstance(node, InputExpr): return "string"
        if isinstance(node, CChannelExpr): return "c_channel"
        if isinstance(node, ReceiveExpr): return "string"
        if isinstance(node, ListLiteral): return "list"
        if isinstance(node, MatrixCreateExpr): return "matrix"
        if isinstance(node, NewExpr): return node.class_name
        if isinstance(node, ThisExpr): return self._current_class or "unknown"
        if isinstance(node, IdentifierExpr):
            sym = self._lookup(node.name)
            return sym.tipo if sym else "unknown"
        if isinstance(node, UnaryExpr):
            return "bool" if node.op == "!" else self._infer_type(node.operand)
        if isinstance(node, BinaryExpr):
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"): return "bool"
            if node.op == "+" and (lt == "string" or rt == "string"): return "string"
            if node.op == "+" and (lt == "list" or rt == "list"): return "list"
            return "number"
        if isinstance(node, PropertyAccess):
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name in cls.atributos: return cls.atributos[node.property_name]
            return "unknown"
        if isinstance(node, MethodCall):
            return "unknown"
        if isinstance(node, FuncCallExpr):
            if node.name in ("random", "exp", "len"): return "number"
            if node.name in ("range", "parse_ints"): return "list"
            if node.name == "join_str": return "string"
            if node.name == "slice" and node.arguments: return self._infer_type(node.arguments[0])
            return "unknown"
        if isinstance(node, IndexExpr):
            return "string" if self._infer_type(node.object) == "string" else "unknown"
        return "unknown"

    def _types_compatible(self, declared: str, actual: str) -> bool:
        if declared in ("var", "unknown") or actual == "unknown": return True
        if declared == "int" and actual == "number": return True
        if declared == "number" and actual == "int": return True
        return declared == actual

    def _collect_declarations(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, FuncDecl):
                self._functions[stmt.name] = Simbolo(stmt.name, "FUNC", stmt.line, parametros=list(stmt.params))
            elif isinstance(stmt, ClassDecl):
                attrs = {a.name: a.type for a in stmt.attributes}
                self._class_attr_decls[stmt.name] = {a.name: a for a in stmt.attributes}
                methods = {m.name: m.params for m in stmt.methods}
                self._classes[stmt.name] = Simbolo(stmt.name, "CLASS", stmt.line, atributos=attrs, metodos=methods)

    def validate_node(self, node: ASTNode) -> None:
        if node is None: return

        if isinstance(node, VarDecl):
            self.validate_node(node.init_value)
            actual_type = self._infer_type(node.init_value)
            declared_type = actual_type if node.type == "var" and actual_type != "unknown" else node.type
            if not self._types_compatible(declared_type, actual_type):
                self._report(node.line, f"Tipo incompativel em '{node.name}': esperado {declared_type}, recebido {actual_type}.")
            self._define_symbol(node.name, declared_type, node.line)
            sym = self._lookup(node.name)
            if sym is not None and sym.declaracao is None:
                sym.declaracao = node
                sym.tipo_numerico = "float" if node.promover_double else self._numeric_kind(node.init_value)
        elif isinstance(node, Assignment):
            sym = self._lookup(node.name)
            if sym is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
            self.validate_node(node.value)
            if sym is not None:
                self._promover(sym.declaracao, node.value)
            if sym and not self._types_compatible(sym.tipo, self._infer_type(node.value)):
                self._report(node.line, f"Tipo incompativel em atribuicao de '{node.name}'.")
        elif isinstance(node, PrintStmt):
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, SendStmt):
            self.validate_node(node.channel)
            self.validate_node(node.message)
        elif isinstance(node, CChannelExpr):
            self.validate_node(node.ip)
            self.validate_node(node.port)
        elif isinstance(node, ReceiveExpr):
            self.validate_node(node.channel)
        elif isinstance(node, ListLiteral):
            for e in node.elements: self.validate_node(e)
            if node.tipo_elemento is None and node.elements:
                node.tipo_elemento = self._tipo_elementos(node.elements)
        elif isinstance(node, MatrixCreateExpr):
            self.validate_node(node.rows)
            self.validate_node(node.cols)
            self.validate_node(node.init_value)
        elif isinstance(node, IndexExpr):
            self.validate_node(node.object)
            self.validate_node(node.index)
        elif isinstance(node, IndexAssign):
            self.validate_node(node.target)
            self.validate_node(node.value)
            if isinstance(node.target, IndexExpr):
                self._registrar_elemento(node.target.object, node.value)
        elif isinstance(node, IdentifierExpr):
            if self._lookup(node.name) is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
        elif isinstance(node, BinaryExpr):
            self.validate_node(node.left)
            self.validate_node(node.right)
            if node.op in ("+", "-", "*", "/", "//", "%", "&", "|", "^", "<<", ">>"):
                lt, rt = self._infer_type(node.left), self._infer_type(node.right)
                if node.op != "+" and (lt not in ("number", "int", "var", "unknown") or rt not in ("number", "int", "var", "unknown")):
                    self._report(node.line, f"Operador '{node.op}' exige operandos numericos.")
        elif isinstance(node, UnaryExpr):
            self.validate_node(node.operand)
        elif isinstance(node, (SeqBlock, ParBlock)):
            self._enter_scope("bloco par" if isinstance(node, ParBlock) else "bloco seq")
            for stmt in node.statements: self.validate_node(stmt)
            self._exit_scope()
        elif isinstance(node, IfStmt):
            self.validate_node(node.condition)
            self.validate_node(node.then_branch)
            if node.else_branch: self.validate_node(node.else_branch)
        elif isinstance(node, WhileStmt):
            self.validate_node(node.condition)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
        elif isinstance(node, DoWhileStmt):
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self.validate_node(node.condition)
        elif isinstance(node, ForStmt):
            self._enter_scope("for")
            if node.iterator_name:
                self.validate_node(node.iterable)
                self._define_symbol(node.iterator_name, "var", node.line)
            else:
                self.validate_node(node.initializer)
                self.validate_node(node.condition)
                self.validate_node(node.increment)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self._exit_scope()
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                self._report(node.line, f"'{node.__class__.__name__.replace('Stmt', '').lower()}' usado fora de laco.")
        elif isinstance(node, ClassDecl):
            if node.superclass and node.superclass not in self._classes:
                self._report(node.line, f"Superclasse '{node.superclass}' nao declarada.")
            self._define_symbol(node.name, "CLASS", node.line)
            self._enter_scope(f"classe {node.name}")
            old_class = self._current_class
            self._current_class = node.name
            for attr in node.attributes: self.validate_node(attr)
            for method in node.methods: self.validate_node(method)
            self._current_class = old_class
            self._exit_scope()
        elif isinstance(node, FuncDecl):
            self._define_symbol(node.name, "FUNC", node.line, node.params)
            if self._current_class:
                self._enter_scope(f"metodo {self._current_class}.{node.name}")
            else:
                self._enter_scope(f"funcao {node.name}")
            old_function = self._current_function
            self._current_function = node.name
            reais = self._params_reais.get((self._current_class, node.name), set())
            for i, p in enumerate(node.params):
                self._define_symbol(p, "var", node.line)
                sym = self._lookup(p)
                if sym is not None and i in reais:
                    sym.tipo_numerico = "float"
            self.validate_node(node.body)
            self._current_function = old_function
            self._exit_scope()
        elif isinstance(node, ReturnStmt):
            if node.value: self.validate_node(node.value)
        elif isinstance(node, MethodCall):
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.method_name not in cls.metodos:
                self._report(node.line, f"Metodo '{node.method_name}' nao declarado em '{obj_type}'.")
            elif cls and len(cls.metodos[node.method_name]) != len(node.arguments):
                self._report(node.line, f"Metodo '{node.method_name}' espera {len(cls.metodos[node.method_name])} argumento(s), recebeu {len(node.arguments)}.")
            self.validate_node(node.object)
            for arg in node.arguments: self.validate_node(arg)
            if cls:
                self._registrar_args_reais(obj_type, node.method_name, node.arguments)
            if node.method_name in ("append", "push_back") and len(node.arguments) == 1:
                self._registrar_elemento(node.object, node.arguments[0])
        elif isinstance(node, FuncCallExpr):
            if node.name not in self._functions and node.name not in self.FUNCOES_NATIVAS:
                self._report(node.line, f"Funcao '{node.name}' nao declarada.")
            elif node.name in self._functions and len(self._functions[node.name].parametros) != len(node.arguments):
                self._report(node.line, f"Funcao '{node.name}' espera {len(self._functions[node.name].parametros)} argumento(s), recebeu {len(node.arguments)}.")
            for arg in node.arguments: self.validate_node(arg)
            if node.name in self._functions:
                self._registrar_args_reais(None, node.name, node.arguments)
        elif isinstance(node, PropertyAccess):
            self.validate_node(node.object)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name not in cls.atributos:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
        elif isinstance(node, PropertyAssign):
            self.validate_node(node.object)
            self.validate_node(node.value)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and node.property_name not in cls.atributos:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
            self._promover(self._attr_decl(node.object, node.property_name), node.value)
        elif isinstance(node, NewExpr):
            if node.class_name not in self._classes:
                self._report(node.line, f"Classe '{node.class_name}' nao declarada.")
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, ThisExpr):
            pass
        elif isinstance(node, InputExpr):
            if node.prompt: self.validate_node(node.prompt)

    def analyze(self, program: Program) -> bool:
        # A promocao int -> double pode se propagar: em "y = x * 2", y so vira real
        # depois que x foi promovido. Por isso a analise roda em rodadas ate que nenhuma
        # nova promocao aconteca (as marcacoes ficam gravadas nos nos VarDecl da AST).
        for _ in range(self.MAX_RODADAS):
            self._nova_rodada()
            self._collect_declarations(program)
            for stmt in program.statements: self.validate_node(stmt)
            if self._promocoes == 0:
                break
        return not self.erros

    MAX_RODADAS = 6

    def _nova_rodada(self) -> None:
        self._tabela = self._tabela.__class__()
        self.erros = []
        self._current_function = None
        self._current_class = None
        self._classes = {}
        self._functions = {}
        self._class_attr_decls = {}
        self._loop_depth = 0
        self._promocoes = 0

    FUNCOES_NATIVAS = ("exp", "random", "range", "len", "to_number", "parse_ints", "slice", "join_str")

    # ---- Tipos das listas (elemento C++) ----
    def _lista_declarada(self, obj: ASTNode) -> Optional[ListLiteral]:
        """Literal de lista que inicializou a variavel/atributo 'obj', se houver."""
        decl = None
        if isinstance(obj, IdentifierExpr):
            sym = self._lookup(obj.name)
            decl = sym.declaracao if sym else None
        elif isinstance(obj, PropertyAccess):
            decl = self._attr_decl(obj.object, obj.property_name)
        if decl is not None and isinstance(decl.init_value, ListLiteral):
            return decl.init_value
        return None

    def _tipo_cpp(self, node: ASTNode) -> Optional[str]:
        """Tipo C++ de um valor, quando o semantico consegue determinar."""
        tipo = self._infer_type(node)
        if tipo == "string": return "std::string"
        if tipo == "bool": return "bool"
        kind = self._numeric_kind(node)
        if kind == "int": return "long long"
        if kind == "float": return "double"
        if tipo in self._classes: return f"std::shared_ptr<{tipo}>"
        if isinstance(node, ListLiteral) and node.tipo_elemento:
            return f"std::vector<{node.tipo_elemento}>"
        return None

    def _tipo_elementos(self, elementos: List[ASTNode]) -> Optional[str]:
        tipos = [self._tipo_cpp(e) for e in elementos]
        if all(t == "long long" for t in tipos): return "long long"
        if all(t in ("long long", "double") for t in tipos): return "double"
        if all(t == tipos[0] for t in tipos): return tipos[0]
        return None   # o C++ deduz o tipo comum dos elementos

    def _registrar_elemento(self, lista: ASTNode, valor: ASTNode) -> None:
        """Ajusta o tipo dos elementos de uma lista ao receber 'valor' (indice ou append)."""
        lit = self._lista_declarada(lista)
        if lit is None:
            return
        if lit.tipo_elemento is None and not lit.elements:
            tipo = self._tipo_cpp(valor)          # lista vazia: tipo do primeiro elemento
            if tipo:
                lit.tipo_elemento = tipo
                self._promocoes += 1
        elif lit.tipo_elemento == "long long" and self._numeric_kind(valor) != "int":
            # Na duvida (valor real ou desconhecido), a lista numerica vira de reais,
            # como era no MiniPar 2026.1 (toda lista era vector<double>).
            lit.tipo_elemento = "double"
            self._promocoes += 1

    # ---- Inferencia numerica (int x float), para escolher o tipo C++ ----
    FUNCOES_REAIS = ("exp", "random", "clock", "to_number")
    FUNCOES_INTEIRAS = ("len", "to_int")

    def _numeric_kind(self, node: Optional[ASTNode]) -> Optional[str]:
        """Retorna "int", "float" ou None (nao numerico ou desconhecido)."""
        if isinstance(node, NumberExpr):
            return "float" if "." in node.value else "int"
        if isinstance(node, UnaryExpr) and node.op in ("-", "+"):
            return self._numeric_kind(node.operand)
        if isinstance(node, BinaryExpr):
            if node.op == "/":
                return "float"                      # divisao real, como no Python 3
            if node.op in ("&", "|", "^", "<<", ">>"):
                return "int"
            if node.op in ("+", "-", "*", "//", "%"):
                lk, rk = self._numeric_kind(node.left), self._numeric_kind(node.right)
                if "float" in (lk, rk): return "float"
                if lk == "int" and rk == "int": return "int"
            return None
        if isinstance(node, IdentifierExpr):
            sym = self._lookup(node.name)
            return sym.tipo_numerico if sym else None
        if isinstance(node, PropertyAccess):
            decl = self._attr_decl(node.object, node.property_name)
            if decl is not None:
                return "float" if decl.promover_double else self._numeric_kind(decl.init_value)
            return None
        if isinstance(node, FuncCallExpr):
            if node.name in self.FUNCOES_REAIS: return "float"
            if node.name in self.FUNCOES_INTEIRAS: return "int"
        if isinstance(node, IndexExpr):
            lit = self._lista_declarada(node.object)
            if lit is not None:
                return {"long long": "int", "double": "float"}.get(lit.tipo_elemento)
        return None

    def _attr_decl(self, obj: ASTNode, attr: str) -> Optional[VarDecl]:
        cls_name = self._infer_type(obj)
        return self._class_attr_decls.get(cls_name, {}).get(attr)

    def _registrar_args_reais(self, classe: Optional[str], funcao: str, argumentos: List[ASTNode]) -> None:
        """Se uma chamada passa um valor real, o parametro correspondente e real."""
        reais = self._params_reais.setdefault((classe, funcao), set())
        for i, arg in enumerate(argumentos):
            if i not in reais and self._numeric_kind(arg) == "float":
                reais.add(i)
                self._promocoes += 1

    def _promover(self, decl: Optional[VarDecl], valor: ASTNode) -> None:
        """Marca a declaracao como double se ela recebe um valor real."""
        if decl is None or decl.promover_double:
            return
        if self._numeric_kind(valor) == "float":
            decl.promover_double = True
            self._promocoes += 1
