"""
Testes de unidade dos componentes C_Semantico e C_TabelaSimbolos
(fase 3: AST -> AST validada + tabela de simbolos).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_semantico -v
"""
import unittest

from apoio import mensagens_aviso, mensagens_erro, semantico
from tabela_simbolos import C_TabelaSimbolos


class TestTabelaSimbolos(unittest.TestCase):
    def setUp(self):
        self.t = C_TabelaSimbolos()

    def test_escopo_global_inicial(self):
        self.assertEqual(self.t.nivel(), 0)
        self.assertEqual(self.t.escopo_atual(), "global")

    def test_definir_e_buscar(self):
        self.assertTrue(self.t.definir("x", "number", 1))
        s = self.t.buscar("x")
        self.assertEqual((s.nome, s.tipo, s.linha, s.escopo), ("x", "number", 1, "global"))
        self.assertIsNone(self.t.buscar("y"))

    def test_duplicata_no_mesmo_escopo_e_rejeitada(self):
        self.t.definir("x", "number", 1)
        self.assertFalse(self.t.definir("x", "string", 2))
        self.assertEqual(self.t.buscar("x").tipo, "number")

    def test_escopo_interno_esconde_o_externo(self):
        self.t.definir("x", "number", 1)
        self.t.entrar_escopo("funcao f")
        self.assertEqual(self.t.nivel(), 1)
        self.assertTrue(self.t.definir("x", "string", 2))     # outro x, permitido
        self.assertEqual(self.t.buscar("x").tipo, "string")
        self.t.sair_escopo()
        self.assertEqual(self.t.buscar("x").tipo, "number")

    def test_simbolo_do_escopo_externo_e_visivel(self):
        self.t.definir("g", "number", 1)
        self.t.entrar_escopo("bloco")
        self.t.entrar_escopo("bloco")
        self.assertIsNotNone(self.t.buscar("g"))

    def test_escopo_global_nunca_sai(self):
        self.t.sair_escopo()
        self.t.sair_escopo()
        self.assertEqual(self.t.nivel(), 0)
        self.assertTrue(self.t.definir("x", "number", 1))

    def test_exportar_mantem_historico_apos_sair(self):
        self.t.definir("f", "FUNC", 1, ["a"])
        self.t.entrar_escopo("funcao f")
        self.t.definir("a", "var", 1)
        self.t.sair_escopo()
        self.assertEqual(self.t.exportar(), [
            {"nome": "f", "tipo": "FUNC", "escopo": "global", "linha": 1, "parametros": ["a"]},
            {"nome": "a", "tipo": "var", "escopo": "funcao f", "linha": 1, "parametros": []},
        ])


class TestTabelaPreenchidaPeloSemantico(unittest.TestCase):
    def test_tipos_e_escopos(self):
        _, sem, _ = semantico('func soma(a, b) { var r = a + b; return r; }\n'
                              'var n = 3;\nvar s = "oi";\nvar l = [1, 2];\nvar ok = true;\n'
                              'class P { var x = 0; func f() { return 1; } }\n'
                              'fork t = soma(1, 2);\nvar v = join t;')
        tabela = {(s["nome"], s["escopo"]): s for s in sem.obter_tabela().exportar()}
        self.assertEqual(tabela[("soma", "global")]["tipo"], "FUNC")
        self.assertEqual(tabela[("soma", "global")]["parametros"], ["a", "b"])
        self.assertIn(("a", "funcao soma"), tabela)
        self.assertIn(("r", "funcao soma"), tabela)
        self.assertEqual(tabela[("n", "global")]["tipo"], "number")
        self.assertEqual(tabela[("s", "global")]["tipo"], "string")
        self.assertEqual(tabela[("l", "global")]["tipo"], "list")
        self.assertEqual(tabela[("t", "global")]["tipo"], "tarefa")
        self.assertEqual(tabela[("n", "global")]["linha"], 2)

    def test_novo_semantico_a_cada_analise(self):
        _, sem1, _ = semantico("var a = 1;")
        _, sem2, _ = semantico("var b = 1;")
        self.assertEqual([s["nome"] for s in sem2.obter_tabela().exportar()], ["b"])
        self.assertEqual([s["nome"] for s in sem1.obter_tabela().exportar()], ["a"])


