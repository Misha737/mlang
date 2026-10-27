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
        structs = []
        functions = []
        statements = []
        while self.is_token("keyword", "struct"):
            structs.append(self.parse_struct())
        while self.is_function_start():
            functions.append(self.parse_function())
        while True:
            if self.is_token("EOF"):
                self.error("expected 'exit', found end of file")
            if self.is_token("INDENT"):
                self.error("unexpected indentation")
            if self.is_token("keyword", "exit"):
                exit = self.parse_exit(require_nl=False)
                break
            statements.append(self.parse_statement())
        if self.is_token("NL"):
            self.eat()
        if not self.is_token("EOF"):
            self.error(f"unexpected {describe(self.peek())} after 'exit'")
        return ProgramNode(first.line, first.col, structs, functions, statements, exit)

    def parse_statement(self):
        token = self.peek()
        if token.kind == "keyword":
            if token.text in TYPE_NAMES:
                return self.parse_decl()
            if token.text == "if":
                return self.parse_if()
            if token.text == "while":
                return self.parse_while()
            if token.text == "print":
                return self.parse_print()
        elif token.kind == "ident":
            if self.is_token("ident", k=1):
                return self.parse_decl()
            return self.parse_assign()
        self.error(f"unexpected {describe(token)}, expected a statement")

    def parse_decl(self):
        type_token = self.parse_type()
        is_const = False
        if self.is_token("keyword", "const"):
            self.eat()
            is_const = True
        name = self.expect("ident", what="identifier")
        init = None
        if self.is_token("operator", "="):
            self.eat()
            init = self.parse_expr()
        elif self.is_token("lbrace"):
            init = self.parse_init()
        self.expect("NL", what="end of line")
        return DeclStmt(type_token.line, type_token.col, type_token.text, is_const, name.text, init)

    def parse_assign(self):
        target = self.parse_chain()
        if not self.is_token("operator", "=") and self.ends_with_call(target):
            self.expect("NL", what="end of line")
            return ExprStmt(target.line, target.col, target)
        eq = self.expect("operator", "=")
        names = self.target_names(target)
        if names is None:
            self.error("cannot assign to a call", eq)
        value = self.parse_expr()
        self.expect("NL", what="end of line")
        return AssignStmt(target.line, target.col, ".".join(names), value)

    def ends_with_call(self, chain):
        last = chain.items[-1] if isinstance(chain, ChainExpr) else chain
        return isinstance(last, CallExpr)

    def target_names(self, chain):
        items = chain.items if isinstance(chain, ChainExpr) else [chain]
        if not all(isinstance(item, IdentExpr) for item in items):
            return None
        return [item.name for item in items]

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
        if token.kind == "keyword" and token.text == "read":
            return self.parse_read()
        if token.kind == "ident":
            return self.parse_chain()
        if token.kind == "operator" and token.text == "!":
            self.eat()
            return UnaryExpr(token.line, token.col, "!", self.parse_factor())
        self.error(f"expected expression, found {describe(token)}")

    def is_type_token(self, k=0):
        token = self.peek(k)
        return token.kind == "ident" or (token.kind == "keyword" and token.text in TYPE_NAMES)

    def is_function_start(self):
        return self.is_type_token() and self.is_token("ident", k=1) and self.is_token("lbracket", k=2)

    def parse_type(self):
        if not self.is_type_token():
            self.error(f"expected type, found {describe(self.peek())}")
        return self.eat()

    def parse_struct(self):
        keyword = self.eat()
        name = self.expect("ident", what="identifier")
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        if not self.is_token("INDENT"):
            self.error("struct must contain at least one member")
        self.eat()
        members = []
        while not self.is_token("DEDENT"):
            if self.is_function_start():
                members.append(self.parse_function())
            else:
                members.append(self.parse_field_decl())
        self.eat()
        return StructDecl(keyword.line, keyword.col, name.text, members)

    def parse_field_decl(self):
        type_token = self.parse_type()
        is_const = False
        if self.is_token("keyword", "const"):
            self.eat()
            is_const = True
        name = self.expect("ident", what="identifier")
        self.expect("NL", what="end of line")
        return FieldDecl(type_token.line, type_token.col, type_token.text, is_const, name.text)

    def parse_function(self):
        type_token = self.parse_type()
        name = self.expect("ident", what="identifier")
        self.expect("lbracket", "(")
        params = []
        if not self.is_token("rbracket"):
            params.append(self.parse_param())
            while self.is_token("coma"):
                self.eat()
                params.append(self.parse_param())
        self.expect("rbracket", ")")
        self.expect("colon", ":")
        self.expect("NL", what="end of line")
        body = self.parse_block()
        return FunctionDecl(type_token.line, type_token.col, type_token.text, name.text, params, body)

    def parse_param(self):
        type_token = self.parse_type()
        name = self.expect("ident", what="identifier")
        return ParamNode(type_token.line, type_token.col, type_token.text, name.text)

    def parse_init(self):
        brace = self.expect("lbrace", "{")
        values = [self.parse_value()]
        while self.is_token("coma"):
            self.eat()
            values.append(self.parse_value())
        self.expect("rbrace", "}")
        return InitExpr(brace.line, brace.col, values)

    def parse_value(self):
        if self.is_token("lbrace"):
            return self.parse_init()
        return self.parse_expr()

    def parse_call(self):
        name = self.expect("ident", what="identifier")
        self.expect("lbracket", "(")
        args = []
        if not self.is_token("rbracket"):
            args.append(self.parse_expr())
            while self.is_token("coma"):
                self.eat()
                args.append(self.parse_expr())
        self.expect("rbracket", ")")
        return CallExpr(name.line, name.col, name.text, args)

    def parse_chain_item(self):
        if self.is_token("ident") and self.is_token("lbracket", k=1):
            return self.parse_call()
        name = self.expect("ident", what="identifier")
        return IdentExpr(name.line, name.col, name.text)

    def parse_chain(self):
        first = self.peek()
        items = [self.parse_chain_item()]
        while self.is_token("dot"):
            self.eat()
            items.append(self.parse_chain_item())
        if len(items) == 1:
            return items[0]
        return ChainExpr(first.line, first.col, items)

    def parse_string(self):
        token = self.expect("string", what="string")
        return StringExpr(token.line, token.col, token.text)

    def parse_print(self):
        keyword = self.eat()
        self.expect("lbracket", "(")
        if self.is_token("string"):
            value = self.parse_string()
        else:
            value = self.parse_expr()
        self.expect("rbracket", ")")
        self.expect("NL", what="end of line")
        return PrintStmt(keyword.line, keyword.col, value)

    def parse_read(self):
        keyword = self.eat()
        self.expect("lbracket", "(")
        self.expect("rbracket", ")")
        return ReadExpr(keyword.line, keyword.col)


def parse(tokens):
    return Parser(tokens).parse_program()
