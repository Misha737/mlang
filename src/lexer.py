from entities import *

def is_alpha(b: int) -> bool:
    return b == 0x5F or (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A)

def is_digit(b: int) -> bool:
    return 0x30 <= b <= 0x39

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
            if line_start and spaces and byte not in (0x20, 0x0D, 0x0A, -1):
                error("indentation must be a multiple of 4 spaces")
            if line_start and byte not in (0x20, 0x09, 0x0D, 0x0A, -1):
                while depth < tabs:
                    tokens.append(Token("INDENT", "", line, tab_cols[depth]))
                    depth += 1
                while depth > tabs:
                    tokens.append(Token("DEDENT", "", line, col))
                    depth -= 1
                line_start = False
            if byte == -1:
                pass
            elif byte == 0x20:                     # space
                if line_start:
                    spaces += 1
                    if spaces == 4:
                        tab_cols.append(col - 3)
                        tabs += 1
                        spaces = 0
            elif byte == 0x0D:                     # \r
                pass
            elif byte == 0x09:                     # tab
                if line_start:
                    tab_cols.append(col)
                    tabs += 1
            elif byte == 0x0A:                     # \n
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
            elif byte == 0x3D:                     # =
                state = "EQ"
            elif byte == 0x21:                     # !
                state = "BANG"
            elif is_arithmetic(byte):
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
            elif byte == 0x3A:                     # :
                i += 1; col += 1
                emit("colon")
                i -= 1; col -= 1
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

        elif state == "EQ":
            if byte == 0x3D:                       # ==
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
                state = "START"
            else:
                emit("operator")                # =
                state, advance = "START", False

        elif state == "BANG":
            if byte == 0x3D:                       # !=
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
                state = "START"
            else:
                emit("operator")                # !
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
