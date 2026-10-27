from entities import *
from ast_nodes import *

INT_MIN, INT_MAX = -2**31, 2**31 - 1
LONG_MIN, LONG_MAX = -2**63, 2**63 - 1

NUMERIC_TYPES = ("int", "double")


def error_at(node, message):
    return CompileError(f"{node.line}:{node.col}: {message}")


def assignable(target, source):
    return target == source or (target == "double" and source == "int")


def fits(value, type_name):
    if type_name == "int":
        return INT_MIN <= value <= INT_MAX
    return LONG_MIN <= value <= LONG_MAX


class VarSymbol:
    def __init__(self, name, type_name, is_const):
        self.name = name
        self.type = type_name
        self.is_const = is_const
        self.const_value = None


class FieldSymbol:
    def __init__(self, name, type_name, is_const, index, struct_name):
        self.name = name
        self.type = type_name
        self.is_const = is_const
        self.index = index
        self.struct_name = struct_name


class FunctionSymbol:
    def __init__(self, name, params, return_type, node, struct_name=None):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.node = node
        self.struct_name = struct_name
        self.mutates = False

    @property
    def qualified_name(self):
        return f"{self.struct_name}.{self.name}" if self.struct_name else self.name


class StructSymbol:
    def __init__(self, name, node):
        self.name = name
        self.node = node
        self.fields = []
        self.field_map = {}
        self.methods = {}


class CallSite:
    def __init__(self, node, callee, caller, const_by, from_self):
        self.node = node
        self.callee = callee
        self.caller = caller
        self.const_by = const_by
        self.from_self = from_self


