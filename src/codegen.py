from __future__ import annotations
import dataclasses
import hashlib
from typing import List, Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr, 
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign,
    ForkStmt, JoinStmt, JoinExpr
)
from cpp_template import _CPP_HEADER
from interfaces import IGeradorCpp


class C_GeradorCpp(IGeradorCpp):
    """Componente Gerador de Codigo C++ - implementa IGeradorCpp.

    Traduz a AST validada para C++20: classes MiniPar viram classes C++ com
    std::shared_ptr, blocos par viram std::thread com join, e c_channel usa
    a classe MiniParChannel (sockets TCP) definida em cpp_template.py.
    Apenas GERA o texto; a compilacao fica no componente C_CompiladorGcc.
    """

    @staticmethod
    def _escape_string(value: str) -> str:
        res = []
        for ch in value:
            if ch == "\n": res.append("\\n")
            elif ch == "\t": res.append("\\t")
            elif ch == '"': res.append('\\"')
            elif ch == "\\": res.append("\\\\")
            else: res.append(ch)
        return "".join(res)

    # Operadores com semantica do Python implementados por funcoes do template C++
    OPERADORES_FUNCAO = {"/": "__div", "//": "__floordiv", "%": "__mod"}
    OPERADORES_BIT = ("&", "|", "^", "<<", ">>")

    @staticmethod
    def _translate_number(value: str) -> str:
        """Inteiros viram long long (64 bits), evitando o estouro do int de 32 bits."""
        if value.lower().startswith("0x"):
            return f"{int(value, 16)}LL"
        if "." in value:
            return value
        return f"{value}LL"

    def _translate_expression(self, node: Optional[ASTNode]) -> str:
        if node is None: return "0"
        if isinstance(node, NumberExpr): return self._translate_number(node.value)
        # std::string (e nao const char*): permite concatenar, comparar e indexar
        if isinstance(node, StringExpr): return f'std::string("{self._escape_string(node.value)}")'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, UnaryExpr): return f"({node.op}{self._translate_expression(node.operand)})"
        if isinstance(node, BinaryExpr):
            left = self._translate_expression(node.left)
            right = self._translate_expression(node.right)
            if node.op in self.OPERADORES_FUNCAO:
                return f"{self.OPERADORES_FUNCAO[node.op]}({left}, {right})"
            if node.op in self.OPERADORES_BIT:
                return f"(__as_int({left}) {node.op} __as_int({right}))"
            if node.op == "+":
                return f"__add({left}, {right})"   # numeros, strings (com conversao) ou listas
            return f"({left} {node.op} {right})"
        
        if isinstance(node, NewExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            return f"std::make_shared<{node.class_name}>({args})"
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, PropertyAccess):
            if node.property_name == "size": return f"__len({self._translate_expression(node.object)})"
            return f"{self._translate_expression(node.object)}->{node.property_name}"
        
        if isinstance(node, MethodCall):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            m_name = node.method_name
            if m_name in ("append", "push_back"): return f"{self._translate_expression(node.object)}.push_back({args})"
            if m_name == "pop": return f"__array_pop({self._translate_expression(node.object)})"
            if m_name == "size": return f"__len({self._translate_expression(node.object)})"
            return f"{self._translate_expression(node.object)}->{m_name}({args})"
        
        if isinstance(node, FuncCallExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            if node.name == "exp":
                return f"std::exp({args})"
            if node.name == "random":
                return "random_val()"
            if node.name == "len":
                return f"__len({self._translate_expression(node.arguments[0])})"
            if node.name == "range":
                return f"__minipar_range({args})"
            if node.name == "to_number":
                return f"__to_number({args})"
            if node.name == "to_int":
                return f"__to_int({args})"
            if node.name == "str":
                return f"__str({args})"
            if node.name == "format":
                return f"__format({args})"
            if node.name == "write_file":
                return f"__write_file({args})"
            if node.name == "nucleo":
                return "__nucleo()"
            if node.name == "clock":
                return "__clock()"
            if node.name == "parse_ints":
                return f"__parse_ints({args})"
            if node.name == "slice":
                return f"__slice({args})"
            if node.name == "join_str":
                return f"__join_str({args})"
            return f"{node.name}({args})"

        if isinstance(node, CChannelExpr):
            ip = self._translate_expression(node.ip)
            port = self._translate_expression(node.port)
            return f"std::make_shared<MiniParChannel>({ip}, {port})"
        if isinstance(node, ReceiveExpr):
            return f"{self._translate_expression(node.channel)}->receiveData()"
        if isinstance(node, InputExpr):
            if node.prompt:
                return f"input({self._translate_expression(node.prompt)})"
            return "input()"
        if isinstance(node, JoinExpr):
            return f"{node.handle}.get()"      # espera a subtarefa e devolve o retorno

        if isinstance(node, ListLiteral):
            elems = ", ".join(self._translate_expression(e) for e in node.elements)
            if node.tipo_elemento:                       # tipo decidido pelo semantico
                return f"__lista_t<{node.tipo_elemento}>({elems})"
            if not node.elements:                        # lista vazia sem uso conhecido
                return "std::vector<double>{}"
            return f"__lista({elems})"                   # C++ deduz o tipo comum
        if isinstance(node, MatrixCreateExpr):
            r = self._translate_expression(node.rows)
            c = self._translate_expression(node.cols)
            v = self._translate_expression(node.init_value)
            if node.promover_double:
                v = f"static_cast<double>({v})"
            return f"__make_matrix({r}, {c}, {v})"
        if isinstance(node, IndexExpr):
            obj = self._translate_expression(node.object)
            idx = self._translate_expression(node.index)
            return f"__index({obj}, {idx})"   # leitura com verificacao de limites

        return "0"

    def _translate_index_target(self, target: ASTNode) -> str:
        """Destino de lista[i] = v: escrita alem do fim aumenta a lista (pilha que cresce)."""
        if isinstance(target, IndexExpr):
            obj = self._translate_expression(target.object)
            idx = self._translate_expression(target.index)
            return f"__index_set({obj}, {idx})"
        return self._translate_expression(target)

    @staticmethod
    def _nos(node) -> List[ASTNode]:
        """Todos os nos da AST abaixo de 'node' (percorre os campos das dataclasses)."""
        encontrados = []
        pilha = [node]
        while pilha:
            atual = pilha.pop()
            if isinstance(atual, list):
                pilha.extend(atual)
            elif isinstance(atual, ASTNode) and dataclasses.is_dataclass(atual):
                encontrados.append(atual)
                pilha.extend(getattr(atual, f.name) for f in dataclasses.fields(atual))
        return encontrados

    FUNCOES_PURAS = ("exp", "len", "range", "str", "format", "to_int", "to_number",
                     "slice", "join_str", "parse_ints")

    def _expressao_pura(self, expr: Optional[ASTNode]) -> bool:
        """Expressao sem efeitos colaterais (pode ser reavaliada no computador remoto)."""
        for no in self._nos(expr):
            if isinstance(no, FuncCallExpr) and no.name not in self.FUNCOES_PURAS:
                return False
            if isinstance(no, (MethodCall, InputExpr, ReceiveExpr, CChannelExpr, JoinExpr)):
                return False
        return True

    def _gerar_suporte_remoto(self, program: Program) -> str:
        """Funcoes usadas pelo modo trabalhador (--worker) para atender forks remotos."""
        # 0. Assinatura do programa: o trabalhador recusa pedidos de outra versao do programa
        #    (os forks remotos sao numerados; outra versao executaria a funcao errada)
        assinatura = hashlib.sha1(repr(program).encode("utf-8")).hexdigest()[:16]
        codigo = f'extern const char* const __ASSINATURA_PROGRAMA = "{assinatura}";\n\n'
        # 1. Globais tambem precisam ser inicializadas no computador remoto, mas apenas
        #    as de expressao pura (sem chamar funcoes do programa, input, receive...):
        #    "var t = execucao_sequencial();" nao pode rodar de novo no trabalhador
        #    e que so dependem de globais tambem inicializadas aqui (criterio transitivo:
        #    "speedup = tempo_seq / tempo_par" depende de valores calculados so no principal)
        codigo += "void __iniciar_globais() {\n"
        inicializadas = set()
        for node in program.statements:
            if self._global_tipada(node) and self._expressao_pura(node.init_value) and all(
                    no.name in inicializadas for no in self._nos(node.init_value)
                    if isinstance(no, IdentifierExpr)):
                inicializadas.add(node.name)
                expr = self._translate_expression(node.init_value) if node.init_value else "{}"
                codigo += f"    {node.name} = {expr};\n"
        codigo += "}\n\n"
        # 2. Tabela de subtarefas: reconstroi os argumentos e chama a funcao
        codigo += "std::string __executar_remoto(int id, __Leitor& l) {\n    switch (id) {\n"
        vistos = set()
        for fork in self._nos(program):
            if not isinstance(fork, ForkStmt) or fork.host is None or fork.id_remoto in vistos:
                continue
            vistos.add(fork.id_remoto)
            codigo += f"    case {fork.id_remoto}: {{\n"
            nomes = []
            for i, tipo in enumerate(fork.tipos_args):
                codigo += f"        auto a{i} = __des<{tipo}>(l);\n"
                nomes.append(f"a{i}")
            codigo += f"        return __resposta([&]() {{ return {fork.call.name}({', '.join(nomes)}); }});\n    }}\n"
        codigo += "    }\n    return \"E|subtarefa remota desconhecida\";\n}\n\n"
        return codigo

    @staticmethod
    def _global_tipada(node: ASTNode) -> bool:
        """Variavel do topo do programa com tipo conhecido: vira global no C++."""
        return (isinstance(node, VarDecl) and node.escopo_global
                and (node.promover_double or node.tipo_cpp is not None))

    @staticmethod
    def _decl_type(node: VarDecl) -> str:
        return "double" if node.promover_double else "auto"

    def _has_value_return(self, node: Optional[ASTNode]) -> bool:
        if node is None: return False
        if isinstance(node, ReturnStmt): return node.value is not None
        if isinstance(node, (SeqBlock, ParBlock)):
            return any(self._has_value_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._has_value_return(node.then_branch) or self._has_value_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt)):
            return self._has_value_return(node.body)
        return False

    def _uses_float_return(self, node: Optional[ASTNode]) -> bool:
        """Detecta aritmética de ponto flutuante no corpo da função."""
        if node is None:
            return False
        if isinstance(node, BinaryExpr):
            if node.op == "/":
                return True
            return self._uses_float_return(node.left) or self._uses_float_return(node.right)
        if isinstance(node, NumberExpr):
            return "." in node.value
        if isinstance(node, (SeqBlock, ParBlock)):
            return any(self._uses_float_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._uses_float_return(node.then_branch) or self._uses_float_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt)):
            return self._uses_float_return(node.body)
        if isinstance(node, ReturnStmt):
            return self._uses_float_return(node.value)
        return False

    def _return_type(self, func: FuncDecl) -> str:
        body = func.body
        if not self._has_value_return(body):
            return "void"
        # auto falha no g++ quando há return double e return 0 (int) na mesma função;
        # retorno_real vem do semantico (ex.: return de uma variavel promovida a double)
        if func.retorno_real or self._uses_float_return(body):
            return "double"
        return "auto"

    def _translate_statement(self, node: Optional[ASTNode], indent: str = "") -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            return f"{indent}{self._decl_type(node)} {node.name} = {expr};\n"
        if isinstance(node, Assignment):
            return f"{indent}{node.name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, PropertyAssign):
            obj = self._translate_expression(node.object)
            return f"{indent}{obj}->{node.property_name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, IndexAssign):
            tgt = self._translate_index_target(node.target)
            return f"{indent}{tgt} = {self._translate_expression(node.value)};\n"
        
        if isinstance(node, (MethodCall, FuncCallExpr)):
            return f"{indent}{self._translate_expression(node)};\n"
        if isinstance(node, ReturnStmt):
            val = self._translate_expression(node.value) if node.value else ""
            return f"{indent}return {val};\n"
        if isinstance(node, BreakStmt):
            return f"{indent}break;\n"
        if isinstance(node, ContinueStmt):
            return f"{indent}continue;\n"
        
        if isinstance(node, ForkStmt):
            # [=]: a subtarefa recebe copias dos argumentos (dados independentes)
            call = self._translate_expression(node.call)
            if node.host is not None:
                # Outro computador: envia id + argumentos e espera o resultado (tipo de retorno
                # obtido com decltype da propria chamada, sem executa-la localmente)
                host = self._translate_expression(node.host)
                porta = self._translate_expression(node.porta)
                args = "".join(", " + self._translate_expression(a) for a in node.call.arguments)
                remoto = f"__remoto<decltype({call})>({host}, {porta}, {node.id_remoto}{args})"
                return f"{indent}auto {node.handle} = __fork(-1LL, [=]() {{ return {remoto}; }});\n"
            core = self._translate_expression(node.core) if node.core is not None else "-1LL"
            return f"{indent}auto {node.handle} = __fork({core}, [=]() {{ return {call}; }});\n"
        if isinstance(node, JoinStmt):
            return "".join(f"{indent}{h}.wait();\n" for h in node.handles_resolvidos)
        if isinstance(node, SendStmt):
            chan = self._translate_expression(node.channel)
            msg = self._translate_expression(node.message)
            return f"{indent}{chan}->sendData(__to_string({msg}));\n"

        if isinstance(node, PrintStmt):
            # __print monta a linha no formato do Python e a escreve de uma vez (thread-safe)
            args = ", ".join(self._translate_expression(arg) for arg in node.arguments)
            return f"{indent}__print({args});\n"
        
        if isinstance(node, SeqBlock):
            lines = [f"{indent}{{\n"]
            for stmt in node.statements: lines.append(self._translate_statement(stmt, indent + "    "))
            lines.append(f"{indent}}}\n")
            return "".join(lines)
        if isinstance(node, ParBlock):
            lines = [f"{indent}{{\n", f"{indent}    std::vector<std::thread> __m_thr;\n"]
            for stmt in node.statements:
                lines.append(f"{indent}    __m_thr.emplace_back([&]() {{\n{self._translate_statement(stmt, indent + '        ')}{indent}    }});\n")
            lines.append(f"{indent}    for (auto& t : __m_thr) t.join();\n{indent}}}\n")
            return "".join(lines)
        if isinstance(node, WhileStmt):
            res = f"{indent}while ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, DoWhileStmt):
            res = f"{indent}do\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ").rstrip()
            res += f"\n{indent}while ({self._translate_expression(node.condition)});\n"
            return res
        if isinstance(node, ForStmt):
            if node.iterator_name and node.iterable:
                res = f"{indent}for (auto {node.iterator_name} : {self._translate_expression(node.iterable)})\n"
                res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
                return res
            init = self._translate_for_part(node.initializer)
            cond = self._translate_expression(node.condition) if node.condition else "true"
            inc = self._translate_for_part(node.increment)
            res = f"{indent}for ({init}; {cond}; {inc})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, IfStmt):
            res = f"{indent}if ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.then_branch, indent if isinstance(node.then_branch, (SeqBlock, ParBlock)) else indent + "    ")
            if node.else_branch:
                res = res.rstrip() + f"\n{indent}else\n"
                if isinstance(node.else_branch, IfStmt):
                    res = res.rstrip() + " " + self._translate_statement(node.else_branch, indent).lstrip()
                else:
                    res += self._translate_statement(node.else_branch, indent if isinstance(node.else_branch, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        return ""

    def _translate_for_part(self, node: Optional[ASTNode]) -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            return f"{self._decl_type(node)} {node.name} = {expr}"
        if isinstance(node, Assignment):
            return f"{node.name} = {self._translate_expression(node.value)}"
        if isinstance(node, PropertyAssign):
            return f"{self._translate_expression(node.object)}->{node.property_name} = {self._translate_expression(node.value)}"
        if isinstance(node, IndexAssign):
            return f"{self._translate_index_target(node.target)} = {self._translate_expression(node.value)}"
        return self._translate_expression(node)

    # ---- Interface IGeradorCpp ----
    def gerar(self, programa: Program) -> str:
        program = programa
        cpp_code = _CPP_HEADER

        # Declaracao antecipada das classes: globais e funcoes podem referencia-las
        for node in program.statements:
            if isinstance(node, ClassDecl):
                cpp_code += f"class {node.name};\n"

        # Variaveis globais (var no topo do programa): declaradas aqui, antes das classes
        # e funcoes que as usam, e inicializadas no main() na ordem original do programa
        # (globais de tipo desconhecido continuam locais do main(); o semantico impede
        #  que funcoes as usem)
        for node in program.statements:
            if self._global_tipada(node):
                cpp_code += f"{'double' if node.promover_double else node.tipo_cpp} {node.name};\n"
        cpp_code += "\n"

        for node in program.statements:
            if isinstance(node, ClassDecl):
                cpp_code += f"class {node.name}" + (f" : public {node.superclass}" if node.superclass else "") + " {\npublic:\n"
                for attr in node.attributes:
                    if attr.init_value:
                        init = self._translate_expression(attr.init_value)
                        tipo = "double" if attr.promover_double else f"decltype({init})"
                        cpp_code += f"    {tipo} {attr.name} = {init};\n"
                    else:
                        cpp_code += f"    double {attr.name} = 0;\n"
                for method in node.methods:
                    params = ", ".join(f"auto {p}" for p in method.params)
                    ret = self._return_type(method)
                    cpp_code += f"    {ret} {method.name}({params}) {{\n"
                    if isinstance(method.body, SeqBlock):
                        for stmt in method.body.statements: cpp_code += self._translate_statement(stmt, "        ")
                    else: cpp_code += self._translate_statement(method.body, "        ")
                    cpp_code += "    }\n"
                cpp_code += "};\n\n"
            elif isinstance(node, FuncDecl):
                params = ", ".join(f"auto {p}" for p in node.params)
                ret = self._return_type(node)
                cpp_code += f"{ret} {node.name}({params}) {{\n"
                if isinstance(node.body, SeqBlock):
                    for stmt in node.body.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node.body, "    ")
                cpp_code += "}\n\n"

        cpp_code += self._gerar_suporte_remoto(program)
        cpp_code += "int main(int argc, char** argv) {\n    #ifdef _WIN32\n        WSADATA wsa;\n        WSAStartup(MAKEWORD(2,2), &wsa);\n    #endif\n\n"
        # Modo trabalhador (fork remoto): ./programa --worker PORTA
        cpp_code += ("    if (argc >= 3 && std::string(argv[1]) == \"--worker\") {\n"
                     "        __iniciar_globais();\n"
                     "        __servir_remoto(std::atoll(argv[2]));\n"
                     "        return 0;\n    }\n\n")
        for node in program.statements:
            if self._global_tipada(node):
                expr = self._translate_expression(node.init_value) if node.init_value else "{}"
                cpp_code += f"    {node.name} = {expr};\n"
                continue
            if not isinstance(node, (ClassDecl, FuncDecl)):
                if isinstance(node, SeqBlock):
                    for stmt in node.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node, "    ")
        cpp_code += "\n    return 0;\n}\n"
        return cpp_code
