from __future__ import annotations
from typing import List, Optional
from lexer import Token, TokenType
from erros import ErroSintatico
from interfaces import ISintatico
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, 
    BinaryExpr, UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign,
    ForkStmt, JoinStmt, JoinExpr
)

class C_Sintatico(ISintatico):
    """Componente Analisador Sintatico - implementa ISintatico.

    Parser descendente recursivo: cada producao da gramatica BNF tem um
    metodo _parse_*. A precedencia de operadores vem da cadeia
    or -> and -> comparacao -> | -> ^ -> & -> (<<,>>) -> termo (+,-) -> fator (*,/,//,%)
    -> unario -> primario.
    """

    def __init__(self, tokens: Optional[List[Token]] = None) -> None:
        self._tokens = tokens or []
        self._pos = 0

    # ---- Interface ISintatico ----
    def analisar(self, tokens: List[Token]) -> Program:
        self._tokens = tokens
        self._pos = 0
        return self.parse()

    def _peek(self) -> Token:
        if self._pos >= len(self._tokens): return self._tokens[-1]
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        if self._pos < len(self._tokens): self._pos += 1
        return token

    def _match(self, token_type: TokenType) -> bool:
        if self._peek().type == token_type:
            self._advance()
            return True
        return False

    def _consume(self, token_type: TokenType, err_msg: str) -> Token:
        if self._peek().type == token_type: return self._advance()
        tok = self._peek()
        encontrado = "fim do arquivo" if tok.type == TokenType.END_OF_FILE else repr(tok.lexeme)
        if token_type == TokenType.SEMICOLON and self._pos > 0:
            # O ';' ausente pertence ao fim do token anterior (normalmente na linha de cima),
            # e nao ao proximo token, que e onde o parser percebe a falta.
            ant = self._tokens[self._pos - 1]
            raise ErroSintatico(f"{err_msg} (encontrado: {encontrado})", ant.end_line, ant.end_col)
        raise ErroSintatico(f"{err_msg} (encontrado: {encontrado})", tok.line, tok.col)

    def _parse_var_decl(self, declared_type: str = "var", require_semicolon: bool = True) -> ASTNode:
        node = VarDecl(name="")
        node.line = self._peek().line
        node.type = declared_type
        node.name = self._consume(TokenType.IDENTIFIER, "Esperado nome da variavel").lexeme
        if self._match(TokenType.ASSIGN):
            node.init_value = self._parse_expression()
        if require_semicolon:
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos declaracao de variavel")
        return node

    def _parse_assignment_tail(self, target: ASTNode, require_semicolon: bool = True) -> ASTNode:
        val = self._parse_expression()
        if require_semicolon:
            self._consume(TokenType.SEMICOLON, "Esperado ';'")
        if isinstance(target, IdentifierExpr): return Assignment(name=target.name, value=val, line=target.line)
        if isinstance(target, PropertyAccess): return PropertyAssign(object=target.object, property_name=target.property_name, value=val, line=target.line)
        if isinstance(target, IndexExpr): return IndexAssign(target=target, value=val, line=target.line)
        raise ErroSintatico("Atribuicao invalida: o lado esquerdo deve ser variavel, atributo ou indice", target.line)

    def _parse_print_stmt(self) -> ASTNode:
        node = PrintStmt()
        node.line = self._peek().line
        self._consume(TokenType.LPAREN, "Esperado '(' apos print")
        if self._peek().type != TokenType.RPAREN:
            node.arguments.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                node.arguments.append(self._parse_expression())
        self._consume(TokenType.RPAREN, "Esperado ')' apos argumentos do print")
        self._consume(TokenType.SEMICOLON, "Esperado ';' apos print")
        return node

    def _parse_send_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos send")
        channel = self._parse_expression()
        self._consume(TokenType.COMMA, "Esperado ',' entre canal e mensagem")
        message = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')'")
        self._consume(TokenType.SEMICOLON, "Esperado ';'")
        return SendStmt(channel=channel, message=message, line=line)

    def _parse_seq_block(self) -> ASTNode:
        node = SeqBlock(line=self._peek().line)   # linha do '{' (para destacar no editor)
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            node.statements.append(self._parse_statement())
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco")
        return node

    def _parse_par_block(self) -> ASTNode:
        node = ParBlock(line=self._peek().line)
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco PAR")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            node.statements.append(self._parse_statement())
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco PAR")
        return node

    def _parse_if_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'if'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao do 'if'")
        then_branch = self._parse_statement()
        else_branch = self._parse_statement() if self._match(TokenType.ELSE) else None
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch, line=line)

    def _parse_while_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        body = self._parse_statement()
        return WhileStmt(condition=condition, body=body, line=line)

    def _parse_do_while_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        body = self._parse_statement()
        self._consume(TokenType.WHILE, "Esperado 'while' apos bloco do")
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        self._match(TokenType.SEMICOLON)
        return DoWhileStmt(body=body, condition=condition, line=line)

    def _parse_for_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'for'")
        initializer = condition = increment = iterator_name = iterable = None

        if self._match(TokenType.VAR):
            name_tok = self._consume(TokenType.IDENTIFIER, "Esperado variavel do for")
            if self._match(TokenType.IN):
                iterator_name = name_tok.lexeme
                iterable = self._parse_expression()
                self._consume(TokenType.RPAREN, "Esperado ')' apos iteravel")
                body = self._parse_statement()
                return ForStmt(None, None, None, body, iterator_name, iterable, line)
            initializer = VarDecl(name=name_tok.lexeme, type="var", line=name_tok.line)
            if self._match(TokenType.ASSIGN):
                initializer.init_value = self._parse_expression()
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            initializer = self._parse_var_decl(type_tok.lexeme, require_semicolon=False)
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif not self._match(TokenType.SEMICOLON):
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                initializer = self._parse_assignment_tail(target, require_semicolon=False)
            else:
                initializer = target
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")

        if not self._match(TokenType.SEMICOLON):
            condition = self._parse_expression()
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos condicao do for")

        if self._peek().type != TokenType.RPAREN:
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                increment = self._parse_assignment_tail(target, require_semicolon=False)
            else:
                increment = target
        self._consume(TokenType.RPAREN, "Esperado ')' apos for")
        body = self._parse_statement()
        return ForStmt(initializer, condition, increment, body, line=line)

    def _parse_class_decl(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe").lexeme
        superclass = self._consume(TokenType.IDENTIFIER, "Esperado nome da superclasse").lexeme if self._match(TokenType.EXTENDS) else None
        self._consume(TokenType.LBRACE, "Esperado '{' na classe")
        attrs, methods = [], []
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            if self._match(TokenType.VAR): attrs.append(self._parse_var_decl())
            elif self._match(TokenType.FUNC): methods.append(self._parse_func_decl())
            else:
                tok = self._peek()
                raise ErroSintatico(f"Esperado 'var' ou 'func' na definicao da classe (encontrado: {tok.lexeme!r})", tok.line, tok.col)
        self._consume(TokenType.RBRACE, "Esperado '}' no fim da classe")
        return ClassDecl(name=name, superclass=superclass, attributes=attrs, methods=methods, line=line)

    def _parse_func_decl(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da funcao").lexeme
        self._consume(TokenType.LPAREN, "Esperado '('")
        params = []
        if self._peek().type != TokenType.RPAREN:
            if self._peek().type == TokenType.TYPE:
                self._advance()
            params.append(self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme)
            while self._match(TokenType.COMMA):
                if self._peek().type == TokenType.TYPE:
                    self._advance()
                params.append(self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme)
        self._consume(TokenType.RPAREN, "Esperado ')'")
        body = self._parse_seq_block()
        return FuncDecl(name=name, params=params, body=body, line=line)

    def _parse_return_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        value = None if self._peek().type == TokenType.SEMICOLON else self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return ReturnStmt(value=value, line=line)

    # <fork_stmt> ::= "fork" IDENT "=" <chamada> [ "on" ( "core" <expr> | "host" <expr> ":" <expr> ) ] ";"
    def _parse_fork_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        handle = self._consume(TokenType.IDENTIFIER, "Esperado nome da tarefa apos 'fork'").lexeme
        self._consume(TokenType.ASSIGN, "Esperado '=' apos o nome da tarefa")
        call_tok = self._peek()
        call = self._parse_expression()
        if not isinstance(call, (FuncCallExpr, MethodCall)):
            raise ErroSintatico("fork exige uma chamada de funcao ou metodo (ex.: fork t = f(x);)",
                                call_tok.line, call_tok.col)
        core = host = porta = None
        if self._match(TokenType.ON):
            if self._match(TokenType.HOST):
                # <alocacao> ::= "on" "host" <expressao> ":" <expressao>
                host = self._parse_expression()
                self._consume(TokenType.COLON, "Esperado ':' entre o endereco e a porta (ex.: on host \"127.0.0.1\":5400)")
                porta = self._parse_expression()
            else:
                # <alocacao> ::= "on" "core" <expressao>
                self._consume(TokenType.CORE, "Esperado 'core' ou 'host' apos 'on' (ex.: on core 0)")
                core = self._parse_expression()
        self._consume(TokenType.SEMICOLON, "Esperado ';' apos o fork")
        return ForkStmt(handle=handle, call=call, core=core, line=line, host=host, porta=porta)

    # <join_stmt> ::= "join" [ IDENT { "," IDENT } ] ";"
    def _parse_join_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        handles = []
        if self._peek().type == TokenType.IDENTIFIER:
            handles.append(self._advance().lexeme)
            while self._match(TokenType.COMMA):
                handles.append(self._consume(TokenType.IDENTIFIER, "Esperado nome de tarefa apos ','").lexeme)
        self._consume(TokenType.SEMICOLON, "Esperado ';' apos o join")
        return JoinStmt(handles=handles, line=line)

    def _parse_statement(self) -> ASTNode:
        if self._match(TokenType.CLASS): return self._parse_class_decl()
        if self._match(TokenType.FUNC): return self._parse_func_decl()
        if self._match(TokenType.RETURN): return self._parse_return_stmt()
        if self._match(TokenType.BREAK):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return BreakStmt(line=line)
        if self._match(TokenType.CONTINUE):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return ContinueStmt(line=line)
        if self._match(TokenType.VAR): return self._parse_var_decl()
        if self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            return self._parse_var_decl(type_tok.lexeme)
        if self._match(TokenType.SEQ) or self._peek().type == TokenType.LBRACE: 
            if self._peek().type == TokenType.SEQ: self._advance()
            return self._parse_seq_block()
        if self._match(TokenType.PAR): return self._parse_par_block()
        if self._match(TokenType.PRINT): return self._parse_print_stmt()
        if self._match(TokenType.SEND): return self._parse_send_stmt()
        if self._match(TokenType.IF): return self._parse_if_stmt()
        if self._match(TokenType.WHILE): return self._parse_while_stmt()
        if self._match(TokenType.DO): return self._parse_do_while_stmt()
        if self._match(TokenType.FOR): return self._parse_for_stmt()
        if self._match(TokenType.FORK): return self._parse_fork_stmt()
        if self._match(TokenType.JOIN): return self._parse_join_stmt()

        if self._peek().type in (TokenType.IDENTIFIER, TokenType.THIS, TokenType.NEW, TokenType.RECEIVE, TokenType.INPUT, TokenType.C_CHANNEL, TokenType.MATRIX, TokenType.LBRACKET):
            expr = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                return self._parse_assignment_tail(expr)
            elif isinstance(expr, (MethodCall, FuncCallExpr)):
                self._consume(TokenType.SEMICOLON, "Esperado ';'")
                return expr
            raise ErroSintatico("Expressao isolada nao e uma instrucao valida (esperado atribuicao ou chamada)", expr.line)

        tok = self._peek()
        raise ErroSintatico(f"Instrucao nao reconhecida: {tok.lexeme!r}", tok.line, tok.col)

    def _parse_expression(self) -> ASTNode:
        return self._parse_or()

    def _parse_or(self) -> ASTNode:
        expr = self._parse_and()
        while self._match(TokenType.OR):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_and(), line=op_tok.line)
        return expr

    def _parse_and(self) -> ASTNode:
        expr = self._parse_comparison()
        while self._match(TokenType.AND):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_comparison(), line=op_tok.line)
        return expr

    def _parse_comparison(self) -> ASTNode:
        expr = self._parse_bit_or()
        while self._peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_bit_or())
            node.line = op_tok.line
            expr = node
        return expr

    # Operadores bit a bit com a precedencia do Python (todos abaixo da comparacao):
    #   comparacao < | < ^ < & < (<< >>) < (+ -) < (* / // %)
    # Assim "x & 0xFF == 0" significa "(x & 0xFF) == 0", como no Python.
    def _parse_binary_level(self, tipos, proximo) -> ASTNode:
        expr = proximo()
        while self._peek().type in tipos:
            op_tok = self._advance()
            expr = BinaryExpr(op=op_tok.lexeme, left=expr, right=proximo(), line=op_tok.line)
        return expr

    def _parse_bit_or(self) -> ASTNode:
        return self._parse_binary_level((TokenType.BIT_OR,), self._parse_bit_xor)

    def _parse_bit_xor(self) -> ASTNode:
        return self._parse_binary_level((TokenType.BIT_XOR,), self._parse_bit_and)

    def _parse_bit_and(self) -> ASTNode:
        return self._parse_binary_level((TokenType.BIT_AND,), self._parse_shift)

    def _parse_shift(self) -> ASTNode:
        return self._parse_binary_level((TokenType.SHL, TokenType.SHR), self._parse_term)

    def _parse_term(self) -> ASTNode:
        expr = self._parse_factor()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_factor())
            node.line = op_tok.line
            expr = node
        return expr

    def _parse_factor(self) -> ASTNode:
        expr = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.DSLASH, TokenType.MOD):
            op_tok = self._advance()
            node = BinaryExpr(op=op_tok.lexeme, left=expr, right=self._parse_unary())
            node.line = op_tok.line
            expr = node
        return expr

    def _parse_unary(self) -> ASTNode:
        if self._peek().type in (TokenType.MINUS, TokenType.PLUS, TokenType.NOT):
            op_tok = self._advance()
            node = UnaryExpr(op=op_tok.lexeme, operand=self._parse_unary())
            node.line = op_tok.line
            return node
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()
        node = None

        if self._match(TokenType.JOIN):
            handle = self._consume(TokenType.IDENTIFIER, "Esperado nome da tarefa apos 'join'").lexeme
            return JoinExpr(handle=handle, line=tok.line)
        if self._match(TokenType.MATRIX):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos matrix")
            rows = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            cols = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            init_val = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = MatrixCreateExpr(rows=rows, cols=cols, init_value=init_val, line=line)
        elif self._match(TokenType.LBRACKET):
            line = tok.line
            elements = []
            if self._peek().type != TokenType.RBRACKET:
                elements.append(self._parse_expression())
                while self._match(TokenType.COMMA): elements.append(self._parse_expression())
            self._consume(TokenType.RBRACKET, "Esperado ']'")
            node = ListLiteral(elements=elements, line=line)
        elif self._match(TokenType.C_CHANNEL):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos c_channel")
            ip = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ',' entre ip e porta")
            port = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = CChannelExpr(ip=ip, port=port, line=line)
        elif self._match(TokenType.RECEIVE):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos receive")
            channel = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = ReceiveExpr(channel=channel, line=line)
        elif self._match(TokenType.INPUT):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos input")
            prompt = None if self._peek().type == TokenType.RPAREN else self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')' apos input")
            node = InputExpr(prompt=prompt, line=line)
        elif self._match(TokenType.NEW):
            line = tok.line
            class_name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe").lexeme
            self._consume(TokenType.LPAREN, "Esperado '('")
            args = []
            if self._peek().type != TokenType.RPAREN:
                args.append(self._parse_expression())
                while self._match(TokenType.COMMA): args.append(self._parse_expression())
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = NewExpr(class_name=class_name, arguments=args, line=line)
        elif self._match(TokenType.THIS):
            node = ThisExpr(line=tok.line)
        elif self._match(TokenType.NUMBER):
            node = NumberExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.STRING_LITERAL):
            node = StringExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.BOOL_LITERAL):
            node = BoolExpr(value=(tok.lexeme == "true"), line=tok.line)
        elif self._match(TokenType.IDENTIFIER):
            name = tok.lexeme
            if self._match(TokenType.LPAREN):
                args = []
                if self._peek().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA): args.append(self._parse_expression())
                self._consume(TokenType.RPAREN, "Esperado ')'")
                node = FuncCallExpr(name=name, arguments=args, line=tok.line)
            else:
                node = IdentifierExpr(name=name, line=tok.line)
        elif self._match(TokenType.LPAREN):
            node = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
        else:
            raise ErroSintatico(f"Expressao esperada (encontrado: {tok.lexeme!r})", tok.line, tok.col)

        while True:
            if self._match(TokenType.DOT):
                prop_tok = self._consume(TokenType.IDENTIFIER, "Esperado identificador apos '.'")
                if self._match(TokenType.LPAREN):
                    args = []
                    if self._peek().type != TokenType.RPAREN:
                        args.append(self._parse_expression())
                        while self._match(TokenType.COMMA): args.append(self._parse_expression())
                    self._consume(TokenType.RPAREN, "Esperado ')'")
                    node = MethodCall(object=node, method_name=prop_tok.lexeme, arguments=args, line=prop_tok.line)
                else:
                    node = PropertyAccess(object=node, property_name=prop_tok.lexeme, line=prop_tok.line)
            elif self._match(TokenType.LBRACKET):
                idx_tok = self._tokens[self._pos - 1]
                idx = self._parse_expression()
                self._consume(TokenType.RBRACKET, "Esperado ']'")
                node = IndexExpr(object=node, index=idx, line=idx_tok.line)
            else:
                break

        return node

    def parse(self) -> Program:
        prog = Program()
        while self._peek().type != TokenType.END_OF_FILE:
            stmt = self._parse_statement()
            if stmt: prog.statements.append(stmt)
        return prog
