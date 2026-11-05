from __future__ import annotations
import os
import subprocess
import sys
from typing import Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr, 
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)
from cpp_template import _CPP_HEADER

# Extensao do executavel gerado, conforme a plataforma (Windows: .exe; Linux/macOS: sem extensao)
EXE_EXT = ".exe" if sys.platform == "win32" else ""

class CppCodeGenerator:
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

    def _translate_expression(self, node: Optional[ASTNode]) -> str:
        if node is None: return "0"
        if isinstance(node, NumberExpr): return node.value
        if isinstance(node, StringExpr): return f'"{self._escape_string(node.value)}"'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, UnaryExpr): return f"({node.op}{self._translate_expression(node.operand)})"
        if isinstance(node, BinaryExpr):
            return f"({self._translate_expression(node.left)} {node.op} {self._translate_expression(node.right)})"
        
        if isinstance(node, NewExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            return f"std::make_shared<{node.class_name}>({args})"
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, PropertyAccess):
            if node.property_name == "size": return f"{self._translate_expression(node.object)}.size()"
            return f"{self._translate_expression(node.object)}->{node.property_name}"
        
        if isinstance(node, MethodCall):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            m_name = node.method_name
            if m_name in ("append", "push_back"): return f"{self._translate_expression(node.object)}.push_back({args})"
            if m_name == "pop": return f"__array_pop({self._translate_expression(node.object)})"
            if m_name == "size": return f"{self._translate_expression(node.object)}.size()"
            return f"{self._translate_expression(node.object)}->{m_name}({args})"
        
        if isinstance(node, FuncCallExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            if node.name == "exp":
                return f"std::exp({args})"
            if node.name == "random":
                return "random_val()"
            if node.name == "len":
                return f"{self._translate_expression(node.arguments[0])}.size()"
            if node.name == "range":
                return f"__minipar_range({args})"
            if node.name == "to_number":
                return f"std::stod({args})"
            if node.name == "parse_ints":
                return f"__parse_ints({args})"
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

        if isinstance(node, ListLiteral):
            elems = ", ".join(self._translate_expression(e) for e in node.elements)
            return f"std::vector<double>{{{elems}}}"
        if isinstance(node, MatrixCreateExpr):
            r = self._translate_expression(node.rows)
            c = self._translate_expression(node.cols)
            v = self._translate_expression(node.init_value)
            return f"__make_matrix({r}, {c}, {v})"
        if isinstance(node, IndexExpr):
            obj = self._translate_expression(node.object)
            idx = self._translate_expression(node.index)
            return f"{obj}[{idx}]"

        return "0"

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

    def _return_type(self, body: Optional[ASTNode]) -> str:
        if not self._has_value_return(body):
            return "void"
        # auto falha no g++ quando há return double e return 0 (int) na mesma função
        if self._uses_float_return(body):
            return "double"
        return "auto"

    def _translate_statement(self, node: Optional[ASTNode], indent: str = "") -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            return f"{indent}auto {node.name} = {expr};\n"
        if isinstance(node, Assignment):
            return f"{indent}{node.name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, PropertyAssign):
            obj = self._translate_expression(node.object)
            return f"{indent}{obj}->{node.property_name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, IndexAssign):
            tgt = self._translate_expression(node.target)
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
        
        if isinstance(node, SendStmt):
            chan = self._translate_expression(node.channel)
            msg = self._translate_expression(node.message)
            return f"{indent}{chan}->sendData(__to_string({msg}));\n"

        if isinstance(node, PrintStmt):
            parts = []
            for i, arg in enumerate(node.arguments):
                if i > 0:
                    parts.append(' << " "')
                parts.append(f" << {self._translate_expression(arg)}")
            return f"{indent}std::cout{ ''.join(parts) } << std::endl;\n"
        
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
            return f"auto {node.name} = {expr}"
        if isinstance(node, Assignment):
            return f"{node.name} = {self._translate_expression(node.value)}"
        if isinstance(node, PropertyAssign):
            return f"{self._translate_expression(node.object)}->{node.property_name} = {self._translate_expression(node.value)}"
        if isinstance(node, IndexAssign):
            return f"{self._translate_expression(node.target)} = {self._translate_expression(node.value)}"
        return self._translate_expression(node)

    def generate(self, program: Program, output_name: str) -> bool:
        cpp_code = _CPP_HEADER
        
        for node in program.statements:
            if isinstance(node, ClassDecl):
                cpp_code += f"class {node.name}" + (f" : public {node.superclass}" if node.superclass else "") + " {\npublic:\n"
                for attr in node.attributes:
                    if attr.init_value:
                        init = self._translate_expression(attr.init_value)
                        cpp_code += f"    decltype({init}) {attr.name} = {init};\n"
                    else:
                        cpp_code += f"    double {attr.name} = 0;\n"
                for method in node.methods:
                    params = ", ".join(f"auto {p}" for p in method.params)
                    ret = self._return_type(method.body)
                    cpp_code += f"    {ret} {method.name}({params}) {{\n"
                    if isinstance(method.body, SeqBlock):
                        for stmt in method.body.statements: cpp_code += self._translate_statement(stmt, "        ")
                    else: cpp_code += self._translate_statement(method.body, "        ")
                    cpp_code += "    }\n"
                cpp_code += "};\n\n"
            elif isinstance(node, FuncDecl):
                params = ", ".join(f"auto {p}" for p in node.params)
                ret = self._return_type(node.body)
                cpp_code += f"{ret} {node.name}({params}) {{\n"
                if isinstance(node.body, SeqBlock):
                    for stmt in node.body.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node.body, "    ")
                cpp_code += "}\n\n"

        cpp_code += "int main() {\n    #ifdef _WIN32\n        WSADATA wsa;\n        WSAStartup(MAKEWORD(2,2), &wsa);\n    #endif\n\n"
        for node in program.statements:
            if not isinstance(node, (ClassDecl, FuncDecl)):
                if isinstance(node, SeqBlock):
                    for stmt in node.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node, "    ")
        cpp_code += "\n    return 0;\n}\n"

        os.makedirs("output", exist_ok=True)
        cpp_path = os.path.join("output", f"{output_name}.cpp")
        exe_path = os.path.join("output", f"{output_name}{EXE_EXT}")

        with open(cpp_path, "w", encoding="utf-8") as f: f.write(cpp_code)

        print("[CODEGEN] Compilando via g++ com -std=c++20 e -O3...")
        cmd = ["g++", "-std=c++20", "-O3", cpp_path, "-o", exe_path, "-pthread"]
        if sys.platform == "win32":
            cmd.append("-lws2_32")  # Winsock: necessario apenas no Windows
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"[SUCESSO] Executavel: {exe_path}")
            return True
        print("[ERRO] Falha na compilacao.", file=sys.stderr)
        return False
