# Compiler

`mlang` is a compiler for a small imperative language. Source programs are compiled to LLVM IR via `llvmlite`.

## The language

A small statically typed imperative language with `int`, `double` and `bool`, structs with member functions, global functions, `print` and `read`. The full grammar is in [grammar.ebnf](grammar.ebnf).

Every rule below is enforced by the compiler and covered by tests: a **Follows** program that obeys the rule and a **Breaks** program that violates it. Names in backticks are test names: an error case is `tests/cases/err/<name>.mlang`, a valid parse case is `tests/cases/ok/<name>.mlang`, and a program that is compiled, run and compared with its expected output is `tests/programs/<name>.mlang`. Rules that fix the exact output of a running program have no failing program; they are pinned by the expected output of the **Follows** programs instead.

```
struct Point:
    int x
    int y
    int sum():
        exit x + y

int twice(int n):
    exit n * 2

Point p {3, 4}
print(p)
print(twice(p.sum()))
exit 0
```

### Program layout

**Rule.** A program is, in this order: struct declarations, function declarations, statements, and one final `exit`. A struct or a function after the first statement is a syntax error. The `exit` is required and nothing can follow it.

Follows: `struct_and_functions`, `exit_expression`. Breaks: `struct_after_statement`, `function_after_statement`, `missing_exit`, `statement_after_exit`.

### Lexical rules

- One statement per line; the end of a line ends the statement. Blank lines are ignored.
- Blocks are made of indentation: 4 spaces or one tab per level. A block is a line that ends with `:` followed by more deeply indented lines.
- Identifiers: letters, digits and `_`, not starting with a digit. Names are case-sensitive.
- Keywords: `int double bool const exit true false if else while struct print read`.
- A string literal is `"` followed by any bytes except `"` and a newline, followed by `"`. There are no escape sequences. A string literal is allowed only as the argument of `print`.
- A `.` is allowed only right after an identifier or `)`.

Follows: `indent_with_spaces`, `unicode_string`. Breaks: `lex_indent_three_spaces`, `unterminated_string`, `lex_fraction_literal`, `string_outside_print`.

### Types

Three scalar types, all without a fractional part:

| Type     | Size           |
| -------- | -------------- |
| `int`    | signed 32 bits |
| `double` | signed 64 bits |
| `bool`   |                |

`double` is the wide integer type (it is not a floating-point type). Each `struct` declaration adds an object type with the name of the struct.

**Rule: literals.** An integer literal is `int` if it fits in 32 bits, otherwise `double`. A literal outside the 64-bit range is an error. A literal with a dot (`1.5`) is a lexical error. There is no unary minus; negative values are produced by subtraction (`0 - 5`).

```
int small = 42
double big = 5000000000
```

Follows: `double_promotion`. Breaks: `overflow_literal_too_big`, `lex_fraction_literal`.

**Rule: known types.** A type name must be `int`, `double`, `bool` or the name of a declared struct.

Follows: `struct_nested`. Breaks: `decl_unknown_type`, `struct_unknown_field_type`.

**Rule: assignability.** A value of type `T` can be stored where type `U` is expected only if `T` is `U`, or `T` is `int` and `U` is `double`. This one rule applies everywhere a value meets a type: a declaration with an initializer, an assignment, a call argument, a field value in `{...}`, and the value of `exit` inside a function. The other direction (`double` to `int`) is a type error, never a silent truncation.

```
double total = 7 + 5000000000
int back = total
```

The second line is an error.

Follows: `int_to_double_everywhere`. Breaks: `assign_double_to_int`, `call_argument_double_to_int`, `function_exit_double_in_int`, `init_wrong_type`.

### Declarations

`type [const] name [= expr]`. `const` goes after the type.

**Rule: default value.** A scalar variable declared without an initializer holds `0` (`false` for `bool`). An object has no default: it must be given a value for every field (see Objects).

```
int x
double const limit = 5000000000
bool ready
```

Follows: `uninitialized_is_zero`, `decl_const_int`. Breaks: `init_missing`.

