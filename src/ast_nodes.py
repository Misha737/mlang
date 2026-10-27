class ASTNode:
    _fields = ()
    _children = ()

    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col

    @classmethod
    def from_token(cls, token, *args, **kwargs):
        return cls(token.line, token.col, *args, **kwargs)

    def pos(self):
        return self.line, self.col

    def children(self):
        result = []
        for name in self._children:
            value = getattr(self, name)
            if isinstance(value, list):
                result.extend(value)
            elif value is not None:
                result.append(value)
        return result

    def label(self) -> str:
        parts = [type(self).__name__]
        parts += [f"{f}={getattr(self, f)!r}" for f in self._fields]
        parts.append(f"@{self.line}:{self.col}")
        return " ".join(parts)

    def dump(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [pad + self.label()]
        for name in self._children:
            value = getattr(self, name)
            if value is None:
                continue
            lines.append(f"{pad}  {name}:")
            items = value if isinstance(value, list) else [value]
            for item in items:
                lines.append(item.dump(indent + 2))
        return "\n".join(lines)

    def __repr__(self):
        return self.label()


class ProgramNode(ASTNode):
    _children = ("body",)

    def __init__(self, line, col, body):
        super().__init__(line, col)
        self.body = body


class BlockNode(ASTNode):
    _children = ("body",)

    def __init__(self, line, col, body):
        super().__init__(line, col)
        self.body = body


class StmtNode(ASTNode):
    pass


class DeclStmt(StmtNode):
    _fields = ("type_name", "is_const", "name")
    _children = ("init",)

    def __init__(self, line, col, type_name, is_const, name, init=None):
        super().__init__(line, col)
        self.type_name = type_name
        self.is_const = is_const
        self.name = name
        self.init = init


class AssignStmt(StmtNode):
    _fields = ("name",)
    _children = ("value",)

    def __init__(self, line, col, name, value):
        super().__init__(line, col)
        self.name = name
        self.value = value


class IfStmt(StmtNode):
    _children = ("cond", "then_block", "else_block")

    def __init__(self, line, col, cond, then_block, else_block=None):
        super().__init__(line, col)
        self.cond = cond
        self.then_block = then_block
        self.else_block = else_block


class WhileStmt(StmtNode):
    _children = ("cond", "body")

    def __init__(self, line, col, cond, body):
        super().__init__(line, col)
        self.cond = cond
        self.body = body


class ExitStmt(StmtNode):
    _children = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value


class ExprNode(ASTNode):
    pass


class NumberExpr(ExprNode):
    _fields = ("text",)

    def __init__(self, line, col, text):
        super().__init__(line, col)
        self.text = text

    @property
    def value(self):
        return int(self.text)


class BoolExpr(ExprNode):
    _fields = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value


class IdentExpr(ExprNode):
    _fields = ("name",)

    def __init__(self, line, col, name):
        super().__init__(line, col)
        self.name = name


class UnaryExpr(ExprNode):
    _fields = ("op",)
    _children = ("operand",)

    def __init__(self, line, col, op, operand):
        super().__init__(line, col)
        self.op = op
        self.operand = operand


class BinaryExpr(ExprNode):
    _fields = ("op",)
    _children = ("left", "right")

    def __init__(self, line, col, op, left, right):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right


class StringExpr(ExprNode):
    _fields = ("text",)

    def __init__(self, line, col, text):
        super().__init__(line, col)
        self.text = text


class ReadExpr(ExprNode):
    pass


class InitExpr(ExprNode):
    _children = ("values",)

    def __init__(self, line, col, values):
        super().__init__(line, col)
        self.values = values


class CallExpr(ExprNode):
    _fields = ("name",)
    _children = ("args",)

    def __init__(self, line, col, name, args):
        super().__init__(line, col)
        self.name = name
        self.args = args


class ChainExpr(ExprNode):
    _fields = ("is_callable",)
    _children = ("items",)

    def __init__(self, line, col, items):
        super().__init__(line, col)
        self.items = items
        self.is_callable = isinstance(items[-1], CallExpr)


class PrintStmt(StmtNode):
    _children = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value


class ExprStmt(StmtNode):
    _children = ("expr",)

    def __init__(self, line, col, expr):
        super().__init__(line, col)
        self.expr = expr


class FieldDecl(ASTNode):
    _fields = ("type_name", "is_const", "name")

    def __init__(self, line, col, type_name, is_const, name):
        super().__init__(line, col)
        self.type_name = type_name
        self.is_const = is_const
        self.name = name


class ParamNode(ASTNode):
    _fields = ("type_name", "name")

    def __init__(self, line, col, type_name, name):
        super().__init__(line, col)
        self.type_name = type_name
        self.name = name


class FunctionDecl(ASTNode):
    _fields = ("return_type", "name")
    _children = ("params", "body")

    def __init__(self, line, col, return_type, name, params, body):
        super().__init__(line, col)
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body


class StructDecl(ASTNode):
    _fields = ("name",)
    _children = ("members",)

    def __init__(self, line, col, name, members):
        super().__init__(line, col)
        self.name = name
        self.members = members