class SemanticChecker:
    def __init__(self):
        self.scopes = []
        self.structs = {}
        self.functions = {}
        self.current_function = None
        self.current_struct = None
        self.member_functions = []
        self.call_sites = []

    def check(self, program):
        program.accept(self)
        return program

    def visit_program(self, node: ProgramNode):
        for struct in node.structs:
            self.declare_struct(struct)
        for struct in node.structs:
            struct.accept(self)
        self.check_struct_cycles()
        for function in node.functions:
            self.declare_function(function)
        for struct in node.structs:
            self.current_struct = self.structs[struct.name]
            for method in struct.methods:
                method.accept(self)
            self.current_struct = None
        for function in node.functions:
            function.accept(self)
        self.scopes.append({})
        for statement in node.statements:
            statement.accept(self)
        node.exit.accept(self)
        self.scopes.pop()
        self.finish_member_calls()

    def declare_struct(self, node):
        if node.name in self.structs:
            raise error_at(node, f"struct '{node.name}' is already declared")
        self.structs[node.name] = StructSymbol(node.name, node)

    def visit_struct_decl(self, node: StructDecl):
        struct = self.structs[node.name]
        if not node.fields:
            raise error_at(node, f"struct '{node.name}' must have at least one field")
        for field in node.fields:
            if field.name in struct.field_map:
                raise error_at(field, f"field '{field.name}' is already declared in struct '{node.name}'")
            self.require_type(field, field.type_name)
            symbol = FieldSymbol(field.name, field.type_name, field.is_const, len(struct.fields), node.name)
            struct.fields.append(symbol)
            struct.field_map[field.name] = symbol
        for method in node.methods:
            if method.name in struct.methods:
                raise error_at(method, f"member function '{method.name}' is already declared in struct '{node.name}'")
            if method.name in struct.field_map:
                raise error_at(method, f"'{method.name}' is already a field of struct '{node.name}'")
            symbol = self.make_signature(method, node.name)
            struct.methods[method.name] = symbol
            self.member_functions.append(symbol)

    def check_struct_cycles(self):
        state = {}

        def visit(struct):
            if state.get(struct.name) == "done":
                return
            if state.get(struct.name) == "active":
                raise error_at(struct.node, f"struct '{struct.name}' contains itself")
            state[struct.name] = "active"
            for field in struct.fields:
                if field.type in self.structs:
                    visit(self.structs[field.type])
            state[struct.name] = "done"

        for struct in self.structs.values():
            visit(struct)

    def declare_function(self, node):
        if node.name in self.functions:
            raise error_at(node, f"function '{node.name}' is already declared")
        if node.name in self.structs:
            raise error_at(node, f"'{node.name}' is already declared as a struct")
        self.functions[node.name] = self.make_signature(node)

    def make_signature(self, node, struct_name=None):
        self.require_scalar_type(node, node.return_type, "result")
        params = []
        seen = set()
        for param in node.params:
            self.require_scalar_type(param, param.type_name, "parameter")
            if param.name in seen:
                raise error_at(param, f"parameter '{param.name}' is already declared")
            seen.add(param.name)
            params.append((param.type_name, param.name))
        symbol = FunctionSymbol(node.name, params, node.return_type, node, struct_name)
        node.symbol = symbol
        return symbol

    def require_type(self, node, type_name):
        if type_name not in TYPE_NAMES and type_name not in self.structs:
            raise error_at(node, f"unknown type '{type_name}'")

    def require_scalar_type(self, node, type_name, role):
        self.require_type(node, type_name)
        if type_name not in TYPE_NAMES:
            raise error_at(node, f"{role} of type '{type_name}' is not allowed: only int, double and bool")

    def visit_function_decl(self, node: FunctionDecl):
        symbol = node.symbol
        saved = self.scopes, self.current_function
        self.scopes = [{}]
        self.current_function = symbol
        node.param_symbols = []
        for type_name, name in symbol.params:
            param = VarSymbol(name, type_name, False)
            self.scopes[0][name] = param
            node.param_symbols.append(param)
        for statement in node.body.body:
            statement.accept(self)
        if not self.terminates(node.body.body):
            raise error_at(node, f"function '{symbol.qualified_name}' can finish without 'exit'")
        self.scopes, self.current_function = saved

    def terminates(self, statements):
        for statement in statements:
            if isinstance(statement, ExitStmt):
                return True
            if isinstance(statement, IfStmt) and statement.else_block is not None:
                if self.terminates(statement.then_block.body) and self.terminates(statement.else_block.body):
                    return True
        return False

    def visit_block(self, node: BlockNode):
        self.scopes.append({})
        for statement in node.body:
            statement.accept(self)
        self.scopes.pop()

    def visit_decl_stmt(self, node: DeclStmt):
        self.require_type(node, node.type_name)
        const_value = None
        if node.type_name in self.structs:
            if not isinstance(node.init, InitExpr):
                raise error_at(node, f"object '{node.name}' of struct '{node.type_name}' needs a value for every field: {{...}}")
            self.check_init(node.type_name, node.init)
        elif isinstance(node.init, InitExpr):
            raise error_at(node.init, f"'{node.type_name}' variable cannot be initialized with {{...}}")
        elif node.init is not None:
            value_type = node.init.accept(self)
            if not assignable(node.type_name, value_type):
                raise error_at(node.init, f"cannot initialize '{node.type_name}' variable '{node.name}' with a value of type '{value_type}'")
            const_value = node.init.const_value
        if node.name in self.scopes[-1]:
            raise error_at(node, f"'{node.name}' is already declared in this scope")
        symbol = VarSymbol(node.name, node.type_name, node.is_const)
        symbol.const_value = const_value
        self.scopes[-1][node.name] = symbol
        node.symbol = symbol

    def check_init(self, struct_name, init):
        struct = self.structs[struct_name]
        if len(init.values) != len(struct.fields):
            raise error_at(init, f"struct '{struct_name}' has {len(struct.fields)} fields, got {len(init.values)} values")
        for field, value in zip(struct.fields, init.values):
            if field.type in self.structs:
                if not isinstance(value, InitExpr):
                    raise error_at(value, f"field '{field.name}' of struct '{struct_name}' needs {{...}} of struct '{field.type}'")
                self.check_init(field.type, value)
            elif isinstance(value, InitExpr):
                raise error_at(value, f"field '{field.name}' has type '{field.type}' and cannot be initialized with {{...}}")
            else:
                value_type = value.accept(self)
                if not assignable(field.type, value_type):
                    raise error_at(value, f"field '{field.name}' has type '{field.type}', got a value of type '{value_type}'")
        init.type = struct_name

    def visit_init_expr(self, node: InitExpr):
        raise error_at(node, "{...} is allowed only as the value of an object declaration")

    def visit_assign_stmt(self, node: AssignStmt):
        names = node.name.split(".")
        root = self.lookup_name(names[0])
        if root is None:
            raise error_at(node, f"undefined variable '{names[0]}'")
        type_name = root.type
        const_by = names[0] if root.is_const else None
        from_self = isinstance(root, FieldSymbol)
        targets = [root]
        for name in names[1:]:
            field = self.find_field(node, type_name, name)
            targets.append(field)
            type_name = field.type
            if const_by is None and field.is_const:
                const_by = name
        if type_name in self.structs:
            raise error_at(node, f"cannot assign to object '{node.name}' as a whole; assign its fields")
        if const_by is not None:
            raise error_at(node, f"cannot assign to '{node.name}': '{const_by}' is constant")
        value_type = node.value.accept(self)
        if not assignable(type_name, value_type):
            raise error_at(node.value, f"cannot assign a value of type '{value_type}' to '{node.name}' of type '{type_name}'")
        if from_self:
            self.current_function.mutates = True
        elif len(names) == 1:
            root.const_value = node.value.const_value
        node.targets = targets
        node.type = type_name

    def assigned_variables(self, statements):
        result = set()
        for statement in statements:
            if isinstance(statement, AssignStmt) and "." not in statement.name:
                symbol = self.lookup_name(statement.name)
                if isinstance(symbol, VarSymbol):
                    result.add(symbol)
            elif isinstance(statement, IfStmt):
                result |= self.assigned_variables(statement.then_block.body)
                if statement.else_block is not None:
                    result |= self.assigned_variables(statement.else_block.body)
            elif isinstance(statement, WhileStmt):
                result |= self.assigned_variables(statement.body.body)
        return result

    def visit_if_stmt(self, node: IfStmt):
        self.require_bool(node.cond, "condition of 'if'")
        blocks = [node.then_block] + ([node.else_block] if node.else_block is not None else [])
        assigned = self.assigned_variables(sum((b.body for b in blocks), []))
        known = {symbol: symbol.const_value for symbol in assigned}
        for block in blocks:
            for symbol, value in known.items():
                symbol.const_value = value
            block.accept(self)
        for symbol in assigned:
            symbol.const_value = None

    def visit_while_stmt(self, node: WhileStmt):
        assigned = self.assigned_variables(node.body.body)
        for symbol in assigned:
            symbol.const_value = None
        self.require_bool(node.cond, "condition of 'while'")
        node.body.accept(self)
        for symbol in assigned:
            symbol.const_value = None

    def require_bool(self, expr, what):
        type_name = expr.accept(self)
        if type_name != "bool":
            raise error_at(expr, f"{what} must be bool, got '{type_name}'")

    def visit_exit_stmt(self, node: ExitStmt):
        value_type = node.value.accept(self)
        function = self.current_function
        if function is None:
            if value_type not in TYPE_NAMES:
                raise error_at(node, f"'exit' needs an int, double or bool value, got '{value_type}'")
        elif not assignable(function.return_type, value_type):
            raise error_at(node, f"function '{function.qualified_name}' returns '{function.return_type}', but 'exit' has a value of type '{value_type}'")

    def visit_print_stmt(self, node: PrintStmt):
        node.value.accept(self)

    def visit_expr_stmt(self, node: ExprStmt):
        node.expr.accept(self)

    def typed(self, node, type_name, const_value=None):
        node.type = type_name
        node.const_value = const_value
        return type_name

    def visit_number_expr(self, node: NumberExpr):
        value = node.value
        if value > LONG_MAX:
            raise error_at(node, f"integer literal {node.text} does not fit in double")
        return self.typed(node, "int" if value <= INT_MAX else "double", value)

    def visit_bool_expr(self, node: BoolExpr):
        return self.typed(node, "bool")

    def visit_string_expr(self, node: StringExpr):
        return self.typed(node, "string")

    def visit_read_expr(self, node: ReadExpr):
        return self.typed(node, "int")

    def visit_unary_expr(self, node: UnaryExpr):
        operand_type = node.operand.accept(self)
        if operand_type != "bool":
            raise error_at(node, f"operator '{node.op}' needs a bool operand, got '{operand_type}'")
        return self.typed(node, "bool")

    def visit_binary_expr(self, node: BinaryExpr):
        left = node.left.accept(self)
        right = node.right.accept(self)
        if node.op in ("==", "!="):
            both_numeric = left in NUMERIC_TYPES and right in NUMERIC_TYPES
            if not both_numeric and not (left == right == "bool"):
                raise error_at(node, f"cannot compare '{left}' with '{right}'")
            return self.typed(node, "bool")
        if left not in NUMERIC_TYPES or right not in NUMERIC_TYPES:
            raise error_at(node, f"operator '{node.op}' needs int or double operands, got '{left}' and '{right}'")
        result_type = "double" if "double" in (left, right) else "int"
        a, b = node.left.const_value, node.right.const_value
        if a is None or b is None:
            return self.typed(node, result_type)
        value = {"+": a + b, "-": a - b, "*": a * b}[node.op]
        if not fits(value, result_type):
            raise error_at(node, f"overflow: {a} {node.op} {b} does not fit in {result_type}")
        return self.typed(node, result_type, value)

    def visit_ident_expr(self, node: IdentExpr):
        return self.resolve_name(node)[0]

    def visit_call_expr(self, node: CallExpr):
        return self.resolve_first_call(node)[0]

    def visit_chain_expr(self, node: ChainExpr):
        first = node.items[0]
        if isinstance(first, IdentExpr):
            type_name, const_by, from_self = self.resolve_name(first)
        else:
            type_name, const_by, from_self = self.resolve_first_call(first)
        for item in node.items[1:]:
            if type_name not in self.structs:
                raise error_at(item, f"type '{type_name}' has no fields or member functions")
            struct = self.structs[type_name]
            if isinstance(item, IdentExpr):
                field = self.find_field(item, type_name, item.name)
                item.symbol = field
                if const_by is None and field.is_const:
                    const_by = field.name
                type_name = self.typed(item, field.type)
            else:
                method = struct.methods.get(item.name)
                if method is None:
                    raise error_at(item, f"struct '{type_name}' has no member function '{item.name}'")
                self.check_call_args(item, method)
                self.call_sites.append(CallSite(item, method, self.current_function if self.current_struct else None, const_by, from_self))
                type_name = self.typed(item, method.return_type)
                const_by = None
        return self.typed(node, type_name)

    def lookup_name(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if self.current_struct is not None:
            return self.current_struct.field_map.get(name)
        return None

    def resolve_name(self, node: IdentExpr):
        symbol = self.lookup_name(node.name)
        if symbol is None:
            raise error_at(node, f"undefined variable '{node.name}'")
        node.symbol = symbol
        self.typed(node, symbol.type, getattr(symbol, "const_value", None))
        const_by = node.name if symbol.is_const else None
        return symbol.type, const_by, isinstance(symbol, FieldSymbol)

    def resolve_first_call(self, node: CallExpr):
        method = self.current_struct.methods.get(node.name) if self.current_struct else None
        if method is not None:
            self.check_call_args(node, method)
            self.call_sites.append(CallSite(node, method, self.current_function, None, True))
            return self.typed(node, method.return_type), None, False
        function = self.functions.get(node.name)
        if function is None:
            raise error_at(node, f"undefined function '{node.name}'")
        self.check_call_args(node, function)
        return self.typed(node, function.return_type), None, False

    def find_field(self, node, type_name, field_name):
        struct = self.structs.get(type_name)
        if struct is None:
            raise error_at(node, f"type '{type_name}' has no fields")
        field = struct.field_map.get(field_name)
        if field is None:
            raise error_at(node, f"struct '{type_name}' has no field '{field_name}'")
        return field

    def check_call_args(self, node: CallExpr, function: FunctionSymbol):
        node.symbol = function
        name = function.qualified_name
        if len(node.args) != len(function.params):
            raise error_at(node, f"'{name}' takes {len(function.params)} arguments, got {len(node.args)}")
        for position, (arg, (param_type, param_name)) in enumerate(zip(node.args, function.params), 1):
            arg_type = arg.accept(self)
            if not assignable(param_type, arg_type):
                raise error_at(arg, f"argument {position} of '{name}' ('{param_name}') has type '{arg_type}', expected '{param_type}'")

    def finish_member_calls(self):
        changed = True
        while changed:
            changed = False
            for site in self.call_sites:
                inherits = site.from_self and site.const_by is None and site.callee.mutates
                if inherits and site.caller is not None and not site.caller.mutates:
                    site.caller.mutates = True
                    changed = True
        for site in self.call_sites:
            if site.callee.mutates and site.const_by is not None:
                raise error_at(site.node, f"member function '{site.callee.qualified_name}' assigns a field and cannot be called on constant '{site.const_by}'")
