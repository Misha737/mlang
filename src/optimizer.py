from ast_nodes import *
from semantic import VarSymbol


def walk(node):
    yield node
    for child in node.children():
        yield from walk(child)


def is_effect(node):
    if isinstance(node, (CallExpr, ReadExpr)):
        return True
    return isinstance(node, BinaryExpr) and node.op in ("+", "-", "*") and node.const_value is None


def has_effect(expr):
    return any(is_effect(node) for node in walk(expr))


def kept_effects(value):
    if isinstance(value, InitExpr):
        return [stmt for item in value.values for stmt in kept_effects(item)]
    if value is not None and has_effect(value):
        return [ExprStmt(value.line, value.col, value)]
    return []


def unused_symbols(tree):
    reads = set()
    declared = set()
    for node in walk(tree):
        if isinstance(node, IdentExpr) and isinstance(node.symbol, VarSymbol):
            reads.add(node.symbol)
        elif isinstance(node, DeclStmt):
            declared.add(node.symbol)
    return declared - reads


def rewrite_block(block, unused):
    block.body = rewrite_statements(block.body, unused)


def rewrite_statements(statements, unused):
    result = []
    for statement in statements:
        if isinstance(statement, DeclStmt) and statement.symbol in unused:
            result.extend(kept_effects(statement.init))
            continue
        if isinstance(statement, AssignStmt) and statement.targets[0] in unused:
            result.extend(kept_effects(statement.value))
            continue
        if isinstance(statement, IfStmt):
            rewrite_block(statement.then_block, unused)
            if statement.else_block is not None:
                rewrite_block(statement.else_block, unused)
        elif isinstance(statement, WhileStmt):
            rewrite_block(statement.body, unused)
        result.append(statement)
    return result


def remove_unused_variables(tree):
    unused = unused_symbols(tree)
    if not unused:
        return False
    tree.statements = rewrite_statements(tree.statements, unused)
    for function in tree.functions:
        rewrite_block(function.body, unused)
    for struct in tree.structs:
        for method in struct.methods:
            rewrite_block(method.body, unused)
    return True


def all_functions(tree):
    functions = list(tree.functions)
    for struct in tree.structs:
        functions.extend(struct.methods)
    return functions


def called_symbols(tree):
    called = set()
    for function in all_functions(tree):
        for node in walk(function.body):
            if isinstance(node, CallExpr) and node.symbol is not function.symbol:
                called.add(node.symbol)
    for statement in [*tree.statements, tree.exit]:
        for node in walk(statement):
            if isinstance(node, CallExpr):
                called.add(node.symbol)
    return called


def remove_unused_functions(tree):
    unused = {function.symbol for function in all_functions(tree)} - called_symbols(tree)
    if not unused:
        return False
    tree.functions = [function for function in tree.functions if function.symbol not in unused]
    for struct in tree.structs:
        struct.members = [member for member in struct.members
                          if not (isinstance(member, FunctionDecl) and member.symbol in unused)]
    return True


def statement_lists(statements):
    yield statements
    for statement in statements:
        if isinstance(statement, IfStmt):
            yield from statement_lists(statement.then_block.body)
            if statement.else_block is not None:
                yield from statement_lists(statement.else_block.body)
        elif isinstance(statement, WhileStmt):
            yield from statement_lists(statement.body.body)


def all_statement_lists(tree):
    yield from statement_lists(tree.statements)
    for function in all_functions(tree):
        yield from statement_lists(function.body.body)


def whole_call(statement):
    if isinstance(statement, DeclStmt):
        value = statement.init
    elif isinstance(statement, ExprStmt):
        value = statement.expr
    elif isinstance(statement, (AssignStmt, PrintStmt, ExitStmt)):
        value = statement.value
    else:
        return None
    return value if isinstance(value, CallExpr) else None


def straight_line(function):
    body = function.body.body
    exits = [node for statement in body for node in walk(statement) if isinstance(node, ExitStmt)]
    return len(exits) == 1 and isinstance(body[-1], ExitStmt)


def calls_itself(function):
    return any(isinstance(node, CallExpr) and node.symbol is function.symbol for node in walk(function.body))


def rename_locals(tree, function):
    symbols = list(function.param_symbols)
    symbols += [node.symbol for node in walk(function.body) if isinstance(node, DeclStmt)]
    taken = {node.name for node in walk(tree) if isinstance(node, (DeclStmt, ParamNode, FunctionDecl))}
    names = {}
    for symbol in symbols:
        base = f"{function.name}_{symbol.name}"
        name, number = base, 0
        while name in taken:
            number += 1
            name = f"{base}_{number}"
        taken.add(name)
        names[symbol] = name
    for node in walk(function.body):
        if isinstance(node, (DeclStmt, IdentExpr)) and node.symbol in names:
            node.name = names[node.symbol]
        elif isinstance(node, AssignStmt) and node.targets[0] in names:
            node.name = ".".join([names[node.targets[0]], *node.name.split(".")[1:]])
    for symbol, name in names.items():
        symbol.name = name


def expand_call(tree, function, statement):
    call = whole_call(statement)
    body = function.body.body
    rename_locals(tree, function)
    result = []
    for param, symbol, argument in zip(function.params, function.param_symbols, call.args):
        declaration = DeclStmt(param.line, param.col, param.type_name, False, symbol.name, argument)
        declaration.symbol = symbol
        result.append(declaration)
    result.extend(body[:-1])
    value = body[-1].value
    if isinstance(statement, ExprStmt):
        result.extend(kept_effects(value))
    else:
        if isinstance(statement, DeclStmt):
            statement.init = value
        else:
            statement.value = value
        result.append(statement)
    return result


def inline_functions(tree):
    sites = {}
    for node in walk(tree):
        if isinstance(node, CallExpr):
            sites.setdefault(node.symbol, []).append(node)
    for function in tree.functions:
        calls = sites.get(function.symbol, [])
        if len(calls) != 1 or not straight_line(function) or calls_itself(function):
            continue
        if whole_call(tree.exit) is calls[0]:
            tree.statements.extend(expand_call(tree, function, tree.exit)[:-1])
        else:
            for statements in all_statement_lists(tree):
                index = next((i for i, s in enumerate(statements) if whole_call(s) is calls[0]), None)
                if index is not None:
                    statements[index:index + 1] = expand_call(tree, function, statements[index])
                    break
            else:
                continue
        tree.functions.remove(function)
        return True
    return False


PASSES = [remove_unused_variables, remove_unused_functions, inline_functions]


def optimize(tree):
    changed = True
    while changed:
        changed = False
        for run_pass in PASSES:
            while run_pass(tree):
                changed = True
    return tree
