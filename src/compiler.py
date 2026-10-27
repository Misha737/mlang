import sys
import argparse
from entities import CompileError
from lexer import lex
from parser import parse
from semantic import SemanticChecker
from generator import CodeGenerator

def main():
    args = parse_args()
    data_source = read_source(args.source)
    try:
        tokens = lex(data_source)
        if args.tokens:
            for token in tokens:
                print(f"{token.text!r} {token.kind} {token.line}:{token.col}")
            return
        tree = parse(tokens)
        if args.ast:
            print(tree.dump())
            return
        if args.output is None:
            sys.exit("compiler.py: error: the following arguments are required: output")
        SemanticChecker().check(tree)
        module = CodeGenerator(tree).generate()
        with open(args.output, "w") as file:
            file.write(str(module))
    except CompileError as e:
        print(f"compilation error: line {e}", file=sys.stderr)
        sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="mlang compiler")
    parser.add_argument("source")
    parser.add_argument("output", nargs="?")
    parser.add_argument("-a", "--ast", action="store_true")
    parser.add_argument("-t", "--tokens", action="store_true")
    return parser.parse_args()

def read_source(source_path):
    with open(source_path, "rb") as file:
        return file.read()

if __name__ == "__main__":
    main()
