import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "src" / "compiler.py"
CASES = Path(__file__).resolve().parent / "cases"


def collect(kind: str):
    return sorted(CASES.joinpath(kind).glob("*.mlang"))


def run_compiler(source: Path):
    return subprocess.run(
        [sys.executable, str(COMPILER), "--ast", str(source)],
        capture_output=True,
        text=True,
    )


def check_ok(source: Path):
    expected = source.with_suffix(".ast").read_text().rstrip("\n")
    result = run_compiler(source)
    problems = []
    if result.returncode != 0:
        problems.append(f"exit code {result.returncode}, expected 0")
    if result.stderr:
        problems.append(f"unexpected stderr: {result.stderr.strip()}")
    if result.stdout.rstrip("\n") != expected:
        problems.append(f"AST mismatch\n--- expected\n{expected}\n--- actual\n{result.stdout.rstrip()}")
    return problems


def check_err(source: Path):
    expected = source.with_suffix(".err").read_text().rstrip("\n")
    result = run_compiler(source)
    problems = []
    if result.returncode == 0:
        problems.append("exit code 0, expected non-zero")
    if result.stdout:
        problems.append(f"unexpected stdout: {result.stdout.strip()}")
    if result.stderr.rstrip("\n") != expected:
        problems.append(f"error mismatch\n--- expected\n{expected}\n--- actual\n{result.stderr.rstrip()}")
    elif "\n" in expected:
        problems.append("error must be a single line")
    return problems
