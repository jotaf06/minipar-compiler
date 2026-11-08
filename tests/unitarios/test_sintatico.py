"""
Testes de unidade do componente C_Sintatico (fase 2: tokens -> AST).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_sintatico -v
"""
import unittest

from apoio import ast, tokens
from ast_nodes import (
    Assignment, BinaryExpr, BoolExpr, ClassDecl, DoWhileStmt, ForkStmt, ForStmt, FuncCallExpr,
    FuncDecl, IdentifierExpr, IfStmt, IndexAssign, IndexExpr, JoinExpr, JoinStmt, ListLiteral,
    MatrixCreateExpr, MethodCall, NewExpr, NumberExpr, ParBlock, PrintStmt, Program,
    PropertyAccess, PropertyAssign, ReturnStmt, SeqBlock, StringExpr, UnaryExpr, VarDecl,
    WhileStmt,
)
from erros import ErroSintatico
from parser import C_Sintatico


def expr(texto):
    """AST da expressao em 'var _ = <texto>;'."""
    return ast(f"var _ = {texto};").statements[0].init_value


def forma(no):
    """Representacao compacta de uma expressao: (op esquerda direita)."""
    if isinstance(no, BinaryExpr):
        return f"({no.op} {forma(no.left)} {forma(no.right)})"
    if isinstance(no, UnaryExpr):
        return f"({no.op} {forma(no.operand)})"
    if isinstance(no, NumberExpr):
        return no.value
    if isinstance(no, IdentifierExpr):
        return no.name
    return type(no).__name__


class TestPrecedencia(unittest.TestCase):
    def test_aritmetica(self):
        self.assertEqual(forma(expr("1 + 2 * 3")), "(+ 1 (* 2 3))")
        self.assertEqual(forma(expr("(1 + 2) * 3")), "(* (+ 1 2) 3)")
        self.assertEqual(forma(expr("a // b % c")), "(% (// a b) c)")

    def test_associatividade_a_esquerda(self):
        self.assertEqual(forma(expr("10 - 4 - 3")), "(- (- 10 4) 3)")
        self.assertEqual(forma(expr("a / b / c")), "(/ (/ a b) c)")

    def test_unario(self):
        self.assertEqual(forma(expr("-a * b")), "(* (- a) b)")
        self.assertEqual(forma(expr("!a && b")), "(&& (! a) b)")

    def test_bit_a_bit_entre_comparacao_e_soma(self):
        # Mesma ordem do Python: | < ^ < & < shifts < + -
        self.assertEqual(forma(expr("a | b ^ c & d")), "(| a (^ b (& c d)))")
        self.assertEqual(forma(expr("x & 0x7F << 1 + 1")), "(& x (<< 0x7F (+ 1 1)))")
        self.assertEqual(forma(expr("a & b == c")), "(== (& a b) c)")

    def test_logicos(self):
        self.assertEqual(forma(expr("a || b && c")), "(|| a (&& b c))")
        self.assertEqual(forma(expr("a < b && b <= c")), "(&& (< a b) (<= b c))")


class TestComandos(unittest.TestCase):
    def test_declaracao_com_e_sem_tipo(self):
        p = ast('var x = 1;\nnumber y = 2;\nstring s = "a";\nvar z;')
        self.assertEqual([(d.name, d.type) for d in p.statements],
                         [("x", "var"), ("y", "number"), ("s", "string"), ("z", "var")])
        self.assertIsNone(p.statements[3].init_value)
        self.assertEqual([d.line for d in p.statements], [1, 2, 3, 4])

    def test_atribuicoes(self):
        p = ast("x = 1; v[0] = 2; obj.campo = 3; m[1][2] = 4;")
        self.assertIsInstance(p.statements[0], Assignment)
        self.assertIsInstance(p.statements[1], IndexAssign)
        self.assertIsInstance(p.statements[2], PropertyAssign)
        alvo = p.statements[3].target
        self.assertIsInstance(alvo, IndexExpr)
        self.assertIsInstance(alvo.object, IndexExpr)

    def test_if_else_aninhado(self):
        s = ast("if (a) { x = 1; } else if (b) { x = 2; } else { x = 3; }").statements[0]
        self.assertIsInstance(s, IfStmt)
        self.assertIsInstance(s.else_branch, IfStmt)
        self.assertIsInstance(s.else_branch.else_branch, SeqBlock)

    def test_lacos(self):
        p = ast("while (i < 3) { i = i + 1; }\n"
                "do { i = i - 1; } while (i > 0);\n"
                "for (var k = 0; k < 3; k = k + 1) { print(k); }\n"
                "for (var e in [1, 2]) { print(e); }")
        w, d, f, fin = p.statements
        self.assertIsInstance(w, WhileStmt)
        self.assertIsInstance(d, DoWhileStmt)
        self.assertIsInstance(f, ForStmt)
        self.assertEqual((f.initializer.name, forma(f.condition)), ("k", "(< k 3)"))
        self.assertIsInstance(f.increment, Assignment)
        self.assertEqual(fin.iterator_name, "e")
        self.assertIsInstance(fin.iterable, ListLiteral)

    def test_funcao_com_parametros_tipados(self):
        f = ast("func soma(number a, b) { return a + b; }").statements[0]
        self.assertIsInstance(f, FuncDecl)
        self.assertEqual(f.params, ["a", "b"])
        self.assertIsInstance(f.body.statements[0], ReturnStmt)

    def test_classe_com_heranca(self):
        c = ast("class Cao extends Animal { var nome = \"\"; func latir() { print(\"au\"); } }").statements[0]
        self.assertIsInstance(c, ClassDecl)
        self.assertEqual((c.name, c.superclass), ("Cao", "Animal"))
        self.assertEqual([a.name for a in c.attributes], ["nome"])
        self.assertEqual([m.name for m in c.methods], ["latir"])

    def test_objetos_metodos_e_atributos(self):
        p = ast("var o = new Ponto(1, 2);\no.mover(3);\nprint(o.x);")
        self.assertIsInstance(p.statements[0].init_value, NewExpr)
        self.assertIsInstance(p.statements[1], MethodCall)
        self.assertIsInstance(p.statements[2].arguments[0], PropertyAccess)

    def test_seq_par_e_canais(self):
        p = ast('seq { var c = c_channel("127.0.0.1", 5000);\n'
                'par { send(c, "oi"); { var m = receive(c); } } }')
        seq = p.statements[0]
        self.assertIsInstance(seq, SeqBlock)
        self.assertIsInstance(seq.statements[1], ParBlock)

    def test_literais_de_lista_e_matriz(self):
        lista = expr("[1, \"a\", true, [2]]")
        self.assertEqual([type(e) for e in lista.elements], [NumberExpr, StringExpr, BoolExpr, ListLiteral])
        self.assertIsInstance(expr("matrix(2, 3, 0)"), MatrixCreateExpr)
        self.assertEqual(expr("[]").elements, [])

    def test_print_com_varios_argumentos(self):
        s = ast('print("a", 1, x);').statements[0]
        self.assertIsInstance(s, PrintStmt)
        self.assertEqual(len(s.arguments), 3)


