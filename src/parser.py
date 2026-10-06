from entities import CompileError, TYPE_NAMES
from ast_nodes import *


def describe(token) -> str:
    if token.kind == "NL":
        return "end of line"
    if token.kind == "EOF":
        return "end of file"
    if token.kind == "TAB":
        return "indentation"
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

    def indent_count(self):
        n = 0
        while self.is_token("TAB", k=n):
            n += 1
        return n

    def parse_program(self):
        first = self.peek()
        body = []
        while True:
            if self.is_token("EOF"):
                self.error("expected 'exit', found end of file")
            if self.is_token("TAB"):
                self.error("unexpected indentation")
            if self.is_token("keyword", "exit"):
                body.append(self.parse_exit())
                break
            body.append(self.parse_statement(0))
        if not self.is_token("EOF"):
            self.error(f"unexpected {describe(self.peek())} after 'exit'")
        return ProgramNode(first.line, first.col, body)

    def parse_statement(self, depth):
        token = self.peek()
        if token.kind == "keyword":
            if token.text in TYPE_NAMES:
                return self.parse_decl()
            if token.text == "if":
                return self.parse_if(depth)
            if token.text == "while":
                return self.parse_while(depth)
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

    def parse_if(self, depth):
        keyword = self.eat()
        cond = self.parse_expr()
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        then_block = self.parse_block(depth + 1)
        else_block = None
        if self.indent_count() == depth and self.is_token("keyword", "else", k=depth):
            for _ in range(depth):
                self.eat()
            self.eat()
            self.expect("colon", ":")
            self.expect("NL", what="end of line")
            else_block = self.parse_block(depth + 1)
        return IfStmt(keyword.line, keyword.col, cond, then_block, else_block)

    def parse_while(self, depth):
        keyword = self.eat()
        cond = self.parse_expr()
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        body = self.parse_block(depth + 1)
        return WhileStmt(keyword.line, keyword.col, cond, body)

    def parse_block(self, depth):
        first = self.peek()
        body = []
        while True:
            count = self.indent_count()
            if count < depth:
                break
            if count > depth:
                self.error("unexpected indentation", self.peek(depth))
            for _ in range(depth):
                self.eat()
            if self.is_token("keyword", "exit"):
                body.append(self.parse_exit())
                if self.indent_count() >= depth:
                    self.error("statement after 'exit' in block", self.peek(self.indent_count()))
                break
            body.append(self.parse_statement(depth))
        return BlockNode(first.line, first.col, body)

    def parse_exit(self):
        keyword = self.eat()
        value = self.parse_expr()
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
