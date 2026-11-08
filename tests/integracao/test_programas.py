"""
Testes de integracao: cada programa de tests/ passa por TODOS os componentes
(C_Controle -> lexico -> sintatico -> semantico -> TAC -> C++ -> g++), e o
executavel gerado e executado com uma entrada fixa. O teste confere trechos da
saida que comprovam o resultado do algoritmo (os tempos variam entre maquinas,
entao nos testes 8-10 confere-se a estrutura e a consistencia, nao os numeros).

Os programas sao compilados uma unica vez, em paralelo, no inicio (setUpClass).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest discover -s tests/integracao -v
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "unitarios"))
from apoio import PASTA_TESTES  # noqa: E402
from controle import C_Controle  # noqa: E402

TEMPO_MAX_EXECUCAO = 120   # segundos por execucao
PORTA_TRABALHADOR = 5400   # usada pelos programas com "on host" (fixa no codigo-fonte)

# arquivo (relativo a tests/) -> entrada padrao
PROGRAMAS = {
    "teste1_calculadora_cliente_servidor.minipar": "+\n5\n7\n",
    "teste2_fatorial_fibonacci_par.minipar": "",
    "teste3_neuronio.minipar": "",
    "teste4_rede_neural_xor.minipar": "",
    # Comprou: Smartphone, Jeans, Micro-ondas e Ficcao (mesma entrada do expected_results)
    "teste5_recomendacao.minipar": "1\n0\n0\n0\n0\n1\n0\n0\n0\n1\n0\n0\n1\n0\n0\n0\n",
    "teste6_quicksort_classes.minipar": "10 -3 -40 80 70 -100\n",
    "teste7_quicksort_iterativo_tac.minipar": "",
    "teste8_avaliacao_4_nucleos.minipar": "",
    "teste8_remoto_3_nucleos_1_computador.minipar": "",
    "teste9_5_nucleos_mandelbrot.minipar": "",
    "teste10_6_nucleos_2_fractais.minipar": "",
    "teste_adicional1_paralelismo_3_computadores.minipar": "",
    "teste_adicional2_tapete_sierpinski.minipar": "",
    "teste_ascii_art_divertidapkrl.minipar": "",
    "teste_bnf_controles_input.minipar": "Ana\n",
    "recursos/recurso_fork_join.minipar": "",
    "recursos/recurso_fork_remoto.minipar": "",
    "recursos/recurso_globais.minipar": "",
    "recursos/recurso_numeros.minipar": "",
    "recursos/recurso_saida_conversoes.minipar": "",
    "recursos/recurso_strings_listas.minipar": "",
}

# Preenchido durante a execucao; lido por tests/executar_testes.py para o relatorio
RELATORIO = {}


def nome_programa(arquivo):
    return os.path.basename(arquivo)[:-len(".minipar")]


def porta_livre(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", porta))
            return True
        except OSError:
            return False


class Trabalhador:
    """Executa o programa em modo --worker (o "outro computador", em localhost)."""

    def __init__(self, executavel, pasta, porta=PORTA_TRABALHADOR):
        self.proc = subprocess.Popen([executavel, "--worker", str(porta)], cwd=pasta,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.linhas = []
        pronto = threading.Event()

        def ler():
            for linha in self.proc.stdout:
                self.linhas.append(linha)
                if "Aguardando subtarefas" in linha:
                    pronto.set()
            pronto.set()

        threading.Thread(target=ler, daemon=True).start()
        if not pronto.wait(10) or self.proc.poll() is not None:
            self.encerrar()
            raise RuntimeError("Trabalhador nao iniciou: " + "".join(self.linhas))

    def encerrar(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(5)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.encerrar()


@unittest.skipUnless(shutil.which("g++"), "g++ nao encontrado")
class TestProgramas(unittest.TestCase):
    pasta = None
    compilados = {}

    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.mkdtemp(prefix="minipar_integracao_")

        def compilar(arquivo):
            with open(os.path.join(PASTA_TESTES, arquivo), encoding="utf-8") as f:
                codigo = f.read()
            inicio = time.perf_counter()
            resultado = C_Controle(pasta_saida=cls.pasta).compilar(codigo, nome_programa(arquivo))
            return arquivo, resultado, time.perf_counter() - inicio

        trabalhadores = max(1, min(4, (os.cpu_count() or 2) // 2))
        with ThreadPoolExecutor(trabalhadores) as executor:
            for arquivo, resultado, segundos in executor.map(compilar, PROGRAMAS):
                cls.compilados[arquivo] = resultado
                RELATORIO[nome_programa(arquivo)] = {
                    "compilou": resultado.sucesso, "compilacao_s": segundos,
                    "execucao_s": None, "avisos": len(resultado.avisos)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    # ---- apoio ----
    def executar(self, arquivo, entrada=None, codigo_esperado=0):
        resultado = self.compilados[arquivo]
        self.assertTrue(resultado.sucesso, f"{arquivo} nao compilou: " + "; ".join(map(str, resultado.erros)))
        if entrada is None:
            entrada = PROGRAMAS[arquivo]
        inicio = time.perf_counter()
        proc = subprocess.run([resultado.executavel], input=entrada, capture_output=True,
                              text=True, timeout=TEMPO_MAX_EXECUCAO, cwd=self.pasta)
        info = RELATORIO[nome_programa(arquivo)]
        if info["execucao_s"] is None:          # tempo da primeira execucao (entrada padrao)
            info["execucao_s"] = time.perf_counter() - inicio
        self.assertEqual(proc.returncode, codigo_esperado, proc.stderr)
        return proc.stdout

    def assertContemLinhas(self, saida, *linhas):
        presentes = saida.splitlines()
        for linha in linhas:
            self.assertIn(linha, presentes, f"linha ausente: {linha!r}")

    def assertBenchmark(self, saida, nucleos):
        """Estrutura comum dos testes 8-10: tempos sequencial/paralelo e speedup."""
        self.assertRegex(saida, r"(Total de Atividades a Avaliar|Carga de Trabalho): 160")
        seq = float(re.search(r"Tempo Sequencial\s*:\s*([\d.]+) s", saida).group(1))
        par = float(re.search(r"Tempo Paralelo\s*:\s*([\d.]+) s", saida).group(1))
        self.assertGreater(seq, 0)
        self.assertGreater(par, 0)
        if (os.cpu_count() or 1) >= nucleos:
            # Com nucleos suficientes, o paralelo precisa ser bem mais rapido
            self.assertGreater(seq / par, 1.5, f"sem ganho de desempenho: {seq} s x {par} s")
        return seq, par

    # ---- Testes 1 a 7 (MiniPar 2026.1) ----
    def test_01_calculadora_cliente_servidor(self):
        saida = self.executar("teste1_calculadora_cliente_servidor.minipar")
        self.assertIn("Servidor recebeu: + 5 7", saida)
        self.assertIn("Resultado: 12.0", saida)

    def test_01_calculadora_divisao(self):
        saida = self.executar("teste1_calculadora_cliente_servidor.minipar", "/\n7\n2\n")
        self.assertIn("Resultado: 3.5", saida)

    def test_02_fatorial_fibonacci_par(self):
        saida = self.executar("teste2_fatorial_fibonacci_par.minipar")
        self.assertIn("Fatorial de 5: 120", saida)
        inicio = saida.splitlines().index("Fibonacci:")
        self.assertEqual(saida.splitlines()[inicio + 1:inicio + 9], ["0", "1", "1", "2", "3", "5", "8", "13"])

    def test_03_neuronio(self):
        saida = self.executar("teste3_neuronio.minipar")
        self.assertContemLinhas(saida, "Neuronio aprendeu dinamicamente.", "Iteracoes totais: 51",
                                "Valor desejado: 0")

    def test_04_rede_neural_xor(self):
        saida = self.executar("teste4_rede_neural_xor.minipar")
        previsoes = dict(re.findall(r"Input: (\[\d, \d\]), Predicted Output: ([\d.e-]+)", saida))
        self.assertEqual(len(previsoes), 4)
        esperado = {"[0, 0]": 0, "[0, 1]": 1, "[1, 0]": 1, "[1, 1]": 0}
        for entrada, alvo in esperado.items():
            self.assertAlmostEqual(float(previsoes[entrada]), alvo, delta=0.1, msg=entrada)

    def test_05_recomendacao(self):
        saida = self.executar("teste5_recomendacao.minipar")
        depois = saida.split("Produtos recomendados para voce:")[1]
        recomendados = [l.split(" probabilidade")[0] for l in depois.strip().splitlines()]
        # Mesmos produtos do expected_results (sem acentos, como no programa MiniPar)
        self.assertEqual(recomendados, [
            "Laptop", "Tablet", "Fones de ouvido", "Camisa", "Jaqueta", "Sapatos", "Geladeira",
            "Maquina de lavar", "Ar condicionado", "Nao-ficcao", "Ficcao cientifica", "Fantasia"])

    def test_06_quicksort_classes(self):
        saida = self.executar("teste6_quicksort_classes.minipar")
        self.assertContemLinhas(saida, "Vetor original: [10, -3, -40, 80, 70, -100]",
                                "Vetor ordenado: [-100, -40, -3, 10, 70, 80]")

    def test_07_quicksort_iterativo_tac(self):
        saida = self.executar("teste7_quicksort_iterativo_tac.minipar")
        self.assertContemLinhas(saida, "Array ordenado: [5, 12, 33, 61, 98]")
        tac = self.compilados["teste7_quicksort_iterativo_tac.minipar"].tac
        self.assertIn("goto", tac)

    # ---- Testes 8 a 10 (fork/join em nucleos da CPU) ----
    def test_08_avaliacao_4_nucleos(self):
        saida = self.executar("teste8_avaliacao_4_nucleos.minipar")
        self.assertIn("Modo Paralelo (4 Núcleos Dedicados", saida)
        self.assertBenchmark(saida, 4)

    def test_09_mandelbrot_5_nucleos(self):
        saida = self.executar("teste9_5_nucleos_mandelbrot.minipar")
        self.assertIn("=== FRACTAL DE MANDELBROT (Gerado pelo Núcleo 5) ===", saida)
        self.assertIn("@@@@@@@@@@", saida)          # interior do conjunto
        self.assertBenchmark(saida, 5)

    def test_10_dois_fractais_6_nucleos(self):
        svg = os.path.join(self.pasta, "tapete_sierpinski.svg")
        if os.path.exists(svg):
            os.remove(svg)
        saida = self.executar("teste10_6_nucleos_2_fractais.minipar")
        self.assertIn("FRACTAL DE MANDELBROT", saida)
        self.assertIn("=== TAPETE DE SIERPINSKI (Gerado pelo Núcleo 6) ===", saida)
        self.assertIn("Núcleos Utilizados (Paralelo) : 6", saida)
        self.assertBenchmark(saida, 6)
        with open(svg, encoding="utf-8") as f:
            conteudo = f.read()
        self.assertTrue(conteudo.startswith("<svg"))
        self.assertTrue(conteudo.rstrip().endswith("</svg>"))
        self.assertGreater(conteudo.count("<rect"), 100)

    # ---- Fork em outro computador (trabalhador em localhost) ----
    def executar_com_trabalhador(self, arquivo):
        if not porta_livre(PORTA_TRABALHADOR):
            self.skipTest(f"porta {PORTA_TRABALHADOR} ocupada")
        resultado = self.compilados[arquivo]
        self.assertTrue(resultado.sucesso, "; ".join(map(str, resultado.erros)))
        with Trabalhador(resultado.executavel, self.pasta) as trabalhador:
            saida = self.executar(arquivo)
        return saida, "".join(trabalhador.linhas)

    def test_08_remoto_3_nucleos_1_computador(self):
        saida, log = self.executar_com_trabalhador("teste8_remoto_3_nucleos_1_computador.minipar")
        self.assertIn("Atividades corrigidas: 160 | ultima (computador remoto): "
                      "[Monitor 3] Concluiu: Aluno 40 - Atividade 4", saida)
        self.assertBenchmark(saida, 4)
        self.assertIn("[WORKER] Executando subtarefa 0", log)

    def test_fork_remoto(self):
        saida, log = self.executar_com_trabalhador("recursos/recurso_fork_remoto.minipar")
        self.assertContemLinhas(
            saida,
            "Remota: [Monitor 1] Concluiu: Aluno 2 - Atividade 1 | [Monitor 1] Concluiu: Aluno 2 - Atividade 2",
            "Media calculada no computador remoto: 8.333333333333334")
        self.assertIn("registro: subtarefa sem retorno", log)   # executou no trabalhador

    def test_fork_remoto_sem_trabalhador_falha_com_mensagem(self):
        if not porta_livre(PORTA_TRABALHADOR):
            self.skipTest(f"porta {PORTA_TRABALHADOR} ocupada")
        resultado = self.compilados["recursos/recurso_fork_remoto.minipar"]
        proc = subprocess.run([resultado.executavel], capture_output=True, text=True,
                              timeout=TEMPO_MAX_EXECUCAO, cwd=self.pasta)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("127.0.0.1:5400 indisponivel", proc.stderr)

    # ---- Testes adicionais do MiniPar 2026.1 ----
    def test_adicional1_paralelismo_3_computadores(self):
        saida = self.executar("teste_adicional1_paralelismo_3_computadores.minipar")
        self.assertContemLinhas(saida,
                                "PC1 QuickSort: [33,12,98,5,61] -> [5,12,33,61,98]",
                                "PC2 Matrizes: [[1,2],[3,4]] x [[5,6],[7,8]] -> [[19,22],[43,50]]",
                                "PC3 Fatorial: 5! = 120")

    def test_adicional2_tapete_sierpinski(self):
        saida = self.executar("teste_adicional2_tapete_sierpinski.minipar")
        self.assertContemLinhas(saida, "[#, #, #, #, #, #, #, #, #]", "[#,  , #, #,  , #, #,  , #]",
                                "[#, #, #,  ,  ,  , #, #, #]")

    def test_ascii_art(self):
        saida = self.executar("teste_ascii_art_divertidapkrl.minipar")
        self.assertIn("FRACTAL DE SIERPINSKI", saida)
        self.assertGreater(len(saida.splitlines()), 30)

    def test_bnf_controles_input(self):
        saida = self.executar("teste_bnf_controles_input.minipar")
        self.assertIn("Controle OK: 7 2", saida)

    # ---- Recursos novos do MiniPar 2026.2 (saida deterministica) ----
    def test_recurso_numeros(self):
        saida = self.executar("recursos/recurso_numeros.minipar")
        self.assertContemLinhas(saida, "3 / 20 = 0.15", "7 // 2 = 3 | -7 // 2 = -4",
                                "-7 % 3 = 2 | 7.5 % 2 = 1.5", "LCG: 231794730",
                                "bits: 2 7 5 1024 128", "soma: 2.0", "dobro: 4.0", "acumulador: 2.5")

    def test_recurso_saida_conversoes(self):
        saida = self.executar("recursos/recurso_saida_conversoes.minipar")
        self.assertContemLinhas(saida, "2.0 0.30000000000000004 0.3333333333333333 1e-05 3.5 2",
                                "True False [1.5, 2.0] [a, b]", "str: 422.5True",
                                "to_int: 3 -3 124", "to_number: 5.0")
        self.assertIn("clock ok: True", saida)

    def test_recurso_strings_listas(self):
        saida = self.executar("recursos/recurso_strings_listas.minipar")
        self.assertContemLinhas(saida, "concatenacao: abcd | com numero: Aluno 7",
                                "comparacao: True True", "fatia 0 : [10, 20]", "fatia 3 : [70, 80]",
                                "concatenadas: [1, 2, 3]", "fatia de texto: Mini",
                                "pilha: [0, 4, 1, 3] tamanho 4")

    def test_recurso_globais(self):
        saida = self.executar("recursos/recurso_globais.minipar")
        self.assertContemLinhas(saida, "Total: 160 | avaliadores: 4")

    def test_recurso_fork_join(self):
        saida = self.executar("recursos/recurso_fork_join.minipar")
        self.assertIn("resultados iguais: True", saida)
        nucleos = set(re.findall(r"executou no nucleo (\d+)", saida.split("--- Paralelo")[1]))
        if (os.cpu_count() or 1) >= 4:
            self.assertEqual(nucleos, {"0", "1", "2", "3"})   # "on core" respeitado

    # ---- Todos os programas compilam sem erro ----
    def test_todos_os_programas_compilam(self):
        falhas = {a: [str(e) for e in r.erros] for a, r in self.compilados.items() if not r.sucesso}
        self.assertEqual(falhas, {})


if __name__ == "__main__":
    unittest.main()
