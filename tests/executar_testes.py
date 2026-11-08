"""
Executa todos os testes automatizados do MiniPar 2026.2 e gera a tabela de
resultados para o relatorio (tests/resultados/RESULTADOS.md).

Uso (na raiz do projeto; o run_tests.sh faz isso):
    .venv/bin/python tests/executar_testes.py                 # todos os testes
    .venv/bin/python tests/executar_testes.py --rapido        # sem integracao e sem API (nao chama o g++)
    .venv/bin/python tests/executar_testes.py --saida arq.md  # outro arquivo de relatorio

Codigo de saida: 0 se todos passarem, 1 caso contrario.
"""
import argparse
import os
import platform
import subprocess
import sys
import time
import unittest
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA)
for sub in ("unitarios", "integracao"):
    sys.path.insert(0, os.path.join(PASTA, sub))

# (modulo, componente testado, tipo)
SUITES = [
    ("test_lexico", "C_Lexico (analise lexica)", "Unidade"),
    ("test_sintatico", "C_Sintatico (analise sintatica / AST)", "Unidade"),
    ("test_semantico", "C_Semantico + C_TabelaSimbolos", "Unidade"),
    ("test_tac", "C_GeradorTAC (codigo de 3 enderecos)", "Unidade"),
    ("test_cpp", "C_GeradorCpp + C_CompiladorGcc", "Unidade"),
    ("test_controle", "C_Controle (integracao dos componentes)", "Integracao"),
    ("test_api_v2", "API v2 (rotas por fase)", "API"),
    ("test_programas", "Programas de teste (ponta a ponta)", "Integracao"),
]
LENTAS = {"test_api_v2", "test_programas"}


