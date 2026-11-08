"""
Testes de unidade dos componentes C_GeradorCpp (fase 5: AST -> C++)
e C_CompiladorGcc (fase 6: C++ -> executavel).

O comportamento do C++ gerado em execucao (divisao, formatacao, listas...)
e conferido nos testes de integracao, que executam os programas de tests/recursos.

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_cpp -v
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from apoio import cpp, cpp_remoto, cpp_usuario
from compilador_gcc import C_CompiladorGcc
from erros import ErroGeracao


class TestGeradorCpp(unittest.TestCase):
    def test_estrutura_do_arquivo(self):
        texto = cpp("print(1);")
        self.assertIn("#include", texto)
        self.assertIn("int main(int argc, char** argv)", texto)
        self.assertIn('std::string(argv[1]) == "--worker"', texto)   # modo trabalhador
        self.assertTrue(texto.rstrip().endswith("}"))

    def test_literais_tipados(self):
        codigo = cpp_usuario('var i = 3;\nvar r = 2.5;\nvar s = "oi";\nvar b = true;\nprint(i, r, s, b);')
        for esperado in ("i = 3LL;", "s = std::string(\"oi\");", "b = true;", "__print(i, r, s, b);"):
            self.assertIn(esperado, codigo)
        self.assertIn("long long i;", codigo)     # globais declaradas antes das funcoes
        self.assertIn("std::string s;", codigo)

    def test_operadores_com_semantica_do_python(self):
        codigo = cpp_usuario("var a = 7;\nprint(a / 2, a // 2, a % 2, a & 3, 1 << a);")
        self.assertIn("__div(a, 2LL)", codigo)          # divisao real
        self.assertIn("__floordiv(a, 2LL)", codigo)     # divisao inteira arredondando para baixo
        self.assertIn("(__as_int(a) & __as_int(3LL))", codigo)
        self.assertIn("(__as_int(1LL) << __as_int(a))", codigo)

    def test_listas_tipadas_e_indice(self):
        codigo = cpp_usuario('var l = [1, 2];\nvar n = ["a", "b"];\nprint(l[0], n[1]);')
        self.assertIn("__lista_t<long long>(1LL, 2LL)", codigo)
        self.assertIn("__lista_t<std::string>(", codigo)
        self.assertIn("__index(l, 0LL)", codigo)

    def test_promocao_para_double(self):
        codigo = cpp_usuario("var soma = 0;\nsoma = soma + 0.5;")
        self.assertIn("double soma;", codigo)

    def test_controle_de_fluxo(self):
        codigo = cpp_usuario("var i = 0;\nwhile (i < 3) { if (i == 1) { break; } i = i + 1; }")
        self.assertIn("while ((i < 3LL))", codigo)
        self.assertIn("break;", codigo)

    def test_funcao_e_classe_com_heranca(self):
        codigo = cpp_usuario("func f(x) { return x * 2; }\n"
                             "class P { var x = 0; func mover(d) { this.x = this.x + d; } }\n"
                             "class Q extends P { var y = 1; }\nvar p = new P();\np.mover(2);")
        self.assertIn("auto f(auto x)", codigo)
        self.assertIn("class Q : public P", codigo)
        self.assertIn("this->x = __add(this->x, d);", codigo)
        self.assertIn("p = std::make_shared<P>();", codigo)
        self.assertIn("p->mover(2LL);", codigo)

    def test_bloco_par_cria_uma_thread_por_comando(self):
        codigo = cpp_usuario("par { print(1); print(2); }")
        self.assertEqual(codigo.count("emplace_back"), 2)
        self.assertIn("t.join();", codigo)

    def test_fork_em_nucleo_e_join(self):
        codigo = cpp_usuario("func f(x) { return x * 2; }\nfork a = f(1) on core 2;\n"
                             "fork b = f(2);\nvar r = join a;\njoin b;")
        self.assertIn("auto a = __fork(2LL, [=]() { return f(1LL); });", codigo)
        self.assertIn("auto b = __fork(-1LL,", codigo)       # -1: nucleo escolhido pelo SO
        self.assertIn("auto r = a.get();", codigo)
        self.assertIn("b.wait();", codigo)

    def test_fork_remoto_gera_tabela_de_despacho(self):
        programa = 'func f(x) { return x * 2; }\nfork a = f(1) on host "127.0.0.1":5400;\nvar r = join a;'
        self.assertIn('__remoto<decltype(f(1LL))>(std::string("127.0.0.1"), 5400LL, 0, 1LL)',
                      cpp_usuario(programa))
        remoto = cpp_remoto(programa)
        self.assertIn("case 0:", remoto)
        self.assertIn("__des<long long>(l)", remoto)
        self.assertIn("__ASSINATURA_PROGRAMA", remoto)

    def test_assinatura_muda_com_o_programa(self):
        a = cpp_remoto("func f(x) { return x; }\nprint(f(1));")
        b = cpp_remoto("func f(x) { return x + 1; }\nprint(f(1));")
        assinatura = lambda t: t.split("__ASSINATURA_PROGRAMA = ")[1].split(";")[0]
        self.assertNotEqual(assinatura(a), assinatura(b))
        self.assertEqual(assinatura(a), assinatura(cpp_remoto("func f(x) { return x; }\nprint(f(1));")))


@unittest.skipUnless(shutil.which("g++"), "g++ nao encontrado")
class TestCompiladorGcc(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="minipar_gcc_")
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)

    def test_compila_e_executa(self):
        exe = C_CompiladorGcc(self.pasta).compilar(cpp('print("ola", 1 + 1);'), "ola")
        self.assertTrue(os.path.isfile(exe))
        self.assertTrue(os.path.isfile(os.path.join(self.pasta, "ola.cpp")))
        saida = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        self.assertEqual(saida.stdout, "ola 2\n")

    def test_cpp_invalido_vira_erro_de_geracao(self):
        with self.assertRaises(ErroGeracao) as ctx:
            C_CompiladorGcc(self.pasta).compilar("int main( { nao compila", "quebrado")
        self.assertEqual(ctx.exception.fase, "GERACAO")
        self.assertIn("Falha ao compilar", ctx.exception.mensagem)


if __name__ == "__main__":
    unittest.main()
