"""
Componente Compilador C++ (C_CompiladorGcc) - implementa ICompiladorCpp.

Recebe o codigo C++ produzido pelo Gerador de Codigo C++ e chama o g++
com otimizacao (-O3) para gerar o executavel nativo.

Separado do gerador de C++ para que cada componente tenha uma unica
responsabilidade: a interface didatica pode mostrar o C++ gerado sem
compilar, e trocar o compilador (ex.: clang++) nao afeta a geracao.
"""
from __future__ import annotations

import os
import subprocess
import sys

from erros import ErroGeracao
from interfaces import ICompiladorCpp

# Extensao do executavel gerado, conforme a plataforma (Windows: .exe; Linux/macOS: sem extensao)
EXE_EXT = ".exe" if sys.platform == "win32" else ""


class C_CompiladorGcc(ICompiladorCpp):
    def __init__(self, pasta_saida: str = "output") -> None:
        self.pasta_saida = pasta_saida

    def caminho_cpp(self, nome_saida: str) -> str:
        return os.path.join(self.pasta_saida, f"{nome_saida}.cpp")

    def caminho_executavel(self, nome_saida: str) -> str:
        return os.path.join(self.pasta_saida, f"{nome_saida}{EXE_EXT}")

    def compilar(self, codigo_cpp: str, nome_saida: str) -> str:
        os.makedirs(self.pasta_saida, exist_ok=True)
        cpp_path = self.caminho_cpp(nome_saida)
        exe_path = self.caminho_executavel(nome_saida)

        with open(cpp_path, "w", encoding="utf-8") as f:
            f.write(codigo_cpp)

        cmd = ["g++", "-std=c++20", "-O3", cpp_path, "-o", exe_path, "-pthread"]
        if sys.platform == "win32":
            cmd.append("-lws2_32")  # Winsock: necessario apenas no Windows

        try:
            resultado = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            raise ErroGeracao("g++ nao encontrado. Instale o GCC e garanta que ele esteja no PATH.")

        if resultado.returncode != 0:
            # Mostra so o inicio da saida do g++ (erros de template costumam ser enormes)
            detalhes = "\n".join(resultado.stderr.strip().splitlines()[:15])
            raise ErroGeracao(f"Falha ao compilar o C++ gerado com g++:\n{detalhes}")
        return exe_path
