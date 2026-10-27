# Compiler

`mlang` is a compiler for a small imperative language. Source programs are compiled to LLVM IR via `llvmlite`.

## The language

A small statically typed imperative language. The full grammar is in [grammar.ebnf](grammar.ebnf). A program is a sequence of statements that must end with an `exit`.

```
int a
int b = 7
a = 3
if a == b:
    exit 1
exit a + b
```

### Lexical rules

- One statement per line; the end of a line ends the statement. Blank lines are ignored.
- Identifiers: letters, digits and `_`, not starting with a digit. Names are case-sensitive.
- Keywords: `int double bool const exit true false if else while`.

### Types

Three types, all without a fractional part:

| Type     | Size           |
| -------- | -------------- |
| `int`    | signed 32 bits |
| `double` | signed 64 bits |
| `bool`   |                |

`double` is the wide integer type (it is not a floating-point type). Literals are decimal integers (`42`) and `true`/`false`; a literal with a dot (`1.5`) is a lexical error. The type of an integer literal depends on its value: it is `int` if it fits in 32 bits, otherwise `double`.

Mixing the two integer types promotes to the wider one: `int + double` is `double`, and an `int` can be assigned to a `double` variable. The other direction (`double` to `int`) is not allowed implicitly.

```
int count = 10
double big = 5000000000
double total = count + big
bool done = false
```

### Declarations

`type [const] name [= expr]`. The initializer is optional. `const` goes after the type.

```
int x
double const limit = 5000000000
bool const ready = true
```

### Assignment

`name = expr`

```
int x
x = 5
x = x * 2 + 1
```

### Expressions

| Operator  | Meaning               | Precedence |
| --------- | --------------------- | ---------- |
| `!`       | logical not           | highest    |
| `*`       | multiplication        |            |
| `+` `-`   | addition, subtraction |            |
| `==` `!=` | equality, inequality  | lowest     |

`*`, `+` and `-` are left-associative. A comparison cannot be chained: `a == b == c` is a syntax error.

```
int a = 1 + 2 * 3
bool same = a == 7
bool other = !same
```

### Conditionals

`if expr:` followed by an indented block, with an optional `else:` block at the same indentation. Every block must contain at least one statement (a block consisting only of `exit` counts) and blocks can be nested.

```
int a = 3
if a == 3:
    a = 0
else:
    if a != 5:
        a = 1
exit a
```

### Loops

`while expr:` followed by an indented block with at least one statement.

```
int i = 0
while i != 10:
    i = i + 1
exit i
```

### Exit

`exit expr` ends the program and gives the value of the expression. It is required as the last statement of the program. It may also appear as the last statement of a block, but nothing can follow it in that block.

```
int a = 2
if a == 2:
    exit 1
exit a * 3
```

### Overflow checks

`int` is the range -2147483648 to 2147483647 and `double` is -9223372036854775808 to 9223372036854775807. There is no unary minus, so negative values are produced by subtraction (`0 - 5`). The checks belong to the semantic stage (the parser only records literals as text):

- A literal outside the 64-bit range is a compile-time error. A literal that does not fit in `int` has type `double`.
- `+`, `-` and `*` whose result does not fit the result type are an overflow error: the `int` range when both operands are `int`, the `double` range when at least one operand is `double`. If the operands are known at compile time it is reported at compile time, otherwise the generated program checks the result at run time and stops with an error instead of wrapping around.
- Promotion happens before the check: in `int + double` the sum is computed as `double`, so it is checked against the `double` range, not the `int` one.
- Assigning a value to a variable of a narrower type is a type error, not a silent truncation.
- `bool` has no arithmetic.

```
int big = 2147483647
int boom = big + 1
double wide = big + 5000000000
double bad = 9223372036854775808
```

Here `big + 1` is an overflow error (it is not wrapped to -2147483648), `big + 5000000000` is fine because the sum is a `double`, and `9223372036854775808` does not fit even in `double`.

### Errors

A lexical or syntax error is reported as one line on stderr, `compilation error: line L:C: message`, with a non-zero exit code and no other output.

```
compilation error: line 1:8: expected expression, found end of line
```

## Environment setup

Reference environment: Ubuntu 24.04 (native Linux, WSL 2, Multipass, or Docker).

1. Install the LLVM toolchain:

```bash
   sudo apt update
   sudo apt install -y llvm clang python3 python3-venv python3-pip binutils file
   llc --version
   clang --version
```

2. Create a virtual environment and install `llvmlite`:

```bash
   python3 -m venv ~/lcd
   source ~/lcd/bin/activate
   pip install 'llvmlite==0.49.*'
   python3 -c "import llvmlite.binding as b; print(b.llvm_version_info)"   # (22, 1, 0)
```

Activate the virtual environment (`source ~/lcd/bin/activate`) in every new shell before running the compiler or the tests. Keep this exact `llvmlite` version for the whole term.

## Running the compiler

```bash
python3 compiler.py input.mlang output.ll
```

To print the token list produced by the lexer (text, kind and `line:col` of each token) instead of compiling:

```bash
python3 compiler.py --tokens input.mlang
```

To print the abstract syntax tree built by the parser instead of compiling:

```bash
python3 compiler.py --ast input.mlang
```

To run the generated IR directly, without linking:

```bash
lli output.ll
```

To produce a native executable:

```bash
llc -filetype=obj -relocation-model=pic output.ll -o output.o
clang -fPIE output.o -o program
./program
```

## Running the tests

Install `pytest`:

```bash
pip install pytest
```

Run the suite from the repository root:

```bash
python3 -m pytest tests/
```

To run every case with a per-case report that lists the failures:

```bash
python3 tests/run_tests.py
```
