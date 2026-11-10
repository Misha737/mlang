from entities import *

def is_alpha(b: int) -> bool:
    return b == ord('_') or (ord('A') <= b <= ord('Z')) or (ord('a') <= b <= ord('z'))

def is_digit(b: int) -> bool:
    return ord('0') <= b <= ord('9')

def is_arithmetic(b: int) -> bool:
    return b in [ ord(x) for x in ARITHMETIC_OPERATORS ]

def lex(data: bytes):
    lines = []
    tokens = []
    state, start, line, col = "START", 0, 1, 1
    i = 0
    data_len = len(data)
    line_start = True
    tabs = 0
    spaces = 0
    depth = 0
    tab_cols = []

    def get_start_col():
        return col - (i - start)

    def text():
        return data[start:i].decode("ascii")

    def emit(kind, txt=None):
        nonlocal line_start
        tokens.append(Token(kind, txt if txt is not None else text(), line, get_start_col()))
        line_start = False

    def error(msg):
        raise CompileError(f"{line}:{col}: {msg}")

    while i <= data_len:
        byte = data[i] if i < data_len else -1
        advance = True

        if state == "START":
            start = i
            if line_start and spaces and byte not in (ord(' '), ord('\r'), ord('\n'), -1):
                error("indentation must be a multiple of 4 spaces")
            if line_start and byte not in (ord(' '), ord('\t'), ord('\r'), ord('\n'), -1):
                while depth < tabs:
                    tokens.append(Token("INDENT", "", line, tab_cols[depth]))
                    depth += 1
                while depth > tabs:
                    tokens.append(Token("DEDENT", "", line, col))
                    depth -= 1
                line_start = False
            if byte == -1:
                pass
            elif byte == ord(' '):
                if line_start:
                    spaces += 1
                    if spaces == 4:
                        tab_cols.append(col - 3)
                        tabs += 1
                        spaces = 0
            elif byte == ord('\r'):
                pass
            elif byte == ord('\t'):
                if line_start:
                    tab_cols.append(col)
                    tabs += 1
            elif byte == ord('\n'):
                if not line_start:
                    tokens.append(Token("NL", "\n", line, col))
                line += 1
                col = 0
                line_start, tabs, spaces = True, 0, 0
                tab_cols = []
            elif is_alpha(byte):
                state = "IDENT"
            elif is_digit(byte):
                state = "INT"
            elif byte == ord('='):
                state = "EQ"
            elif byte == ord('!'):
                state = "BANG"
            elif is_arithmetic(byte):
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
            elif byte == ord(':'):
                i += 1; col += 1
                emit("colon")
                i -= 1; col -= 1
            elif byte == ord('('):
                emit("lbracket", '(')
            elif byte == ord(')'):
                emit("rbracket", ')')
            elif byte == ord(','):
                emit("coma", ',')
            elif byte == ord('{'):
                emit("lbrace", '{')
            elif byte == ord('}'):
                emit("rbrace", '}')
            elif byte == ord('.') and tokens and tokens[-1].kind in ("ident", "rbracket"):
                emit("dot", '.')
            elif byte == ord('"'):
                state = "STRING"
            else:
                error(f"unexpected character {chr(byte)!r}")

        elif state == "IDENT":
            if byte != -1 and (is_alpha(byte) or is_digit(byte)):
                pass
            else:
                word = data[start:i]
                emit(KEYWORDS.get(word, "ident"), word.decode("ascii"))
                state, advance = "START", False

        elif state == "INT":
            if byte != -1 and is_digit(byte):
                pass
            elif byte != -1 and is_alpha(byte):
                error("invalid number: letter right after digits")
            else:
                emit("number")
                state, advance = "START", False

        elif state == "STRING":
            if byte == ord('"'):
                emit("string", data[start + 1:i].decode("utf-8", errors="replace"))
                state = "START"
            elif byte in (ord('\n'), -1):
                raise CompileError(f"{line}:{get_start_col()}: unterminated string")

        elif state == "EQ":
            if byte == ord('='):
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
                state = "START"
            else:
                emit("operator")
                state, advance = "START", False

        elif state == "BANG":
            if byte == ord('='):
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
                state = "START"
            else:
                emit("operator")
                state, advance = "START", False

        if advance:
            i += 1
            col += 1

    if not line_start:
        tokens.append(Token("NL", "\n", line, col - 1))
    for _ in range(depth):
        tokens.append(Token("DEDENT", "", line, col - 1))
    tokens.append(Token("EOF", "", line, col - 1))
    return tokens
