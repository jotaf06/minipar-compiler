"""
Testes do componente C_Controle (orquestrador das fases) e da integracao
entre os componentes atraves das interfaces I*.

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_controle -v
"""
import os
import shutil
import tempfile
import unittest

import apoio  # noqa: F401  (ajusta o sys.path)
from controle import C_Controle, ResultadoCompilacao
from erros import ErroGeracao
from interfaces import (
    ICompiladorCpp, IControle, IGeradorCpp, IGeradorTAC, ILexico, ISemantico, ISintatico,
    ITabelaSimbolos,
)
from codegen import C_GeradorCpp
from compilador_gcc import C_CompiladorGcc
from lexer import C_Lexico
from parser import C_Sintatico
from semantic import C_Semantico
from tabela_simbolos import C_TabelaSimbolos
from tac import C_GeradorTAC

PROGRAMA = 'func dobro(x) { return x * 2; }\nvar n = 21;\nprint("dobro:", dobro(n));\n'


class CompiladorFalso(ICompiladorCpp):
    """Substitui o g++: registra a chamada e devolve um caminho ficticio."""

    def __init__(self):
        self.chamadas = []

    def compilar(self, codigo_cpp, nome_saida):
        self.chamadas.append(nome_saida)
        return f"/falso/{nome_saida}"


class CompiladorQueFalha(ICompiladorCpp):
    def compilar(self, codigo_cpp, nome_saida):
        raise ErroGeracao("g++ indisponivel")


class LexicoContador(ILexico):
    """Lexico alternativo que delega ao C_Lexico e conta as chamadas."""

    def __init__(self):
        self.vezes = 0
        self.real = C_Lexico()

    def analisar(self, codigo_fonte):
        self.vezes += 1
        return self.real.analisar(codigo_fonte)


class TestComponentesImplementamInterfaces(unittest.TestCase):
    def test_cada_componente_implementa_sua_interface(self):
        pares = [(C_Lexico, ILexico), (C_Sintatico, ISintatico), (C_Semantico, ISemantico),
                 (C_TabelaSimbolos, ITabelaSimbolos), (C_GeradorTAC, IGeradorTAC),
                 (C_GeradorCpp, IGeradorCpp), (C_CompiladorGcc, ICompiladorCpp),
                 (C_Controle, IControle)]
        for componente, interface in pares:
            with self.subTest(componente=componente.__name__):
                self.assertTrue(issubclass(componente, interface))

    def test_interfaces_nao_podem_ser_instanciadas(self):
        for interface in (ILexico, ISintatico, ISemantico, IGeradorTAC, IControle):
            with self.subTest(interface=interface.__name__):
                with self.assertRaises(TypeError):
                    interface()