class ResultadoComTempo(unittest.TextTestResult):
    """Registra situacao e duracao de cada teste."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registros = []
        self._inicio = 0.0

    def startTest(self, test):
        self._inicio = time.perf_counter()
        super().startTest(test)

    def _registrar(self, test, situacao, detalhe=""):
        self.registros.append({
            "modulo": type(test).__module__, "teste": test.id().split(".", 1)[-1],
            "situacao": situacao, "segundos": time.perf_counter() - self._inicio, "detalhe": detalhe})

    def addSuccess(self, test):
        super().addSuccess(test)
        self._registrar(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._registrar(test, "falhou", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        # Erro em setUpClass chega com um _ErrorHolder, sem modulo de teste
        self._registrar(test, "erro", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._registrar(test, "ignorado", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._registrar(test, "ok")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._registrar(test, "falhou", "sucesso inesperado")


def versao_gpp():
    try:
        return subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "g++ nao encontrado"


def modulo_do_registro(r):
    modulo = r["modulo"]
    if modulo in dict((s[0], s) for s in SUITES):
        return modulo
    # _ErrorHolder (falha em setUpClass): o modulo aparece no id do teste
    for nome, *_ in SUITES:
        if nome in r["teste"]:
            return nome
    return modulo


def gerar_relatorio(registros, suites, duracao, caminho):
    por_modulo = {}
    for r in registros:
        por_modulo.setdefault(modulo_do_registro(r), []).append(r)

    linhas = [
        "# Resultados dos Testes Automatizados - MiniPar 2026.2",
        "",
        f"- Data: {datetime.now():%d/%m/%Y %H:%M}",
        f"- Sistema: {platform.system()} {platform.release()} | {os.cpu_count()} nucleos logicos",
        f"- Python {platform.python_version()} | {versao_gpp()}",
        f"- Duracao total: {duracao:.1f} s",
        "",
        "## Resumo por componente",
        "",
        "| Tipo | Componente | Arquivo | Testes | Passaram | Falharam | Ignorados | Tempo (s) |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    totais = [0, 0, 0, 0]
    for modulo, componente, tipo in suites:
        rs = por_modulo.get(modulo, [])
        ok = sum(r["situacao"] == "ok" for r in rs)
        falhas = sum(r["situacao"] in ("falhou", "erro") for r in rs)
        ignorados = sum(r["situacao"] == "ignorado" for r in rs)
        tempo = sum(r["segundos"] for r in rs)
        for i, v in enumerate((len(rs), ok, falhas, ignorados)):
            totais[i] += v
        pasta = "integracao" if modulo == "test_programas" else "unitarios"
        linhas.append(f"| {tipo} | {componente} | `tests/{pasta}/{modulo}.py` | {len(rs)} | {ok} | "
                      f"{falhas} | {ignorados} | {tempo:.1f} |")
    linhas.append(f"| | **Total** | | **{totais[0]}** | **{totais[1]}** | **{totais[2]}** | "
                  f"**{totais[3]}** | **{duracao:.1f}** |")

    if any(s[0] == "test_programas" for s in suites):
        from test_programas import RELATORIO
        situacao_teste = {}
        for r in por_modulo.get("test_programas", []):
            situacao_teste.setdefault(r["teste"].split(".")[-1], r["situacao"])
        linhas += [
            "",
            "## Programas MiniPar (compilacao e execucao)",
            "",
            "| Programa | Compila | Compilacao (s) | Execucao (s) | Avisos | Resultado |",
            "|---|:---:|---:|---:|---:|:---:|",
        ]
        for nome, info in RELATORIO.items():
            testes = [s for t, s in situacao_teste.items() if _teste_do_programa(t, nome)]
            if not info["compilou"] or any(s in ("falhou", "erro") for s in testes):
                resultado = "❌"
            elif testes and all(s == "ignorado" for s in testes):
                resultado = "ignorado"
            else:
                resultado = "✅"
            execucao = f"{info['execucao_s']:.2f}" if info["execucao_s"] is not None else "-"
            linhas.append(f"| `{nome}` | {'✅' if info['compilou'] else '❌'} | {info['compilacao_s']:.1f} | "
                          f"{execucao} | {info['avisos']} | {resultado} |")
        linhas += ["", "Compilacao: todas as fases (lexico ate g++ -O3), com ate 4 programas compilados "
                       "em paralelo antes dos testes (esse tempo nao entra na coluna Tempo do resumo). "
                       "Os testes com `on host` iniciam o mesmo executavel em modo `--worker 5400` em "
                       "localhost, fazendo o papel do outro computador."]

    falhas = [r for r in registros if r["situacao"] in ("falhou", "erro")]
    if falhas:
        linhas += ["", "## Falhas", ""]
        for r in falhas:
            linhas += [f"### {r['teste']}", "", "```", r["detalhe"].strip(), "```", ""]

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# nome do metodo de teste -> trecho do nome do programa que ele exercita
_MAPA = {
    "test_01_": "teste1_", "test_02_": "teste2_", "test_03_": "teste3_", "test_04_": "teste4_",
    "test_05_": "teste5_", "test_06_": "teste6_", "test_07_": "teste7_",
    "test_08_avaliacao": "teste8_avaliacao", "test_08_remoto": "teste8_remoto",
    "test_09_": "teste9_", "test_10_": "teste10_", "test_adicional1": "teste_adicional1",
    "test_adicional2": "teste_adicional2", "test_ascii": "teste_ascii", "test_bnf": "teste_bnf",
    "test_recurso_numeros": "recurso_numeros", "test_recurso_saida": "recurso_saida",
    "test_recurso_strings": "recurso_strings", "test_recurso_globais": "recurso_globais",
    "test_recurso_fork_join": "recurso_fork_join", "test_fork_remoto": "recurso_fork_remoto",
}


def _teste_do_programa(metodo, programa):
    return any(metodo.startswith(m) and programa.startswith(p) for m, p in _MAPA.items())


def main():
    args = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    args.add_argument("--rapido", action="store_true", help="pula integracao e API (sem g++)")
    args.add_argument("--saida", default=os.path.join(PASTA, "resultados", "RESULTADOS.md"))
    args.add_argument("-q", "--quieto", action="store_true", help="nao lista cada teste")
    opcoes = args.parse_args()

    os.chdir(RAIZ)
    suites = [s for s in SUITES if not (opcoes.rapido and s[0] in LENTAS)]
    carregador = unittest.TestLoader()
    tudo = unittest.TestSuite(carregador.loadTestsFromName(m) for m, *_ in suites)

    inicio = time.perf_counter()
    executor = unittest.TextTestRunner(resultclass=ResultadoComTempo, verbosity=1 if opcoes.quieto else 2)
    resultado = executor.run(tudo)
    duracao = time.perf_counter() - inicio

    gerar_relatorio(resultado.registros, suites, duracao, opcoes.saida)
    print(f"\nTabela de resultados: {os.path.relpath(opcoes.saida, RAIZ)}")
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