class TestErrosSemanticos(unittest.TestCase):
    def assertUmErro(self, codigo, trecho):
        erros = mensagens_erro(codigo)
        self.assertTrue(any(trecho in e for e in erros), f"'{trecho}' nao esta em {erros}")

    def test_programa_valido(self):
        valido, sem, _ = semantico("var x = 1;\nfunc f(a) { return a * 2; }\nprint(f(x));")
        self.assertTrue(valido)
        self.assertEqual(sem.obter_erros(), [])

    def test_variavel_nao_declarada(self):
        self.assertUmErro("print(y);", "Variavel 'y' nao declarada")
        self.assertUmErro("y = 3;", "Variavel 'y' nao declarada")

    def test_redeclaracao(self):
        self.assertUmErro("var x = 1;\nvar x = 2;", "Variavel 'x' ja declarada")

    def test_redeclaracao_de_parametro(self):
        self.assertUmErro("func f(a) { var a = 1; }", "'a' ja e um parametro")

    def test_mesmo_nome_em_escopos_diferentes_e_permitido(self):
        self.assertEqual(mensagens_erro("var x = 1;\nfunc f() { var x = 2; return x; }"), [])

    def test_variavel_fora_do_escopo(self):
        self.assertUmErro("seq { var interna = 1; }\nprint(interna);", "Variavel 'interna' nao declarada")

    def test_tipo_incompativel_na_declaracao(self):
        self.assertUmErro('number n = "texto";', "Tipo incompativel em 'n'")

    def test_tipo_incompativel_na_atribuicao(self):
        self.assertUmErro('var n = 1;\nn = "texto";', "Tipo incompativel em atribuicao de 'n'")

    def test_operador_aritmetico_com_texto(self):
        self.assertUmErro('var s = "a" - 1;', "Operador '-' exige operandos numericos")
        self.assertUmErro('var s = "a" & 1;', "Operador '&' exige operandos numericos")

    def test_concatenacao_de_texto_e_permitida(self):
        self.assertEqual(mensagens_erro('var s = "Aluno " + 7;'), [])

    def test_funcao_nao_declarada_e_aridade(self):
        self.assertUmErro("print(nada(1));", "Funcao 'nada' nao declarada")
        self.assertUmErro("func f(a, b) { return a; }\nprint(f(1));", "espera 2 argumento(s), recebeu 1")

    def test_classes_metodos_e_atributos(self):
        base = "class P { var x = 0; func mover(d) { this.x = this.x + d; } }\nvar p = new P();\n"
        self.assertEqual(mensagens_erro(base + "p.mover(1);\nprint(p.x);"), [])
        self.assertUmErro(base + "p.voar();", "Metodo 'voar' nao declarado em 'P'")
        self.assertUmErro(base + "p.mover();", "espera 1 argumento(s), recebeu 0")
        self.assertUmErro(base + "print(p.y);", "Atributo 'y' nao declarado em 'P'")
        self.assertUmErro("var q = new Nada();", "Classe 'Nada' nao declarada")
        self.assertUmErro("class A extends Nada { }", "Superclasse 'Nada' nao declarada")

    def test_break_fora_de_laco(self):
        self.assertUmErro("break;", "usado fora de laco")
        self.assertEqual(mensagens_erro("while (true) { break; }"), [])

    def test_erros_sao_acumulados_com_linha(self):
        _, sem, _ = semantico("var x = 1;\nvar x = 2;\nprint(y);\nz = 1;")
        self.assertEqual([e.linha for e in sem.obter_erros()], [2, 3, 4])
        self.assertTrue(all(e.fase == "SEMANTICO" for e in sem.obter_erros()))


