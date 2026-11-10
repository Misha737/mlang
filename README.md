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
- Keywords: `int double bool const exit true false if else while struct print read private public`.
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

### Encapsulation

A field or a member function of a struct is `public` or `private`. The word stands first on the member's line, before the type: `private int const id`, `private int helper():`. **A member without the word is `public`**, so every program that was valid before this feature means the same as before.

**Rule: who may name a private member.** A private member can be named only inside the member functions of the struct that declares it. Everything else is outside: the statements of the program, global functions, and member functions of other structs. Outside, reading a private field, assigning it, or calling a private member function is an error that names the member. The rule is about the type, not the object: a member function of `Point` may use the private fields of any `Point`, for example of a local one. A chain `a.b.c` is checked link by link against the struct that declares each field, so a struct that has a `Point` field cannot reach a private field of that `Point` through it.

**Rule: inside the struct.** A bare name or a bare call inside a member function always looks into its own struct, so its private fields and private member functions can be used freely.

**Rule: objects and `print`.** `{...}` gives a value to every field, private ones too: the language has no constructors, so `{...}` is the only way to make an object, and `private int const` is a value that is set once and read only by the member functions. `print` writes every field, private ones included: it is a dump of the object, not a use of a field by name.

**Rule: private and constant.** The two rules are independent. When both forbid a use, the private error is reported.

`private` exists only in the checker. The layout of the struct and the generated IR are the same as for `public`.

```
struct Account:
    private int balance
    int owner
    int deposit(int amount):
        balance = balance + amount
        exit balance

Account a {100, 7}
print(a.deposit(50))
print(a.owner)
print(a.balance)
exit 0
```

The last `print` is an error: `compilation error: line 11:9: cannot access private field 'balance' of struct 'Account'`. Without it the program prints `150` and `7`.

```
struct Temperature:
    int celsius
    private int twice(int v):
        exit v * 2
    private int to_f(int c):
        exit twice(c) + 32
    int fahrenheit():
        exit to_f(celsius)

Temperature t {20}
print(t.fahrenheit())
```

This prints `72`. `t.to_f(20)` in the last line would be an error: `cannot call private member function 'to_f' of struct 'Temperature'`.

Follows: `private_field_access`, `private_method_helper`, `private_const_field`, `struct_access_modifiers` (parse only). Breaks: `private_field_read`, `private_field_assign`, `private_method_call`, `private_field_other_struct`.

**IR of a private field.** This is the output of `python3 src/compiler.py` for a shorter `Account` than the one above: only `private int balance` and `deposit`, and `Account a {100}` followed by `print(a.deposit(50))`. `; ...` marks lines left out.

```
%"struct.Account" = type {i32}
define i32 @"ml.Account.deposit"(%"struct.Account"* %".1", i32 %".2")
body:
  store i32 %".2", i32* %".4"
  %".6" = getelementptr %"struct.Account", %"struct.Account"* %".1", i32 0, i32 0
  %".7" = getelementptr %"struct.Account", %"struct.Account"* %".1", i32 0, i32 0
  %".8" = load i32, i32* %".7"
  %".9" = load i32, i32* %".4"
  %".10" = call {i32, i1} @"llvm.sadd.with.overflow.i32"(i32 %".8", i32 %".9")
  ; ...
ok:
  store i32 %".11", i32* %".6"
  ; ...
; in main
  %".2" = alloca %"struct.Account"
  store i32 100, i32* %".3"
  %".5" = call i32 @"ml.Account.deposit"(%"struct.Account"* %".2", i32 50)
```

The struct type `{i32}` keeps `balance` as one unnamed field with no visibility, so `private` leaves no trace: the IR of this program is identical, line for line, to the IR of the same program with the word removed. Inside `deposit` the object comes in as a pointer, the hidden first parameter `%".1"`, and `balance` is written and read through `getelementptr ... i32 0, i32 0` on it, the same instructions a public field would produce. In `main` the call passes the address of the object, not a copy, so `deposit` changes the caller's `a`; the access check was done earlier, in the checker, which is why no instruction guards the private field.

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

## Optimizer

`--optimize`, anywhere on the command line, runs the optimizer on the checked tree before code generation. The optimizer keeps what the program prints, reads and returns; it only changes how. With `--ast` the tree is printed after the optimizer, and the semantic checker has run first, so a semantic error is reported as usual.

```bash
python3 src/compiler.py --optimize input.mlang output.ll
python3 src/compiler.py --optimize --ast input.mlang
```

The optimizer is a list of passes in `src/optimizer.py`: unused variables, unused functions, inlining. Each pass is repeated until it changes nothing, and the whole list is repeated until no pass changes anything, because one pass can give work to another (inlining leaves a function nobody calls, and its parameters may then be unread).

### Unused variables

A variable that is declared and never read is removed together with its declaration and all of its assignments. Removing it can leave another variable unread, so the pass repeats: in `int a = 5`, `int b = a + 1`, `int c = b * 2`, first `c` goes, then `b`, then `a`.