class TestForkJoin(unittest.TestCase):
    def test_fork_em_nucleo(self):
        s = ast("fork t = f(1, 2) on core 0;").statements[0]
        self.assertIsInstance(s, ForkStmt)
        self.assertEqual(s.handle, "t")
        self.assertIsInstance(s.call, FuncCallExpr)
        self.assertEqual(s.core.value, "0")
        self.assertIsNone(s.host)

    def test_fork_sem_alocacao_e_de_metodo(self):
        s = ast("fork t = obj.processar(x);").statements[0]
        self.assertIsInstance(s.call, MethodCall)
        self.assertIsNone(s.core)

    def test_fork_em_outro_computador(self):
        s = ast('fork t = f(x) on host "10.0.0.2":5400;').statements[0]
        self.assertEqual((s.host.value, s.porta.value), ("10.0.0.2", "5400"))
        self.assertIsNone(s.core)

    def test_join_comando_e_expressao(self):
        p = ast("join;\njoin t1, t2;\nvar r = join t1 + join t2;")
        self.assertEqual(p.statements[0].handles, [])
        self.assertEqual(p.statements[1].handles, ["t1", "t2"])
        soma = p.statements[2].init_value
        self.assertIsInstance(soma.left, JoinExpr)
        self.assertEqual(soma.right.handle, "t2")


class TestErrosSintaticos(unittest.TestCase):
    def assertErro(self, codigo, trecho, linha=None, coluna=None):
        with self.assertRaises(ErroSintatico) as ctx:
            ast(codigo)
        self.assertIn(trecho, ctx.exception.mensagem)
        if linha is not None:
            self.assertEqual(ctx.exception.linha, linha)
        if coluna is not None:
            self.assertEqual(ctx.exception.coluna, coluna)

    def test_ponto_e_virgula_faltando_aponta_fim_do_token_anterior(self):
        self.assertErro("var x = 10\nprint(x);", "", linha=1, coluna=11)

    def test_parentese_nao_fechado(self):
        self.assertErro("print((1 + 2);", "Esperado ')'")

    def test_fork_sem_chamada(self):
        self.assertErro("fork t = 1 + 2;", "fork exige uma chamada", linha=1, coluna=10)

    def test_on_sem_core_ou_host(self):
        self.assertErro("fork t = f() on 2;", "Esperado 'core' ou 'host'")

    def test_expressao_isolada(self):
        self.assertErro("x + 1;", "Expressao isolada")

    def test_instrucao_nao_reconhecida(self):
        self.assertErro("var a = 1;\n);", "Instrucao nao reconhecida", linha=2, coluna=1)

    def test_classe_com_membro_invalido(self):
        self.assertErro("class A { print(1); }", "Esperado 'var' ou 'func'")

    def test_atribuicao_a_expressao(self):
        self.assertErro("f() = 3;", "Atribuicao invalida")


class TestComponente(unittest.TestCase):
    def test_programa_vazio(self):
        p = ast("")
        self.assertIsInstance(p, Program)
        self.assertEqual(p.statements, [])

    def test_reutilizacao_do_componente(self):
        sintatico = C_Sintatico()
        sintatico.analisar(tokens("var a = 1; var b = 2;"))
        p = sintatico.analisar(tokens("print(1);"))
        self.assertEqual(len(p.statements), 1)


if __name__ == "__main__":
    unittest.main()
