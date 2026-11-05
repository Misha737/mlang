import subprocess
import sys

import pytest

from cases import COMPILER
from programs import LLI, PROGRAMS, check_program

OPT = PROGRAMS.parent / "opt"


def collect_opt():
    return sorted(OPT.glob("*.mlang"))


@pytest.mark.parametrize("source", collect_opt(), ids=lambda p: p.stem)
def test_optimized_tree(source):
    expected = source.with_suffix(".ast").read_text().rstrip("\n")
    result = subprocess.run(
        [sys.executable, str(COMPILER), "--optimize", "--ast", str(source)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip("\n") == expected


@pytest.mark.skipif(LLI is None, reason="lli is not installed")
@pytest.mark.parametrize("optimize", [False, True], ids=["plain", "optimized"])
@pytest.mark.parametrize("source", collect_opt(), ids=lambda p: p.stem)
def test_optimized_output(source, optimize):
    problems = check_program(source, optimize=optimize)
    assert not problems, "\n".join(problems)
