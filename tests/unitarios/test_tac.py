"""
Testes de unidade do componente C_GeradorTAC
(fase 4: AST -> codigo de tres enderecos).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_tac -v
"""
import re
import unittest

from apoio import tac, tac_linhas


class TestExpressoes(unittest.TestCase):
    def test_atribuicao_simples_nao_usa_temporario(self):
        self.assertEqual(tac_linhas("var x = 3;"), ["x = 3"])

    def test_um_operador_por_instrucao(self):
        self.assertEqual(tac_linhas("var a = 1;\nvar b = 2;\nvar r = a + b * 3;"),
                         ["a = 1", "b = 2", "t0 = b * 3", "t1 = a + t0", "r = t1"])

    def test_parenteses_mudam_a_ordem(self):
        linhas = tac_linhas("var a = 1;\nvar r = (a + 2) * 3;")
        self.assertEqual(linhas[1:], ["t0 = a + 2", "t1 = t0 * 3", "r = t1"])

    def test_temporarios_sao_unicos(self):
        texto = tac("var a = 1;\nvar r = a + 1;\nvar s = a * 2 - r / 4;")
        definidos = re.findall(r"^(t\d+) =", texto, re.M)
        self.assertEqual(len(definidos), len(set(definidos)))

    def test_operadores_novos_e_unarios(self):
        linhas = tac_linhas("var i = 5;\nvar r = 7 // 2 + (0xFF & i) + (1 << 3);\nvar n = -i;\nvar b = !(i > 1);")
        for esperado in ("t0 = 7 // 2", "t1 = 0xFF & i", "t3 = 1 << 3", "t5 = -i", "t7 = !t6"):
            self.assertIn(esperado, linhas)

    def test_lista_indice_e_matriz(self):
        linhas = tac_linhas("var l = [1, 2, 3];\nvar x = l[1];\nvar m = matrix(2, 2, 0);\nm[0][1] = 5;")
        self.assertIn("t0 = [1, 2, 3]", linhas)
        self.assertIn("t1 = l[1]", linhas)
        self.assertIn("t2 = matrix(2, 2, 0)", linhas)
        self.assertEqual(linhas[-2:], ["t3 = m[0]", "t3[1] = 5"])


class TestControleDeFluxo(unittest.TestCase):
    def test_if_else_com_rotulos(self):
        linhas = tac_linhas("var x = 1;\nif (x > 0) { x = 2; } else { x = 3; }")
        self.assertEqual(linhas, [
            "x = 1", "t0 = x > 0", "ifFalse t0 goto ELSE_1", "x = 2", "goto ENDIF_0",
            "ELSE_1:", "x = 3", "ENDIF_0:"])

    def test_while_volta_ao_inicio(self):
        linhas = tac_linhas("var i = 0;\nwhile (i < 3) { i = i + 1; }")
        self.assertEqual(linhas, [
            "i = 0", "WHILE_0:", "t0 = i < 3", "ifFalse t0 goto ENDWHILE_1",
            "t1 = i + 1", "i = t1", "goto WHILE_0", "ENDWHILE_1:"])

    def test_do_while_testa_no_fim(self):
        linhas = tac_linhas("var i = 0;\ndo { i = i + 1; } while (i < 3);")
        self.assertEqual(linhas[1], "DO_0:")
        self.assertEqual(linhas[-2:], ["if t1 goto DO_0", "ENDDO_1:"])

    def test_for_com_break(self):
        linhas = tac_linhas("for (var k = 0; k < 2; k = k + 1) { if (k == 1) { break; } }")
        self.assertEqual(linhas[0:2], ["k = 0", "FOR_0:"])
        self.assertIn("ifFalse t0 goto ENDFOR_2", linhas)
        self.assertIn("FOR_STEP_1:", linhas)
        # break salta para o fim do for
        i = linhas.index("ifFalse t1 goto ENDIF_3")
        self.assertEqual(linhas[i + 1], "goto ENDFOR_2")

    def test_todo_rotulo_usado_em_goto_existe(self):
        texto = tac("var i = 0;\nwhile (i < 5) { if (i == 3) { break; } i = i + 1; }\n"
                    "do { i = i - 1; } while (i > 0);")
        definidos = set(re.findall(r"^\s*(\w+):\s*$", texto, re.M))
        usados = set(re.findall(r"goto (\w+)", texto))
        self.assertTrue(usados <= definidos, usados - definidos)


class TestFuncoesEObjetos(unittest.TestCase):
    def test_funcao_parametros_e_chamada(self):
        linhas = tac_linhas("func soma(a, b) { return a + b; }\nvar r = soma(1, 2);")
        self.assertEqual(linhas, [
            "func soma:", "t0 = a + b", "return t0", "endfunc soma",
            "param 1", "param 2", "t1 = call soma, 2", "r = t1"])

    def test_classe_metodo_e_this(self):
        linhas = tac_linhas("class P { var x = 0; func mover(d) { this.x = this.x + d; } }\n"
                            "var p = new P();\np.mover(2);")
        self.assertIn("# class P", linhas)
        self.assertEqual(linhas[1:6], ["func mover:", "t0 = this.x", "t1 = t0 + d", "this.x = t1", "endfunc mover"])
        self.assertIn("t2 = new P", linhas)
        self.assertEqual(linhas[-2:], ["param 2", "t3 = call p.mover, 1"])

    def test_print_entrada_e_canais(self):
        linhas = tac_linhas('var c = c_channel("127.0.0.1", 5000);\nsend(c, "oi");\n'
                            'var r = receive(c);\nvar s = input("Nome: ");\nprint(s, r);')
        for esperado in ('t0 = c_channel("127.0.0.1", 5000)', 'send c, "oi"', "t1 = receive c",
                         't2 = input("Nome: ")', "print s", "print r"):
            self.assertIn(esperado, linhas)


class TestForkJoin(unittest.TestCase):
    FUNC = "func f(x) { return x * 2; }\n"

    def test_fork_em_nucleo_e_join_como_valor(self):
        linhas = tac_linhas(self.FUNC + "fork t = f(1) on core 0;\nvar r = join t;")
        self.assertEqual(linhas[-4:], ["param 1", "t = fork f, 1, core 0", "t1 = join t", "r = t1"])

    def test_fork_remoto(self):
        linhas = tac_linhas(self.FUNC + 'fork t = f(3) on host "127.0.0.1":5400;\njoin t;')
        self.assertIn('t = fork f, 1, host "127.0.0.1":5400', linhas)
        self.assertEqual(linhas[-1], "join t")

    def test_fork_sem_alocacao_e_join_de_todas(self):
        linhas = tac_linhas(self.FUNC + "fork a = f(1);\nfork b = f(2);\njoin;")
        self.assertIn("a = fork f, 1", linhas)
        self.assertEqual(linhas[-2:], ["join a", "join b"])


if __name__ == "__main__":
    unittest.main()