- **What is a read.** Any use of the variable inside an expression: an initializer, the right side of an assignment, a condition, an argument, `print`, `exit`, the object in `p.x` or `p.f()`. The target of an assignment (`d = 7`, `p.x = 7`) is not a read. A member function call on an object is a read of the object.
- **Scopes and shadowing.** Reads are counted per declaration, not per name. An inner `int z` that nobody reads is removed even when an outer `z` with the same name is read.
- **What is never removed.** Parameters and the fields of a struct. Fields are not variables, and a function may read them.
- **Expressions with effects are never dropped.** When the value of a removed declaration or assignment contains a call, `read()`, or an `+`, `-` or `*` that is checked at run time (its operands are not known at compile time, so it may print `runtime error: integer overflow` and stop the program), the expression stays as a statement of its own, in the original order. Only the variable is removed: `int x = read()` becomes `read()`, and `int m = n + 1` becomes `n + 1`. An expression whose operands are constants is checked at compile time and is dropped.
- **A variable that reads itself stays.** `x = x + 1` reads `x`, so a variable that is only updated from its own value is not removed.

Tests: `tests/opt/unused_var_cascade` (the chain above, with an assignment to a removed variable) and `tests/opt/unused_var_keeps_effects` (`read()` and a call whose result is unused, and an unused inner variable that hides a used outer one). Each has the expected tree after `--optimize --ast` (`.ast`) and the expected output (`.out`, `.in`); the output is the same with and without the flag. `tests/programs` are also run with `--optimize` and must give the same output.

### Unused functions

A function that nobody calls is removed with its whole body, and then the pass looks again: the body that went may have been the only caller of another function. In `tests/opt/unused_func_chain`, `a` calls `b`, `b` calls `c`, and only `used` is called from the program: `a` goes first, then `b`, then `c`.

- **What is a call.** Any call that the checker resolved to the function: `f(x)`, `p.m()`, and a bare `m()` inside a member function. Calls are counted in the statements of the program and in the bodies of the functions that are still there, so a call inside a body that has just been removed no longer counts in the next round.
- **Member functions too.** The program is not a library: only `main` is called from outside, so a member function nobody calls is removed in the same way, public or private. The fields of its struct stay.
- **A function that calls only itself.** A call from a function to itself does not count. A recursive function that nobody else calls is removed.
- **Mutual recursion stays.** If `a` calls `b` and `b` calls `a`, and nobody else calls either, each has a caller, so neither is removed. This is the same limit as reference counting.
- **A removed function has no effect on the output:** it was never run.

Tests: `tests/opt/unused_func_chain` (the chain above; `used` is called twice, so it is not inlined) and `tests/opt/unused_func_methods` (an unused member function that is the only caller of another member function, a recursive function that only calls itself, and a recursive function and two member functions that stay because they are called).

### Inlining

A function that is called exactly once is replaced at its call site by its body, and the function is removed.

- **Which functions.** A global function that is called exactly once in the whole program, does not call itself, and whose body is a straight line: any statements, ending with one `exit`, and no other `exit` anywhere in it, not even inside an `if` or a `while`. Member functions are not inlined.
- **Which call sites.** The call must be the whole value of a statement: the initializer of a declaration, the right side of an assignment, the argument of `print`, the value of `exit`, or a statement on its own. The statements of the body are put before that statement, in the same block, so the order in which things happen does not change: the arguments are evaluated first, then the body, then the statement. A call nested in a bigger expression (`1 + f(x)`), or in the condition of an `if` or `while`, is left alone. A call that is an argument of another call (`f(g(x))`) is inlined in the next round: once `f` is inlined, `g(x)` is the initializer of the parameter of `f`.
- **What happens.** Each parameter becomes a declaration initialised with the argument, in order. The statements of the body follow. The `exit` of the body is dropped and its value stands where the call stood. For a call on its own, the value is kept only when it has an effect (a call, `read()`, or `+ - *` checked at run time), as in unused variables.
- **Names.** Every parameter and every variable declared in the body is renamed to `function_name`, for example `area_w`, with a number added if that name is already taken anywhere in the program. Nothing in the body can collide with a name of the caller, which is also why `w` and `result` of the caller and of `area` below stay apart.
- **Left alone.** A function that is called twice or never (never means it is removed as unused), a recursive function, a function with an `exit` inside an `if` or a `while`, a member function, and a call that is not the whole value of a statement.

```
int area(int w, int h):
    int result = w * h
    exit result + 1

int w = 3
int n = 4
int result = area(w, n)
print(result)
exit 0
```

With `--optimize --ast` the statements of the program are `w`, `n`, then `area_w = w`, `area_h = n`, `area_result = area_w * area_h`, `result = area_result + 1`, and `print(result)`; `area` is gone.

**IR before and after.** The start of `area`, the call to it in `main`, and the same place in `main` with `--optimize`; `; ...` marks lines left out.

Without `--optimize`:

```
define i32 @"ml.area"(i32 %".1", i32 %".2")
body:
  store i32 %".1", i32* %".4"
  store i32 %".2", i32* %".6"
  ; ...
; in main
  %".7" = load i32, i32* %".2"
  %".8" = load i32, i32* %".4"
  %".9" = call i32 @"ml.area"(i32 %".7", i32 %".8")
  store i32 %".9", i32* %".6"
```

With `--optimize` (there is no `ml.area` any more):

```
; in main
  %".7" = load i32, i32* %".2"
  store i32 %".7", i32* %".6"
  %".10" = load i32, i32* %".4"
  store i32 %".10", i32* %".9"
  %".13" = load i32, i32* %".6"
  %".14" = load i32, i32* %".9"
  %".15" = call {i32, i1} @"llvm.smul.with.overflow.i32"(i32 %".13", i32 %".14")
  ; ...
```

Without the flag, `main` calls `@"ml.area"`, which has its own `alloca` slots, stores its two parameters into them, and returns the result in a register. With the flag there is no `call` and no `ml.area` (`%".6"` and `%".9"` are the new slots of `area_w` and `area_h`): the two argument values are stored straight into the new slots of `main`, and the multiplication and the addition run inline, so the overflow checks stay and the output is the same.

Tests: `tests/opt/inline_names` (the program above, with names that collide), `tests/opt/inline_shapes` (the call on its own, on the right side of an assignment, in `print` inside an `if`, and an argument that is read from input) and `tests/opt/inline_left_alone` (an `exit` inside an `if`, a recursive function, a function called twice, and a call inside a bigger expression: nothing is inlined).

## The real program: ATM

`programs/atm.mlang` is an interactive ATM that a person can use from the terminal.

- It prints a prompt before every input and reads a command number: `1` deposit, `2` withdraw, `3` show the balance, `4` print a report, `0` quit. Deposit and withdraw then ask for an amount; any other command prints `Unknown command`.
- The money lives in the struct `Account`. Its fields `balance` and `operations` are **private**, so the statements of the program can only go through the public member functions `deposit`, `withdraw`, `show` and `report`; writing `acc.balance` there is a compile error.
- Encapsulation also keeps the rules in one place: the private member function `can_afford` decides whether a withdrawal is allowed, and the private `record` counts the operations. Only `deposit` and `withdraw` call them.
- The language has no `<` or `>`, so the global function `less` compares two numbers with `is_negative`, which counts up and down from zero until it meets the number. `valid` rejects negative amounts (`Invalid amount`).
- It uses a struct with member functions, global functions (`is_negative`, `less`, `valid`), `read`, `print`, loops and `if`, and the private members.

To build the native binary and run it (`llc` and `clang` are installed in Environment setup):

```bash
python3 src/compiler.py programs/atm.mlang atm.ll
llc -filetype=obj -relocation-model=pic atm.ll -o atm.o
clang -fPIE atm.o -o atm
./atm
```

Two sessions are recorded. `programs/atm_1.in` is what the user types and `programs/atm_1.expected` is the exact output, prompts included; `atm_2` is the same for the second session. Each session is run with:

```bash
./atm < programs/atm_1.in | diff - programs/atm_1.expected
./atm < programs/atm_2.in | diff - programs/atm_2.expected
```

`diff` prints nothing when the output is exactly the expected one. The first session deposits, withdraws more than the balance, and enters negative amounts and an unknown command; the second starts with an empty account, withdraws the whole balance, and deposits `0`. Building with `python3 src/compiler.py --optimize ...` gives the same output.

## Running the tests

Install `pytest`:

```bash
pip install pytest
```

Run the suite from the repository root:

```bash
python3 -m pytest tests/
```

There are five groups of tests:

- `tests/cases/ok`: a valid program and the abstract syntax tree the parser must print for it (`--ast`).
- `tests/cases/err`: an invalid program and the one-line error the compiler must print. These run the whole compiler, so syntax and semantic errors are both covered. Each one is run twice, plain and with `--optimize`, and must give the same error.
- `tests/programs`: complete programs. Each one is compiled to LLVM IR, run with `lli`, and its standard output and exit status are compared with `<name>.out` and `<name>.exit` (0 if absent); `<name>.in` is fed to standard input. These tests are skipped when `lli` is not installed. Each program is run twice, plain and with `--optimize`, and must give the same result.
- `tests/opt`: programs for the optimizer. Each has the tree expected after `--optimize --ast` (`<name>.ast`) and is run plain and with `--optimize` like `tests/programs`.
- `programs/*.in` with `programs/*.expected`: the recorded sessions of the real program. The program is compiled, built into a native binary with `llc` and `clang` when both are installed (otherwise run with `lli`), fed the `.in` file, and its output is compared with the `.expected` file. Each session runs plain and with `--optimize`. These tests are skipped when none of the tools is installed.

To run every case with a per-case report that lists the failures:

```bash
python3 tests/run_tests.py
```
