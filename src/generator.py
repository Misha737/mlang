from llvmlite import ir
from ast_nodes import *
from semantic import FieldSymbol

I1, I32, I64 = ir.IntType(1), ir.IntType(32), ir.IntType(64)
I8P = ir.IntType(8).as_pointer()
SCALAR_TYPES = {"int": I32, "double": I64, "bool": I1}
PRINT_FORMATS = {"int": "%d", "double": "%lld", "bool": "%s"}
OVERFLOW_INTRINSICS = {"+": "sadd", "-": "ssub", "*": "smul"}


def const(type_, value):
    return ir.Constant(type_, value)


class CodeGenerator:
    def __init__(self, program):
        self.program = program
        self.structs = {
            struct.name: [FieldSymbol(f.name, f.type_name, f.is_const, index, struct.name)
                          for index, f in enumerate(struct.fields)]
            for struct in program.structs
        }
        self.module = ir.Module(name="mlang")
        self.module.triple = ""
        self.struct_types = {}
        self.fn_map = {}
        self.strings = {}
        self.intrinsics = {}
        self.builder = None
        self.entry = None
        self.slots = {}
        self.self_ptr = None
        self.return_type = None
        self.in_main = False

    def generate(self):
        self.program.accept(self)
        return self.module

    def llvm_type(self, type_name):
        return SCALAR_TYPES.get(type_name) or self.struct_types[type_name]

    def convert(self, value, source, target):
        if source == "int" and target == "double":
            return self.builder.sext(value, I64)
        return value

    def visit_program(self, node: ProgramNode):
        c_type = ir.FunctionType(I32, [I8P], var_arg=True)
        self.printf = ir.Function(self.module, c_type, name="printf")
        self.scanf = ir.Function(self.module, c_type, name="scanf")
        self.libc_exit = ir.Function(self.module, ir.FunctionType(ir.VoidType(), [I32]), name="exit")

        for name in self.structs:
            self.struct_types[name] = self.module.context.get_identified_type(f"struct.{name}")
        for name, fields in self.structs.items():
            self.struct_types[name].set_body(*[self.llvm_type(f.type) for f in fields])

        for function in node.functions:
            self.declare_function(function.symbol)
        for struct in node.structs:
            for method in struct.methods:
                self.declare_function(method.symbol)

        for function in node.functions:
            function.accept(self)
        for struct in node.structs:
            for method in struct.methods:
                method.accept(self)
        self.generate_main(node)

    def declare_function(self, symbol):
        params = [self.llvm_type(t) for t, _ in symbol.params]
        if symbol.struct_name:
            params.insert(0, self.struct_types[symbol.struct_name].as_pointer())
        fn_type = ir.FunctionType(self.llvm_type(symbol.return_type), params)
        self.fn_map[symbol] = ir.Function(self.module, fn_type, name=f"ml.{symbol.qualified_name}")

    def begin_function(self, fn):
        self.entry = fn.append_basic_block("entry")
        self.alloca_builder = ir.IRBuilder(self.entry)
        self.builder = ir.IRBuilder(fn.append_basic_block("body"))
        self.slots = {}
        self.self_ptr = None

    def alloca(self, type_):
        return self.alloca_builder.alloca(type_)

    def end_function(self):
        self.alloca_builder.branch(self.entry.function.blocks[1])

    def visit_function_decl(self, node: FunctionDecl):
        symbol = node.symbol
        fn = self.fn_map[symbol]
        self.begin_function(fn)
        self.in_main = False
        self.return_type = symbol.return_type
        args = list(fn.args)
        if symbol.struct_name:
            self.self_ptr = args.pop(0)
        for param, arg in zip(node.param_symbols, args):
            slot = self.alloca(arg.type)
            self.builder.store(arg, slot)
            self.slots[param] = slot
        self.gen_statements(node.body.body)
        if not self.builder.block.is_terminated:
            self.builder.unreachable()
        self.end_function()

    def generate_main(self, node):
        fn = ir.Function(self.module, ir.FunctionType(I32, []), name="main")
        self.begin_function(fn)
        self.in_main = True
        self.gen_statements(node.statements)
        node.exit.accept(self)
        self.end_function()

    def gen_statements(self, statements):
        for statement in statements:
            if self.builder.block.is_terminated:
                break
            statement.accept(self)

    def visit_block(self, node: BlockNode):
        self.gen_statements(node.body)

    def visit_decl_stmt(self, node: DeclStmt):
        symbol = node.symbol
        slot = self.alloca(self.llvm_type(node.type_name))
        self.slots[symbol] = slot
        if node.type_name in self.structs:
            self.gen_init(slot, node.type_name, node.init)
        elif node.init is not None:
            value = node.init.accept(self)
            self.builder.store(self.convert(value, node.init.type, node.type_name), slot)
        else:
            self.builder.store(const(slot.type.pointee, 0), slot)

    def gen_init(self, ptr, struct_name, init):
        for field, value in zip(self.structs[struct_name], init.values):
            field_ptr = self.field_ptr(ptr, field)
            if field.type in self.structs:
                self.gen_init(field_ptr, field.type, value)
            else:
                result = value.accept(self)
                self.builder.store(self.convert(result, value.type, field.type), field_ptr)

    def visit_assign_stmt(self, node: AssignStmt):
        ptr = self.symbol_place(node.targets[0])
        for field in node.targets[1:]:
            ptr = self.field_ptr(ptr, field)
        value = node.value.accept(self)
        self.builder.store(self.convert(value, node.value.type, node.type), ptr)

    def visit_if_stmt(self, node: IfStmt):
        cond = node.cond.accept(self)
        fn = self.builder.function
        then_block = fn.append_basic_block("then")
        else_block = fn.append_basic_block("else") if node.else_block else None
        merge = fn.append_basic_block("endif")
        self.builder.cbranch(cond, then_block, else_block or merge)
        for block, body in ((then_block, node.then_block), (else_block, node.else_block)):
            if block is None:
                continue
            self.builder.position_at_end(block)
            body.accept(self)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge)
        self.builder.position_at_end(merge)

    def visit_while_stmt(self, node: WhileStmt):
        fn = self.builder.function
        cond_block = fn.append_basic_block("while.cond")
        body_block = fn.append_basic_block("while.body")
        end_block = fn.append_basic_block("while.end")
        self.builder.branch(cond_block)
        self.builder.position_at_end(cond_block)
        self.builder.cbranch(node.cond.accept(self), body_block, end_block)
        self.builder.position_at_end(body_block)
        node.body.accept(self)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_block)
        self.builder.position_at_end(end_block)

    def visit_exit_stmt(self, node: ExitStmt):
        value = node.value.accept(self)
        if self.in_main:
            if node.value.type == "double":
                value = self.builder.trunc(value, I32)
            elif node.value.type == "bool":
                value = self.builder.zext(value, I32)
        else:
            value = self.convert(value, node.value.type, self.return_type)
        self.builder.ret(value)

    def visit_expr_stmt(self, node: ExprStmt):
        node.expr.accept(self)

    def cstr(self, text):
        if text not in self.strings:
            data = bytearray(text.encode("utf-8") + b"\0")
            glob = ir.GlobalVariable(self.module, ir.ArrayType(ir.IntType(8), len(data)), name=f".str.{len(self.strings)}")
            glob.global_constant = True
            glob.linkage = "private"
            glob.unnamed_addr = True
            glob.initializer = ir.Constant(glob.value_type, data)
            self.strings[text] = glob.gep([const(I32, 0), const(I32, 0)])
        return self.strings[text]

    def printf_text(self, text):
        self.builder.call(self.printf, [self.cstr(text)])

    def print_scalar(self, value, type_name, prefix, suffix):
        fmt = self.cstr(prefix + PRINT_FORMATS[type_name] + suffix)
        if type_name == "bool":
            value = self.builder.select(value, self.cstr("true"), self.cstr("false"))
        self.builder.call(self.printf, [fmt, value])

    def print_struct(self, ptr, struct_name, prefix, end):
        self.printf_text(f"{prefix}{struct_name}{{")
        for field in self.structs[struct_name]:
            label = f"{', ' if field.index else ''}{field.name}="
            field_ptr = self.field_ptr(ptr, field)
            if field.type in self.structs:
                self.print_struct(field_ptr, field.type, label, "")
            else:
                self.print_scalar(self.builder.load(field_ptr), field.type, label, "")
        self.printf_text("}" + end)

    def visit_print_stmt(self, node: PrintStmt):
        value = node.value
        if isinstance(value, StringExpr):
            self.builder.call(self.printf, [self.cstr("%s\n"), self.cstr(value.text)])
        elif value.type in self.structs:
            self.print_struct(self.expr_place(value), value.type, "", "\n")
        else:
            self.print_scalar(value.accept(self), value.type, "", "\n")

    def visit_read_expr(self, node: ReadExpr):
        slot = self.alloca(I32)
        self.builder.call(self.scanf, [self.cstr("%d"), slot])
        return self.builder.load(slot)

    def field_ptr(self, ptr, field):
        return self.builder.gep(ptr, [const(I32, 0), const(I32, field.index)])

    def symbol_place(self, symbol):
        if isinstance(symbol, FieldSymbol):
            return self.field_ptr(self.self_ptr, symbol)
        return self.slots[symbol]

    def items_place(self, items):
        ptr = self.symbol_place(items[0].symbol)
        for item in items[1:]:
            ptr = self.field_ptr(ptr, item.symbol)
        return ptr

    def expr_place(self, expr):
        if isinstance(expr, IdentExpr):
            return self.symbol_place(expr.symbol)
        return self.items_place(expr.items)

    def visit_number_expr(self, node: NumberExpr):
        return const(self.llvm_type(node.type), node.value)

    def visit_bool_expr(self, node: BoolExpr):
        return const(I1, int(node.value))

    def visit_ident_expr(self, node: IdentExpr):
        return self.builder.load(self.symbol_place(node.symbol))

    def visit_chain_expr(self, node: ChainExpr):
        if node.is_callable:
            return self.gen_call(node.items[-1], self.items_place(node.items[:-1]))
        return self.builder.load(self.items_place(node.items))

    def visit_call_expr(self, node: CallExpr):
        return self.gen_call(node, self.self_ptr)

    def gen_call(self, node, receiver):
        symbol = node.symbol
        args = [self.convert(arg.accept(self), arg.type, param_type)
                for arg, (param_type, _) in zip(node.args, symbol.params)]
        if symbol.struct_name:
            args.insert(0, receiver)
        return self.builder.call(self.fn_map[symbol], args)

    def visit_unary_expr(self, node: UnaryExpr):
        return self.builder.xor(node.operand.accept(self), const(I1, 1))

    def visit_binary_expr(self, node: BinaryExpr):
        if node.op in ("==", "!="):
            return self.gen_compare(node)
        if node.const_value is not None:
            return const(self.llvm_type(node.type), node.const_value)
        left = self.convert(node.left.accept(self), node.left.type, node.type)
        right = self.convert(node.right.accept(self), node.right.type, node.type)
        return self.gen_checked(node.op, left, right, self.llvm_type(node.type))

    def gen_compare(self, node):
        left, right = node.left.accept(self), node.right.accept(self)
        if "double" in (node.left.type, node.right.type):
            left = self.convert(left, node.left.type, "double")
            right = self.convert(right, node.right.type, "double")
        return self.builder.icmp_signed(node.op, left, right)

    def gen_checked(self, op, left, right, type_):
        name = f"llvm.{OVERFLOW_INTRINSICS[op]}.with.overflow.i{type_.width}"
        if name not in self.intrinsics:
            result_type = ir.LiteralStructType([type_, I1])
            self.intrinsics[name] = ir.Function(self.module, ir.FunctionType(result_type, [type_, type_]), name=name)
        pair = self.builder.call(self.intrinsics[name], [left, right])
        value = self.builder.extract_value(pair, 0)
        overflow = self.builder.extract_value(pair, 1)
        fn = self.builder.function
        bad = fn.append_basic_block("overflow")
        good = fn.append_basic_block("ok")
        self.builder.cbranch(overflow, bad, good)
        self.builder.position_at_end(bad)
        self.printf_text("runtime error: integer overflow\n")
        self.builder.call(self.libc_exit, [const(I32, 1)])
        self.builder.unreachable()
        self.builder.position_at_end(good)
        return value