**Rule: scope.** A name is visible from its declaration to the end of the block that contains it. A block may declare a name that an outer block already has; the inner one hides the outer one until the block ends. Declaring the same name twice in the same block is an error, and a name is not visible after its block.

```
int a = 1
if a == 1:
    int a = 2
    print(a)
print(a)
```

This prints `2` and then `1`.

Follows: `block_scope_shadow`. Breaks: `redeclare_same_scope`, `use_after_block`.

### Assignment

`name = expr`, or `name.field.field = expr` for a field of an object. The value must be assignable to the type of the target.

**Rule: constants.** A `const` variable cannot be assigned. An object declared `const` has no assignable field at any depth. A field declared `const` is never assignable, not even inside a member function; it only gets its value in the `{...}` of the object declaration.

```
int const a = 1
a = 2
```

Follows: `const_object_rules`. Breaks: `const_assign`, `assign_through_const_object`, `assign_through_const_field`, `assign_through_const_nested_chain`, `method_assigns_const_field`.

### Expressions

| Operator  | Meaning               | Precedence |
| --------- | --------------------- | ---------- |
| `!`       | logical not           | highest    |
| `*`       | multiplication        |            |
| `+` `-`   | addition, subtraction |            |
| `==` `!=` | equality, inequality  | lowest     |

`*`, `+` and `-` are left-associative. A comparison cannot be chained: `a == b == c` is a syntax error. There are no parentheses.

**Rule: operator types.** `+`, `-` and `*` take `int` or `double` operands; the result is `double` if either operand is `double`, otherwise `int`. `==` and `!=` take two numbers (`int` or `double`) or two `bool`s and give `bool`; objects and strings cannot be compared. `!` takes a `bool`. The condition of `if` and `while` must be `bool`; there is no truth value for numbers. `bool` has no arithmetic.

```
int a = 1 + 2 * 3
bool same = a == 7
bool other = !same
```

Follows: `arithmetic`, `bool_logic`. Breaks: `bool_arith`, `not_int`, `compare_int_bool`, `compare_objects`, `if_int_condition`, `while_int_condition`.

### Conditionals and loops

`if expr:` followed by an indented block, with an optional `else:` block at the same indentation. `while expr:` followed by an indented block. Every block must contain at least one statement (a block consisting only of `exit` counts), and blocks can be nested.

```
int i = 0
while i != 3:
    if i == 1:
        print(i)
    i = i + 1
```

Follows: `if_else_nested_read`, `multiplication_table`. Breaks: `if_empty_block`, `while_empty_block`, `else_without_if`, `else_misaligned`.

### Exit

`exit expr` ends the program, or, inside a function, returns from it.

**Rule: exit in the program.** The value of `exit` at the top level is the exit status of the program and must be `int`, `double` or `bool`, never an object. A `double` is cut to its low 32 bits and a `bool` is `0` or `1`. It is required as the last statement of the program. It may also appear as the last statement of a block, but nothing can follow it in that block.

Follows: `sum_exit_code`, `exit_bool`, `exit_double_truncated`. Breaks: `exit_struct`, `statement_after_block_exit`.

### Overflow checks

`int` is the range -2147483648 to 2147483647 and `double` is -9223372036854775808 to 9223372036854775807.

**Rule.** `+`, `-` and `*` whose result does not fit the result type are an overflow error: the `int` range when both operands are `int`, the `double` range when at least one operand is `double`. If the operands are known at compile time it is reported at compile time. Otherwise the generated program checks the result at run time, prints `runtime error: integer overflow` and stops with exit status 1 instead of wrapping around. Promotion happens before the check: in `int + double` the sum is computed as `double`, so it is checked against the `double` range, not the `int` one.

```
int big = 2147483647
int boom = big + 1
double wide = big + 5000000000
```

Here `big + 1` is an overflow error and `big + 5000000000` is fine because the sum is a `double`.

Follows: `double_promotion`. Breaks: `overflow_compile_time`, `runtime_overflow`.

### Objects

