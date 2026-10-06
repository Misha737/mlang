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

    def get_start_col():
        return col - (i - start)

    def text():
        return data[start:i].decode("ascii")

    def emit(kind, txt=None):
        nonlocal line_start
        tokens.append(Token(kind, txt if txt is not None else text(), line, get_start_col()))
        if kind != "TAB":
            line_start = False

    def error(msg):
        raise CompileError(f"{line}:{col}: {msg}")

    while i <= data_len:
        b = data[i] if i < data_len else -1
        advance = True

        if state == "START":
            start = i
            if b == -1:
                pass
            elif b == 0x20 or b == 0x0D:        # space, \r
                pass
            elif b == 0x09:                     # tab
                if line_start:
                    tokens.append(Token("TAB", "\t", line, col))
                    tabs += 1
            elif b == 0x0A:                     # \n
                if line_start:
                    for _ in range(tabs):
                        tokens.pop()
                else:
                    tokens.append(Token("NL", "\n", line, col))
                line += 1
                col = 0
                line_start, tabs = True, 0
            elif is_alpha(b):
                state = "IDENT"
            elif is_digit(b):
                state = "INT"
            elif b == 0x3D:                     # =
                state = "EQ"
            elif b == 0x21:                     # !
                state = "BANG"
            elif is_arithmetic(b):
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
            elif b == 0x3A:                     # :
                i += 1; col += 1
                emit("colon")
                i -= 1; col -= 1
            else:
                error(f"unexpected character {chr(b)!r}")

        elif state == "IDENT":
            if b != -1 and (is_alpha(b) or is_digit(b)):
                pass
            else:
                word = data[start:i]
                emit(KEYWORDS.get(word, "ident"), word.decode("ascii"))
                state, advance = "START", False

        elif state == "INT":
            if b != -1 and is_digit(b):
                pass
            elif b == 0x2E:                     # .
                state = "DOT"
            elif b != -1 and is_alpha(b):
                error("invalid number: letter right after digits")
            else:
                emit("number")
                state, advance = "START", False

        elif state == "DOT":
            if b != -1 and is_digit(b):
                state = "FRAC"
            else:
                error("invalid number: digit expected after '.'")

        elif state == "FRAC":
            if b != -1 and is_digit(b):
                pass
            elif b == 0x2E or (b != -1 and is_alpha(b)):
                error("invalid number")
            else:
                emit("number")
                state, advance = "START", False

        elif state == "EQ":
            if b == 0x3D:                       # ==
                i += 1; col += 1
                emit("operator")
                i -= 1; col -= 1
                state = "START"
            else:
                emit("operator")                # =
                state, advance = "START", False

        elif state == "BANG":
            if b == 0x3D:                       # !=
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
        tokens.append(Token("NL", "\n", line, col))
    else:
        for _ in range(tabs):
            tokens.pop()
    tokens.append(Token("EOF", "", line, col))
    return tokens
