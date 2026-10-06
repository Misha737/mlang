class Token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind!r}, {self.text!r}, {self.line}:{self.col})"

class CompileError(Exception):
    pass

KEYWORDS = {
    b"int": "keyword",
    b"double": "keyword",
    b"bool": "keyword",
    b"const": "keyword",
    b"exit": "keyword",
    b"true": "keyword",
    b"false": "keyword",
    b"if": "keyword",
    b"else": "keyword",
    b"while": "keyword",
}

ARITHMETIC_OPERATORS = ["+", "-", "*"]

TYPE_NAMES = [ "int", "double", "bool" ]
