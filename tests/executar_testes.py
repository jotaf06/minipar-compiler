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
import re
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


def identificar(test):
    """(modulo, nome) de um teste. Erros de setUpClass/setUpModule chegam como um
    _ErrorHolder, cujo id e "setUpClass (test_programas.TestProgramas)"."""
    if isinstance(test, unittest.TestCase):
        modulo = type(test).__module__
        return modulo, test.id()[len(modulo) + 1:]
    descricao = test.id()
    achado = re.search(r"\((\w+)[.)]", descricao)
    return (achado.group(1) if achado else "?"), descricao


class ResultadoComTempo(unittest.TextTestResult):
    """Registra situacao e duracao de cada teste."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registros = []
        self._inicio = 0.0

    def startTest(self, test):
        self._inicio = time.perf_counter()
        super().startTest(test)

    def _registrar(self, test, situacao, detalhe="", nome=None):
        modulo, teste = identificar(test)
        self.registros.append({
            "modulo": modulo, "teste": nome or teste, "metodo": getattr(test, "_testMethodName", ""),
            "situacao": situacao, "segundos": time.perf_counter() - self._inicio, "detalhe": detalhe})

    def addSuccess(self, test):
        super().addSuccess(test)
        self._registrar(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._registrar(test, "falhou", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._registrar(test, "erro", self._exc_info_to_string(err, test))

    def addSubTest(self, test, subtest, err):
        # Subteste que falha nao passa por addFailure/addError, e o teste "pai" nao
        # recebe addSuccess: cada subteste com falha vira um registro proprio
        super().addSubTest(test, subtest, err)
        if err is not None:
            situacao = "falhou" if issubclass(err[0], test.failureException) else "erro"
            self._registrar(test, situacao, self._exc_info_to_string(err, test),
                            nome=identificar(test)[1] + " " + subtest._subDescription())

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._registrar(test, "ignorado", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._registrar(test, "ok")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._registrar(test, "falhou", "sucesso inesperado")


def nucleos_disponiveis():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def versao_gpp():
    try:
        return subprocess.run(["g++", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "g++ nao encontrado"


def situacao_do_programa(info, situacao_metodo):
    """Resultado de um programa a partir dos testes que o executaram."""
    if not info["compilou"]:
        return "❌"
    situacoes = [situacao_metodo[m] for m in info["testes"] if m in situacao_metodo]
    if not situacoes:
        return "⚠️ nao testado"
    if any(s in ("falhou", "erro") for s in situacoes):
        return "❌"
    if all(s == "ignorado" for s in situacoes):
        return "ignorado"
    return "✅"


def gerar_relatorio(registros, suites, duracao, caminho):
    por_modulo = {}
    for r in registros:
        por_modulo.setdefault(r["modulo"], []).append(r)

    linhas = [
        "# Resultados dos Testes Automatizados - MiniPar 2026.2",
        "",
        f"- Data: {datetime.now():%d/%m/%Y %H:%M}",
        f"- Sistema: {platform.system()} {platform.release()} | {os.cpu_count()} nucleos logicos"
        f" ({nucleos_disponiveis()} disponiveis para os testes)",
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
        situacao_metodo = {}
        for r in por_modulo.get("test_programas", []):
            if not r["metodo"]:
                continue
            # Uma falha (inclusive de subteste) prevalece sobre o registro de sucesso
            if situacao_metodo.get(r["metodo"]) not in ("falhou", "erro"):
                situacao_metodo[r["metodo"]] = r["situacao"]
        linhas += [
            "",
            "## Programas MiniPar (compilacao e execucao)",
            "",
            "| Programa | Compila | Compilacao (s) | Execucao (s) | Avisos | Resultado |",
            "|---|:---:|---:|---:|---:|:---:|",
        ]
        for nome, info in RELATORIO.items():
            resultado = situacao_do_programa(info, situacao_metodo)
            execucao = f"{info['execucao_s']:.2f}" if info["execucao_s"] is not None else "-"
            linhas.append(f"| `{nome}` | {'✅' if info['compilou'] else '❌'} | {info['compilacao_s']:.1f} | "
                          f"{execucao} | {info['avisos']} | {resultado} |")
        linhas += ["", "Compilacao: todas as fases (lexico ate g++ -O3), com ate 4 programas compilados "
                       "em paralelo antes dos testes (esse tempo nao entra na coluna Tempo do resumo). "
                       "Os testes com `on host` iniciam o mesmo executavel em modo `--worker 5400` em "
                       "localhost, fazendo o papel do outro computador."]

    modulos = {m for m, *_ in suites}
    fora = [r for r in registros if r["modulo"] not in modulos]
    if fora:
        linhas += ["", f"**Atencao:** {len(fora)} resultado(s) fora dos modulos listados acima."]

    falhas = [r for r in registros if r["situacao"] in ("falhou", "erro")]
    if falhas:
        linhas += ["", "## Falhas", ""]
        for r in falhas:
            linhas += [f"### {r['teste']}", "", "```", r["detalhe"].strip(), "```", ""]

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


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
