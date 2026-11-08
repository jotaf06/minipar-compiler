"""
Testes de unidade do componente C_Lexico (fase 1: codigo-fonte -> tokens).

Execucao (na raiz do projeto):
    .venv/bin/python -m unittest tests.unitarios.test_lexico -v
"""
import unittest

from apoio import tokens, tipos, TokenType as T
from erros import ErroLexico


class TestLexico(unittest.TestCase):
    def test_palavras_chave_e_identificadores(self):
        self.assertEqual(
            tipos("var func class extends new if else while do for in return nome _x2"),
            [T.VAR, T.FUNC, T.CLASS, T.EXTENDS, T.NEW, T.IF, T.ELSE, T.WHILE, T.DO, T.FOR,
             T.IN, T.RETURN, T.IDENTIFIER, T.IDENTIFIER])

    def test_palavras_chave_de_fork_join(self):
        self.assertEqual(tipos('fork t = f() on core 0; join t; on host "ip":1'),
                         [T.FORK, T.IDENTIFIER, T.ASSIGN, T.IDENTIFIER, T.LPAREN, T.RPAREN,
                          T.ON, T.CORE, T.NUMBER, T.SEMICOLON, T.JOIN, T.IDENTIFIER, T.SEMICOLON,
                          T.ON, T.HOST, T.STRING_LITERAL, T.COLON, T.NUMBER])

    def test_literais(self):
        lista = tokens('42 3.14 0x7FFFFFFF "texto" true false')
        self.assertEqual([(t.type, t.lexeme) for t in lista[:-1]], [
            (T.NUMBER, "42"), (T.NUMBER, "3.14"), (T.NUMBER, "0x7FFFFFFF"),
            (T.STRING_LITERAL, "texto"), (T.BOOL_LITERAL, "true"), (T.BOOL_LITERAL, "false")])

    def test_tipos_declarados(self):
        self.assertEqual(tipos("number int string bool void list dict"), [T.TYPE] * 7)

    def test_operadores_de_dois_caracteres(self):
        self.assertEqual(tipos("== != <= >= && || // << >>"),
                         [T.EQ, T.NEQ, T.LTE, T.GTE, T.AND, T.OR, T.DSLASH, T.SHL, T.SHR])

    def test_operadores_de_um_caractere(self):
        self.assertEqual(tipos("+ - * / % = < > ! & | ^ ( ) { } [ ] ; : , ."),
                         [T.PLUS, T.MINUS, T.STAR, T.SLASH, T.MOD, T.ASSIGN, T.LT, T.GT, T.NOT,
                          T.BIT_AND, T.BIT_OR, T.BIT_XOR, T.LPAREN, T.RPAREN, T.LBRACE,
                          T.RBRACE, T.LBRACKET, T.RBRACKET, T.SEMICOLON, T.COLON, T.COMMA, T.DOT])

    def test_escapes_em_string(self):
        lista = tokens(r'"a\nb\t\"c\"\\"')
        self.assertEqual(lista[0].lexeme, 'a\nb\t"c"\\')

    def test_comentarios_e_espacos_sao_ignorados(self):
        self.assertEqual(tipos("# comentario inteiro\nvar x = 1; # fim de linha\n\t  "),
                         [T.VAR, T.IDENTIFIER, T.ASSIGN, T.NUMBER, T.SEMICOLON])

    def test_linha_e_coluna_de_inicio_e_fim(self):
        lista = tokens('var x = 10;\n  print("oi");')
        x, dez = lista[1], lista[3]
        self.assertEqual((x.line, x.col, x.end_line, x.end_col), (1, 5, 1, 6))
        self.assertEqual((dez.line, dez.col, dez.end_col), (1, 9, 11))
        texto = lista[7]
        self.assertEqual((texto.lexeme, texto.line, texto.col, texto.end_col), ("oi", 2, 9, 13))

    def test_fim_de_arquivo(self):
        lista = tokens("var a = 1;\n")
        self.assertEqual(lista[-1].type, T.END_OF_FILE)
        self.assertEqual(tokens("")[0].type, T.END_OF_FILE)

    def test_acesso_a_metodo(self):
        # O ponto do acesso a metodo vira um token DOT separado
        self.assertEqual(tipos("obj.metodo()"),
                         [T.IDENTIFIER, T.DOT, T.IDENTIFIER, T.LPAREN, T.RPAREN])

    # ---- Erros lexicos: excecao com linha e coluna ----
    def test_caractere_invalido(self):
        with self.assertRaises(ErroLexico) as ctx:
            tokens("var x = 1;\nvar y = @;")
        self.assertEqual((ctx.exception.linha, ctx.exception.coluna), (2, 9))
        self.assertIn("Caractere invalido", ctx.exception.mensagem)

    def test_string_nao_fechada(self):
        with self.assertRaises(ErroLexico) as ctx:
            tokens('print("sem fim);')
        self.assertEqual((ctx.exception.linha, ctx.exception.coluna), (1, 7))
        self.assertIn("String nao fechada", ctx.exception.mensagem)

    def test_hexadecimal_sem_digitos(self):
        with self.assertRaises(ErroLexico):
            tokens("var x = 0x;")

    def test_reutilizacao_do_componente(self):
        # O mesmo C_Lexico analisa varios programas (a posicao e reiniciada)
        from lexer import C_Lexico
        lexico = C_Lexico()
        lexico.analisar("var a = 1;\nvar b = 2;")
        segundo = lexico.analisar("x")
        self.assertEqual((segundo[0].line, segundo[0].col), (1, 1))


if __name__ == "__main__":
    unittest.main()