class TestControle(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="minipar_controle_")
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.gcc = CompiladorFalso()

    def controle(self, **kw):
        kw.setdefault("compilador", self.gcc)
        return C_Controle(pasta_saida=self.pasta, **kw)

    def test_todas_as_fases_com_sucesso(self):
        r = self.controle().compilar(PROGRAMA, "prog")
        self.assertIsInstance(r, ResultadoCompilacao)
        self.assertTrue(r.sucesso)
        self.assertIsNone(r.fase_erro)
        self.assertEqual(r.erros, [])
        self.assertTrue(r.tokens)
        self.assertEqual(type(r.ast).__name__, "Program")
        self.assertIn("dobro", [s["nome"] for s in r.simbolos])
        self.assertIn("func dobro:", r.tac)
        self.assertIn("int main(", r.cpp)
        self.assertEqual(r.executavel, "/falso/prog")
        self.assertEqual(self.gcc.chamadas, ["prog"])

    def test_tac_e_salvo_na_pasta_de_saida(self):
        r = self.controle().compilar(PROGRAMA, "prog")
        with open(os.path.join(self.pasta, "prog.tac"), encoding="utf-8") as f:
            self.assertEqual(f.read(), r.tac)

    def test_sem_executavel_salva_o_cpp_e_nao_chama_o_gcc(self):
        r = self.controle().compilar(PROGRAMA, "prog", gerar_executavel=False)
        self.assertTrue(r.sucesso)
        self.assertIsNone(r.executavel)
        self.assertEqual(self.gcc.chamadas, [])
        self.assertTrue(os.path.isfile(os.path.join(self.pasta, "prog.cpp")))

    def test_log_das_fases_em_ordem(self):
        mensagens = []
        self.controle(log=mensagens.append).compilar(PROGRAMA, "prog")
        fases = [m.split("]")[0] + "]" for m in mensagens]
        self.assertEqual(fases, [f"[Fase {i}]" for i in range(1, 7)])

    def test_erro_lexico_para_na_fase_1(self):
        r = self.controle().compilar("var x = 1;\nvar y = $;", "prog")
        self.assertFalse(r.sucesso)
        self.assertEqual(r.fase_erro, "LEXICO")
        self.assertEqual((r.erros[0].linha, r.erros[0].coluna), (2, 9))
        self.assertEqual(r.tokens, [])
        self.assertIsNone(r.ast)

    def test_erro_sintatico_mantem_os_tokens(self):
        r = self.controle().compilar("var x = 1\nprint(x);", "prog")
        self.assertEqual(r.fase_erro, "SINTATICO")
        self.assertTrue(r.tokens)
        self.assertIsNone(r.ast)

    def test_erro_semantico_mantem_tokens_ast_e_tabela(self):
        r = self.controle().compilar("var x = 1;\nprint(y);\nprint(z);", "prog")
        self.assertEqual(r.fase_erro, "SEMANTICO")
        self.assertEqual(len(r.erros), 2)                 # todos os erros semanticos
        self.assertIsNotNone(r.ast)
        self.assertEqual([s["nome"] for s in r.simbolos], ["x"])
        self.assertEqual((r.tac, r.cpp), ("", ""))       # fases 4 e 5 nao executaram
        self.assertEqual(self.gcc.chamadas, [])
        self.assertFalse(os.path.exists(os.path.join(self.pasta, "prog.tac")))

    def test_erro_no_gcc_mantem_tac_e_cpp(self):
        r = self.controle(compilador=CompiladorQueFalha()).compilar(PROGRAMA, "prog")
        self.assertEqual(r.fase_erro, "GCC")
        self.assertEqual(r.erros[0].fase, "GERACAO")
        self.assertTrue(r.tac)
        self.assertTrue(r.cpp)
        self.assertIsNone(r.executavel)

    def test_avisos_nao_impedem_a_compilacao(self):
        r = self.controle().compilar("join;", "prog")
        self.assertTrue(r.sucesso)
        self.assertEqual(len(r.avisos), 1)
        self.assertEqual(r.avisos[0].fase, "AVISO")

    def test_componente_injetado_via_interface(self):
        lexico = LexicoContador()
        controle = self.controle(lexico=lexico)
        controle.compilar(PROGRAMA, "a")
        controle.compilar(PROGRAMA, "b")
        self.assertEqual(lexico.vezes, 2)

    def test_semantico_novo_a_cada_compilacao(self):
        controle = self.controle()
        controle.compilar("var a = 1;", "a")
        r = controle.compilar("var a = 2;", "b")       # sem "Variavel 'a' ja declarada"
        self.assertTrue(r.sucesso, [str(e) for e in r.erros])

    def test_para_dict_e_serializavel(self):
        import json
        r = self.controle().compilar("var x = 1;\nprint(y);", "prog")
        d = r.para_dict()
        json.dumps(d)
        self.assertEqual(d["fase_erro"], "SEMANTICO")
        self.assertEqual(d["erros"][0]["linha"], 2)
        self.assertEqual(d["tokens"][0], {"tipo": "VAR", "lexema": "var", "linha": 1, "coluna": 1})


if __name__ == "__main__":
    unittest.main()