A `struct` declares an object type: a name, then one field per line, then optionally member functions. A struct needs at least one field.

```
struct Line:
    Point from
    Point to
    int length_x():
        exit to.x - from.x
```

**Rule: struct declarations.** Struct names are unique. Field names are unique inside a struct. A member function cannot share its name with a field or with another member function of the same struct. A struct cannot contain itself, directly or through other structs.

Follows: `struct_nested`, `struct_methods`. Breaks: `struct_without_members`, `struct_duplicate`, `struct_duplicate_field`, `method_duplicate`, `method_named_as_field`, `struct_cycle`.

**Rule: object declaration.** An object is declared as `Type [const] name {v1, v2, ...}`. There must be exactly one value per field, in the order of the fields. A field of a struct type takes a nested `{...}`; a scalar field takes an expression that is assignable to the field type (the assignability rule). `{...}` cannot be used for `int`, `double` or `bool`.

```
Line l {{1, 2}, {3, 4}}
```

Follows: `struct_nested`, `decl_struct_init_nested`. Breaks: `init_wrong_count`, `init_wrong_type`, `init_missing`, `init_nested_flat`, `init_int_with_braces`.

**Rule: whole objects.** An object can be used only through its fields and member functions. It cannot be assigned as a whole, compared, passed to a function, returned, or given to `exit`. `print` is the only place an object is used as a value.

Follows: `struct_basic`. Breaks: `assign_whole_object`, `compare_objects`, `exit_struct`.

**Rule: field access.** `a.b.c` follows fields one by one: every part before the last must be an object, and every name must be a field of the struct before it. A member function call can only be the last part: `a.b.m(args)`.

```
l.to.y = 9
print(l.to.y - l.from.x)
```

Follows: `struct_nested`, `chain_field_read_write`. Breaks: `unknown_field_read`, `unknown_field_assign`, `unknown_field_nested`, `field_of_int`, `unknown_method`.

### Functions

A function is `type name(type param, ...):` followed by an indented block. Struct declarations come first, then global functions.

```
int power(int base, int exp):
    int result = 1
    int i = 0
    while i != exp:
        result = result * base
        i = i + 1
    exit result
```

**Rule: parameter and result types.** Parameters and the result are `int`, `double` or `bool`; an object type is not allowed in either position. Parameter names inside one function are unique. Function names are unique and cannot be the name of a struct.

Follows: `power_function`, `bool_function`. Breaks: `function_param_struct_type`, `function_result_struct_type`, `duplicate_param`, `function_duplicate`, `function_named_as_struct`.

**Rule: every path returns.** The body must end with an `exit`, or with an `if`/`else` where both branches end that way (checked recursively). An `exit` only inside a `while`, or only inside an `if` without `else`, does not count. The value of `exit` must be assignable to the declared result type (the assignability rule).

Follows: `function_if_else_exit`, `fibonacci_recursive`. Breaks: `function_missing_exit`, `function_if_without_else`, `function_exit_only_in_while`, `function_exit_wrong_type`.

**Rule: calls.** A call must have exactly as many arguments as the function has parameters, and each argument must be assignable to its parameter (the assignability rule). Arguments are passed by value, and a parameter is an ordinary local variable that the function may change; the caller's variable stays as it was.

```
int bump(int a):
    a = a + 1
    exit a

int x = 1
print(bump(x))
print(x)
```

This prints `2` and then `1`.

Follows: `param_assignment`, `power_function`. Breaks: `call_too_many_arguments`, `call_too_few_arguments`, `call_argument_wrong_type`, `method_call_too_many_arguments`.

**Rule: which function a call means.** A call `f(...)` without a dot is looked up among the member functions of the struct we are inside, if any, and then among the global functions. At the top level and in a global function only the global functions are searched. A global function may call any global function, whatever the order of declaration, and itself. A name that is found nowhere is an error.

Follows: `call_member_before_global`, `function_forward_call`, `fibonacci_recursive`. Breaks: `unknown_function`.

### Member functions

A member function is declared inside a struct, after or between its fields, and is called as `object.name(args)`. It works on the object it was called on.

