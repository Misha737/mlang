from entities import CompileError, TYPE_NAMES
from ast_nodes import *


def describe(token) -> str:
    if token.kind == "NL":
        return "end of line"
    if token.kind == "EOF":
        return "end of file"
    if token.kind == "INDENT":
        return "indentation"
    if token.kind == "DEDENT":
        return "end of block"
    return repr(token.text)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, k=0):
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

    def eat(self):
        token = self.peek()
        if token.kind != "EOF":
            self.pos += 1
        return token

    def is_token(self, kind, text=None, k=0):
        token = self.peek(k)
        return token.kind == kind and (text is None or token.text == text)

    def error(self, message, token=None):
        token = token or self.peek()
        raise CompileError(f"{token.line}:{token.col}: {message}")

    def expect(self, kind, text=None, what=None):
        if not self.is_token(kind, text):
            self.error(f"expected {what or repr(text) or kind}, found {describe(self.peek())}")
        return self.eat()

    def parse_program(self):
        first = self.peek()
        body = []
        while True:
            if self.is_token("EOF"):
                self.error("expected 'exit', found end of file")
            if self.is_token("INDENT"):
                self.error("unexpected indentation")
            if self.is_token("keyword", "exit"):
                body.append(self.parse_exit(require_nl=False))
                break
            body.append(self.parse_statement())
        if self.is_token("NL"):
            self.eat()
        if not self.is_token("EOF"):
            self.error(f"unexpected {describe(self.peek())} after 'exit'")
        return ProgramNode(first.line, first.col, body)

    def parse_statement(self):
        token = self.peek()
        if token.kind == "keyword":
            if token.text in TYPE_NAMES:
                return self.parse_decl()
            if token.text == "if":
                return self.parse_if()
            if token.text == "while":
                return self.parse_while()
        elif token.kind == "ident":
            return self.parse_assign()
        self.error(f"unexpected {describe(token)}, expected a statement")

    def parse_decl(self):
        type_token = self.eat()
        is_const = False
        if self.is_token("keyword", "const"):
            self.eat()
            is_const = True
        name = self.expect("ident", what="identifier")
        init = None
        if self.is_token("operator", "="):
            self.eat()
            init = self.parse_expr()
        self.expect("NL", what="end of line")
        return DeclStmt(type_token.line, type_token.col, type_token.text, is_const, name.text, init)

    def parse_assign(self):
        name = self.eat()
        self.expect("operator", "=")
        value = self.parse_expr()
        self.expect("NL", what="end of line")
        return AssignStmt(name.line, name.col, name.text, value)

    def parse_if(self):
        keyword = self.eat()
        cond = self.parse_expr()
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        then_block = self.parse_block()
        else_block = None
        if self.is_token("keyword", "else"):
            self.eat()
            self.expect("colon", ":")
            self.expect("NL", what="end of line")
            else_block = self.parse_block()
        return IfStmt(keyword.line, keyword.col, cond, then_block, else_block)

    def parse_while(self):
        keyword = self.eat()
        cond = self.parse_expr()
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        body = self.parse_block()
        return WhileStmt(keyword.line, keyword.col, cond, body)

    def parse_block(self):
        first = self.peek()
        if not self.is_token("INDENT"):
            self.error("block must contain at least one statement", first)
        self.eat()
        body = []
        while not self.is_token("DEDENT"):
            if self.is_token("INDENT"):
                self.error("unexpected indentation")
            if self.is_token("keyword", "exit"):
                body.append(self.parse_exit())
                if not self.is_token("DEDENT"):
                    self.error("statement after 'exit' in block")
                break
            body.append(self.parse_statement())
        self.eat()
        return BlockNode(first.line, 1, body)

    def parse_exit(self, require_nl=True):
        keyword = self.eat()
        value = self.parse_expr()
        if require_nl:
            self.expect("NL", what="end of line")
        return ExitStmt(keyword.line, keyword.col, value)

    def parse_expr(self):
        left = self.parse_arith()
        if self.is_token("operator", "==") or self.is_token("operator", "!="):
            op = self.eat()
            right = self.parse_arith()
            return BinaryExpr(op.line, op.col, op.text, left, right)
        return left

    def parse_arith(self):
        left = self.parse_term()
        while self.is_token("operator", "+") or self.is_token("operator", "-"):
            op = self.eat()
            right = self.parse_term()
            left = BinaryExpr(op.line, op.col, op.text, left, right)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.is_token("operator", "*"):
            op = self.eat()
            right = self.parse_factor()
            left = BinaryExpr(op.line, op.col, op.text, left, right)
        return left

    def parse_factor(self):
        token = self.peek()
        if token.kind == "number":
            self.eat()
            return NumberExpr(token.line, token.col, token.text)
        if token.kind == "keyword" and token.text in ("true", "false"):
            self.eat()
            return BoolExpr(token.line, token.col, token.text == "true")
        if token.kind == "ident":
            self.eat()
            return IdentExpr(token.line, token.col, token.text)
        if token.kind == "operator" and token.text == "!":
            self.eat()
            return UnaryExpr(token.line, token.col, "!", self.parse_factor())
        self.error(f"expected expression, found {describe(token)}")


def parse(tokens):
    return Parser(tokens).parse_program()
