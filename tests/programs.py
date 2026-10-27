import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "src" / "compiler.py"
PROGRAMS = Path(__file__).resolve().parent / "programs"
LLI = shutil.which("lli")


def collect_programs():
    return sorted(PROGRAMS.glob("*.mlang"))


def read_bytes(path: Path, default: bytes = b"") -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n") if path.exists() else default


def check_program(source: Path):
    with tempfile.TemporaryDirectory() as tmp:
        ir_path = Path(tmp) / f"{source.stem}.ll"
        compiled = subprocess.run(
            [sys.executable, str(COMPILER), str(source), str(ir_path)],
            capture_output=True,
            text=True,
        )
        if compiled.returncode != 0:
            return [f"compilation failed: {compiled.stderr.strip()}"]
        run = subprocess.run(
            [LLI, str(ir_path)],
            input=read_bytes(source.with_suffix(".in")),
            capture_output=True,
        )

    expected_out = read_bytes(source.with_suffix(".out"))
    expected_code = int(read_bytes(source.with_suffix(".exit"), b"0").strip())
    problems = []
    if run.returncode != expected_code:
        problems.append(f"exit code {run.returncode}, expected {expected_code}")
    if run.stdout != expected_out:
        problems.append(
            f"output mismatch\n--- expected\n{expected_out.decode('utf-8', 'replace')}"
            f"--- actual\n{run.stdout.decode('utf-8', 'replace')}"
        )
    return problems