```
struct Counter:
    int value
    int next():
        value = value + 1
        exit value

Counter c {0}
print(c.next())
```

**Rule: name lookup inside a function.** Inside a function body a name is looked up in this order, and the first match wins:

1. the parameters and locals of the function, the innermost block first;
2. if the function is a member function, the fields of its struct;
3. nothing else. Global variables are not visible inside any function: all functions are declared before the first statement, so no global variable exists yet at that point.

So a parameter or a local that has the same name as a field hides the field, and a global variable with the same name as a field or a parameter changes nothing. A name that is found by none of these steps is an error. The same order applies to the left-hand side of an assignment.

```
struct S:
    int v
    int by_param(int v):
        exit v
    int by_field():
        exit v

int v = 100
S s {1}
print(s.by_param(7))
print(s.by_field())
print(v)
```

This prints `7`, `1` and `100`.

Follows: `name_lookup_order`. Breaks: `function_cannot_see_global`, `field_not_visible_in_plain_function`, `param_not_visible_outside`.

**Rule: constant objects.** A member function that assigns a field of its own object, or calls another member function that does, is a changing function. A changing function cannot be called on a `const` object, or on an object reached through a `const` object or a `const` field. A member function that only reads fields can be called on a `const` object.

Follows: `const_object_rules`. Breaks: `mutating_method_on_const_object`, `mutating_method_in_expression_on_const`, `mutating_method_through_const_field`, `indirect_mutating_method_on_const`.

### Output and input

**Rule: print arguments.** `print(...)` takes exactly one argument: a string literal, or an expression of type `int`, `double`, `bool`, or an object.

Follows: `print_all_types`, `hello`. Breaks: `print_empty`, `print_two_arguments`, `print_missing_open_paren`.

**Rule: print output.** Every `print` writes its text and then exactly one newline, and nothing else. The text is:

| Value            | Text                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| string literal   | the bytes between the quotes, unchanged                                               |
| `int`, `double`  | decimal digits, with a leading `-` for a negative value                               |
| `bool`           | `true` or `false`                                                                     |
| object           | `Name{field=value, field=value}`: the fields in declaration order, separated by `, ` |

A field that is itself an object is written in the same form inside the outer braces. The newline comes only after the outermost closing brace, never after a nested one.

```
S{a=1, b=5000000000, c=true, p=P{x=7}}
```

Pinned by the expected output of: `hello`, `print_all_types`, `struct_basic`, `struct_nested`, `struct_methods`, `bool_logic`.

**Rule: read.** `read()` has type `int`. It reads one whitespace-separated decimal integer from standard input each time it is evaluated, so it can be used wherever an `int` expression can. The behaviour on missing or malformed input is not defined.

```
int n = read()
print(read() + n)
```

Follows: `factorial_read`, `read_in_expression`. Breaks: `read_with_argument`.

### Errors

A lexical, syntax or semantic error is reported as one line on stderr, `compilation error: line L:C: message`, with a non-zero exit code and no other output. `L:C` is the position of the offending token or construct.

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
python3 src/compiler.py input.mlang output.ll
```

To print the token list produced by the lexer (text, kind and `line:col` of each token) instead of compiling:

```bash
python3 src/compiler.py --tokens input.mlang
```

To print the abstract syntax tree built by the parser instead of compiling:

```bash
python3 src/compiler.py --ast input.mlang
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

There are three groups of tests:

- `tests/cases/ok`: a valid program and the abstract syntax tree the parser must print for it (`--ast`).
- `tests/cases/err`: an invalid program and the one-line error the compiler must print. These run the whole compiler, so syntax and semantic errors are both covered.
- `tests/programs`: complete programs. Each one is compiled to LLVM IR, run with `lli`, and its standard output and exit status are compared with `<name>.out` and `<name>.exit` (0 if absent); `<name>.in` is fed to standard input. These tests are skipped when `lli` is not installed.

To run every case with a per-case report that lists the failures:

```bash
python3 tests/run_tests.py
```
