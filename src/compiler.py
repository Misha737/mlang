import sys
import argparse
from entities import CompileError
from lexer import lex
from parser import parse

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
    except CompileError as e:
        print(f"compilation error: line {e}", file=sys.stderr)
        sys.exit(1)
    if args.ast:
        print(tree.dump())

def parse_args():
    parser = argparse.ArgumentParser(description="mlang compiler")
    parser.add_argument("source")
    parser.add_argument("-a", "--ast", action="store_true")
    parser.add_argument("-t", "--tokens", action="store_true")
    return parser.parse_args()

def read_source(source_path):
    with open(source_path, "rb") as file:
        return file.read()

if __name__ == "__main__":
    main()
