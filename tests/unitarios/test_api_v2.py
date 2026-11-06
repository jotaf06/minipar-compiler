"""
Testes da API v2 (uma rota por fase do compilador).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest discover -s tests/unitarios -v
"""
import os
import sys
import threading
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import api_v2          # noqa: E402
from app import app    # noqa: E402

PROGRAMA_OK = """
func dobro(x) { return x * 2; }
var nome = input("Nome: ");
print("Ola,", nome, "| dobro:", dobro(21));
"""

PROGRAMA_ERRO_SEMANTICO = """
var x = 1;
var x = 2;
print(y);
"""

PROGRAMA_ERRO_SINTATICO = """
var x = 10
print(x);
"""


class TestApiV2(unittest.TestCase):
    def setUp(self):
        self.cliente = app.test_client()

    def post(self, rota, **dados):
        return self.cliente.post(f"/api/v2/{rota}", json=dados)

    # ---- Fases de analise ----
    def test_tokens(self):
        r = self.post("tokens", codigo=PROGRAMA_OK)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["sucesso"])
        primeiro = d["tokens"][0]
        self.assertEqual(primeiro, {"tipo": "FUNC", "lexema": "func", "linha": 2, "coluna": 1})
        self.assertEqual(d["tokens"][-1]["tipo"], "END_OF_FILE")

    def test_ast(self):
        d = self.post("ast", codigo=PROGRAMA_OK).get_json()
        raiz = d["ast"]
        self.assertEqual(raiz["tipo"], "Program")
        func = raiz["filhos"][0]
        self.assertEqual(func["rotulo"], "func dobro(x)")
        self.assertEqual(func["categoria"], "declaracao")
        self.assertEqual(func["papel"], "comandos")
        self.assertEqual(func["linha"], 2)

    def test_semantico_com_tabela_de_simbolos(self):
        d = self.post("semantico", codigo=PROGRAMA_OK).get_json()
        nomes = {(s["nome"], s["escopo"]) for s in d["simbolos"]}
        self.assertIn(("dobro", "global"), nomes)
        self.assertIn(("x", "funcao dobro"), nomes)
        self.assertIn(("nome", "global"), nomes)

    def test_tac_e_cpp(self):
        d = self.post("analisar", codigo=PROGRAMA_OK).get_json()
        self.assertIn("func dobro:", d["tac"])
        self.assertIn("int main(", d["cpp"])
        for campo in ("tokens", "ast", "simbolos", "tac", "cpp"):
            self.assertIn(campo, d)

    # ---- Erros: fase, linha e coluna + resultado parcial ----
    def test_erro_semantico_mantem_fases_anteriores(self):
        d = self.post("analisar", codigo=PROGRAMA_ERRO_SEMANTICO).get_json()
        self.assertFalse(d["sucesso"])
        self.assertEqual(d["fase_erro"], "SEMANTICO")
        self.assertEqual([e["linha"] for e in d["erros"]], [3, 4])
        self.assertTrue(d["tokens"])                 # fases 1 e 2 continuam disponiveis
        self.assertEqual(d["ast"]["tipo"], "Program")
        self.assertEqual(d["tac"], "")               # fase 4 nao executou

    def test_erro_sintatico_com_coluna(self):
        d = self.post("ast", codigo=PROGRAMA_ERRO_SINTATICO).get_json()
        self.assertEqual(d["fase_erro"], "SINTATICO")
        self.assertEqual((d["erros"][0]["linha"], d["erros"][0]["coluna"]), (2, 11))
        self.assertIsNone(d["ast"])

    def test_requisicao_sem_codigo(self):
        r = self.post("tokens", outro="x")
        self.assertEqual(r.status_code, 400)
        self.assertIn("codigo", r.get_json()["erro_interno"])

    # ---- Compilar, baixar e executar ----
    def test_compilar_e_baixar(self):
        d = self.post("compilar", codigo=PROGRAMA_OK).get_json()
        self.assertTrue(d["sucesso"], d)
        r = self.cliente.get(d["download"])
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.data), 1000)       # binario do executavel
        r.close()

    def test_download_id_invalido_ou_inexistente(self):
        self.assertEqual(self.cliente.get("/api/v2/download/..%2Fapp").status_code, 404)  # barrado pelo roteamento
        self.assertEqual(self.cliente.get("/api/v2/download/abc.def").status_code, 400)   # barrado pela validacao
        self.assertEqual(self.cliente.get("/api/v2/download/abc123").status_code, 404)

    def test_executar_com_entrada(self):
        d = self.post("executar", codigo=PROGRAMA_OK, entradas=["Ana"]).get_json()
        self.assertTrue(d["sucesso"], d)
        self.assertEqual(d["saida"], "Nome: Ola, Ana | dobro: 42\n")
        self.assertEqual(d["codigo_saida"], 0)

    def test_executar_erro_de_execucao(self):
        d = self.post("executar", codigo="print(1 // 0);").get_json()
        self.assertTrue(d["sucesso"])                # compilou; o erro e na execucao
        self.assertEqual(d["codigo_saida"], 1)
        self.assertIn("Divisao inteira por zero", d["erros_execucao"])

    def test_executar_tempo_limite(self):
        original = api_v2.TEMPO_MAX_EXECUCAO
        api_v2.TEMPO_MAX_EXECUCAO = 1
        try:
            d = self.post("executar", codigo="while (true) { }").get_json()
        finally:
            api_v2.TEMPO_MAX_EXECUCAO = original
        self.assertTrue(d["tempo_limite"])

    def test_executar_saida_infinita_e_truncada(self):
        d = self.post("executar", codigo='while (true) { print("linha"); }').get_json()
        self.assertTrue(d["saida_truncada"])
        self.assertLessEqual(len(d["saida"].encode()), api_v2.LIMITE_SAIDA)
        self.assertLess(d["tempo_execucao"], api_v2.TEMPO_MAX_EXECUCAO)

    def test_entradas_deve_ser_lista(self):
        r = self.post("executar", codigo=PROGRAMA_OK, entradas="Ana")
        self.assertEqual(r.status_code, 400)

    def test_analise_nao_deixa_arquivos(self):
        antes = set(os.listdir(api_v2.PASTA_WEB)) if os.path.isdir(api_v2.PASTA_WEB) else set()
        self.post("analisar", codigo=PROGRAMA_OK)
        depois = set(os.listdir(api_v2.PASTA_WEB)) if os.path.isdir(api_v2.PASTA_WEB) else set()
        self.assertEqual(depois - antes, set())

    # ---- Requisicoes simultaneas (um C_Controle por requisicao) ----
    def test_requisicoes_simultaneas(self):
        resultados = {}

        def analisar(i):
            codigo = f"var v{i} = {i};\nprint(v{i});"
            resultados[i] = app.test_client().post("/api/v2/semantico", json={"codigo": codigo}).get_json()

        threads = [threading.Thread(target=analisar, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        for i, d in resultados.items():
            self.assertTrue(d["sucesso"])
            self.assertEqual([s["nome"] for s in d["simbolos"]], [f"v{i}"])


if __name__ == "__main__":
    unittest.main()
