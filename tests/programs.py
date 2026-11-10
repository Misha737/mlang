import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "src" / "compiler.py"
PROGRAMS = Path(__file__).resolve().parent / "programs"
LLI = shutil.which("lli")
LLC = shutil.which("llc")
CLANG = shutil.which("clang")
SESSIONS = ROOT / "programs"
CAN_RUN_SESSIONS = bool(LLC and CLANG) or LLI is not None


def collect_programs():
    return sorted(PROGRAMS.glob("*.mlang"))


def read_bytes(path: Path, default: bytes = b"") -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n") if path.exists() else default


def check_program(source: Path, optimize=False):
    with tempfile.TemporaryDirectory() as tmp:
        ir_path = Path(tmp) / f"{source.stem}.ll"
        flags = ["--optimize"] if optimize else []
        compiled = subprocess.run(
            [sys.executable, str(COMPILER), *flags, str(source), str(ir_path)],
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


def collect_sessions():
    return sorted(SESSIONS.glob("*.in"))


def check_session(session: Path, optimize=False):
    source = session.with_name(session.stem.rsplit("_", 1)[0] + ".mlang")
    flags = ["--optimize"] if optimize else []
    with tempfile.TemporaryDirectory() as tmp:
        ir_path = Path(tmp) / "program.ll"
        compiled = subprocess.run(
            [sys.executable, str(COMPILER), *flags, str(source), str(ir_path)],
            capture_output=True,
            text=True,
        )
        if compiled.returncode != 0:
            return [f"compilation failed: {compiled.stderr.strip()}"]
        if LLC and CLANG:
            obj_path = Path(tmp) / "program.o"
            exe_path = Path(tmp) / "program"
            for command in (
                [LLC, "-filetype=obj", "-relocation-model=pic", str(ir_path), "-o", str(obj_path)],
                [CLANG, "-fPIE", str(obj_path), "-o", str(exe_path)],
            ):
                built = subprocess.run(command, capture_output=True, text=True)
                if built.returncode != 0:
                    return [f"{Path(command[0]).name} failed: {built.stderr.strip()}"]
            run_command = [str(exe_path)]
        else:
            run_command = [LLI, str(ir_path)]
        run = subprocess.run(run_command, input=read_bytes(session), capture_output=True)

    expected = read_bytes(session.with_suffix(".expected"))
    problems = []
    if run.returncode != 0:
        problems.append(f"exit code {run.returncode}, expected 0")
    if run.stdout.replace(b"\r\n", b"\n") != expected:
        problems.append(
            f"output mismatch\n--- expected\n{expected.decode('utf-8', 'replace')}"
            f"--- actual\n{run.stdout.decode('utf-8', 'replace')}"
        )
    return problems
