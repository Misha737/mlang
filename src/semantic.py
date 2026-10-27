from entities import *
from ast_nodes import *

def error_at(node, message):
    return CompileError(f"line {node.line}:{node.col}: {message}")

class SemanticChecker:
    def __init(self):
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
            struct.accept(self)
        for function in node.functions:
            self.declare_function(function)
        for struct in node.structs:
            for method in struct.methods:
                method.accept(self)
        for function in node.functions:
            function.accept(self)
        self.scopes.append({})
        for statement in node.statements:
            statement.accept(self)
        node.exit.accept(self)
        self.scopes.pop()
        self.finish_member_calls()