class TestForkJoinSemantico(unittest.TestCase):
    FUNC = "func f(x) { return x * 2; }\nfunc g(x) { print(x); }\n"

    def assertUmErro(self, codigo, trecho):
        erros = mensagens_erro(self.FUNC + codigo)
        self.assertTrue(any(trecho in e for e in erros), f"'{trecho}' nao esta em {erros}")

    def test_fork_join_validos(self):
        codigo = self.FUNC + "fork a = f(1) on core 0;\nfork b = f(2);\nvar r = join a;\njoin b;"
        self.assertEqual(mensagens_erro(codigo), [])

    def test_join_de_tarefa_inexistente(self):
        self.assertUmErro("join nada;", "Tarefa 'nada' nao declarada")

    def test_join_de_variavel_que_nao_e_tarefa(self):
        self.assertUmErro("var v = 1;\njoin v;", "'v' nao e uma tarefa criada com fork")

    def test_tarefa_usada_como_valor(self):
        self.assertUmErro("fork t = f(1);\nprint(t);", "use 'join t'")

    def test_join_como_valor_de_funcao_sem_retorno(self):
        self.assertUmErro("fork t = g(1);\nvar r = join t;", "nao retorna valor")

    def test_fork_dentro_de_laco(self):
        self.assertUmErro("var i = 0;\nwhile (i < 2) { fork t = f(i); join t; i = i + 1; }",
                          "fork nao pode ser usado dentro de laco")

    def test_nucleo_deve_ser_inteiro(self):
        self.assertUmErro("fork t = f(1) on core 1.5;\njoin t;", "deve ser um numero inteiro")
        self.assertUmErro('fork t = f(1) on core "0";\njoin t;', "deve ser um numero inteiro")

    def test_fork_remoto_valido(self):
        codigo = self.FUNC + 'fork t = f(3) on host "127.0.0.1":5400;\nvar r = join t;'
        self.assertEqual(mensagens_erro(codigo), [])

    def test_fork_remoto_endereco_e_porta(self):
        self.assertUmErro("fork t = f(1) on host 10:5400;\njoin t;", "endereco em 'on host' deve ser um texto")
        self.assertUmErro('fork t = f(1) on host "ip":"porta";\njoin t;', "porta em 'on host' deve ser um numero")

    def test_fork_remoto_so_de_funcao_do_programa(self):
        self.assertUmErro('fork t = to_int("3") on host "ip":1;\njoin t;', "aceita apenas funcoes declaradas")

    def test_join_sem_tarefas_gera_aviso(self):
        self.assertIn("'join;' sem nenhuma tarefa (fork) para esperar.", mensagens_aviso("join;"))

    def test_aviso_de_global_alterada_em_fork(self):
        avisos = mensagens_aviso("var total = 0;\nfunc soma(x) { total = total + x; return total; }\n"
                                 "fork t = soma(1);\njoin t;")
        self.assertTrue(any("altera variavel global" in a for a in avisos), avisos)

    def test_join_sem_nomes_resolve_todas_as_tarefas(self):
        _, _, programa = semantico(self.FUNC + "fork a = f(1);\nfork b = f(2);\njoin;")
        self.assertEqual(programa.statements[-1].handles_resolvidos, ["a", "b"])


class TestAnotacoesParaOsGeradores(unittest.TestCase):
    """O semantico preenche informacoes da AST que os geradores de codigo usam."""

    def test_variavel_global(self):
        _, _, p = semantico("var x = 1;\nseq { var y = 2; }")
        self.assertTrue(p.statements[0].escopo_global)
        self.assertEqual(p.statements[0].tipo_cpp, "long long")
        self.assertFalse(p.statements[1].statements[0].escopo_global)

    def test_promocao_para_real(self):
        _, _, p = semantico("var soma = 0;\nsoma = soma + 0.5;")
        self.assertTrue(p.statements[0].promover_double)

    def test_tipo_dos_elementos_da_lista(self):
        _, _, p = semantico('var a = [1, 2];\nvar b = ["x", "y"];\nvar c = [1, 2.5];')
        self.assertEqual([d.init_value.tipo_elemento for d in p.statements],
                         ["long long", "std::string", "double"])

    def test_retorno_real_da_funcao(self):
        _, _, p = semantico("func metade(x) { return x / 2; }")
        self.assertTrue(p.statements[0].retorno_real)


if __name__ == "__main__":
    unittest.main()
