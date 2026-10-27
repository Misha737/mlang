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

    def accept(self, visitor):
        raise NotImplementedError

    def __repr__(self):
        return self.label()


class ProgramNode(ASTNode):
    _children = ("structs", "functions", "statements", "exit")

    def __init__(self, line, col, structs, functions, statements, exit):
        super().__init__(line, col)
        self.structs = structs
        self.functions = functions
        self.statements = statements
        self.exit = exit

    def accept(self, visitor):
        return visitor.visit_program(self)


class BlockNode(ASTNode):
    _children = ("body",)

    def __init__(self, line, col, body):
        super().__init__(line, col)
        self.body = body

    def accept(self, visitor):
        return visitor.visit_block(self)


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

    def accept(self, visitor):
        return visitor.visit_decl_stmt(self)



class AssignStmt(StmtNode):
    _fields = ("name",)
    _children = ("value",)

    def __init__(self, line, col, name, value):
        super().__init__(line, col)
        self.name = name
        self.value = value

    def accept(self, visitor):
        return visitor.visit_assign_stmt(self)



class IfStmt(StmtNode):
    _children = ("cond", "then_block", "else_block")

    def __init__(self, line, col, cond, then_block, else_block=None):
        super().__init__(line, col)
        self.cond = cond
        self.then_block = then_block
        self.else_block = else_block

    def accept(self, visitor):
        return visitor.visit_if_stmt(self)



class WhileStmt(StmtNode):
    _children = ("cond", "body")

    def __init__(self, line, col, cond, body):
        super().__init__(line, col)
        self.cond = cond
        self.body = body

    def accept(self, visitor):
        return visitor.visit_while_stmt(self)



class ExitStmt(StmtNode):
    _children = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def accept(self, visitor):
        return visitor.visit_exit_stmt(self)



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

    def accept(self, visitor):
        return visitor.visit_number_expr(self)



class BoolExpr(ExprNode):
    _fields = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def accept(self, visitor):
        return visitor.visit_bool_expr(self)



class IdentExpr(ExprNode):
    _fields = ("name",)

    def __init__(self, line, col, name):
        super().__init__(line, col)
        self.name = name

    def accept(self, visitor):
        return visitor.visit_ident_expr(self)



class UnaryExpr(ExprNode):
    _fields = ("op",)
    _children = ("operand",)

    def __init__(self, line, col, op, operand):
        super().__init__(line, col)
        self.op = op
        self.operand = operand

    def accept(self, visitor):
        return visitor.visit_unary_expr(self)



class BinaryExpr(ExprNode):
    _fields = ("op",)
    _children = ("left", "right")

    def __init__(self, line, col, op, left, right):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right

    def accept(self, visitor):
        return visitor.visit_binary_expr(self)



class StringExpr(ExprNode):
    _fields = ("text",)

    def __init__(self, line, col, text):
        super().__init__(line, col)
        self.text = text

    def accept(self, visitor):
        return visitor.visit_string_expr(self)



class ReadExpr(ExprNode):
    def accept(self, visitor):
        return visitor.visit_read_expr(self)


class InitExpr(ExprNode):
    _children = ("values",)

    def __init__(self, line, col, values):
        super().__init__(line, col)
        self.values = values

    def accept(self, visitor):
        return visitor.visit_init_expr(self)



class CallExpr(ExprNode):
    _fields = ("name",)
    _children = ("args",)

    def __init__(self, line, col, name, args):
        super().__init__(line, col)
        self.name = name
        self.args = args

    def accept(self, visitor):
        return visitor.visit_call_expr(self)



class ChainExpr(ExprNode):
    _fields = ("is_callable",)
    _children = ("items",)

    def __init__(self, line, col, items):
        super().__init__(line, col)
        self.items = items
        self.is_callable = isinstance(items[-1], CallExpr)

    def accept(self, visitor):
        return visitor.visit_chain_expr(self)



class PrintStmt(StmtNode):
    _children = ("value",)

    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def accept(self, visitor):
        return visitor.visit_print_stmt(self)



class ExprStmt(StmtNode):
    _children = ("expr",)

    def __init__(self, line, col, expr):
        super().__init__(line, col)
        self.expr = expr

    def accept(self, visitor):
        return visitor.visit_expr_stmt(self)



class FieldDecl(ASTNode):
    _fields = ("type_name", "is_const", "name")

    def __init__(self, line, col, type_name, is_const, name):
        super().__init__(line, col)
        self.type_name = type_name
        self.is_const = is_const
        self.name = name

    def accept(self, visitor):
        return visitor.visit_field_decl(self)



class ParamNode(ASTNode):
    _fields = ("type_name", "name")

    def __init__(self, line, col, type_name, name):
        super().__init__(line, col)
        self.type_name = type_name
        self.name = name

    def accept(self, visitor):
        return visitor.visit_param(self)



class FunctionDecl(ASTNode):
    _fields = ("return_type", "name")
    _children = ("params", "body")

    def __init__(self, line, col, return_type, name, params, body):
        super().__init__(line, col)
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body

    def accept(self, visitor):
        return visitor.visit_function_decl(self)



class StructDecl(ASTNode):
    _fields = ("name",)
    _children = ("members",)

    def __init__(self, line, col, name, members):
        super().__init__(line, col)
        self.name = name
        self.members = members

    def accept(self, visitor):
        return visitor.visit_struct_decl(self)
