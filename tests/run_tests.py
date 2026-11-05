import subprocess
import sys

from cases import COMPILER, collect, check_ok, check_err
from programs import LLI, PROGRAMS, collect_programs, check_program

OPT = PROGRAMS.parent / "opt"


def main():
    failed = []
    total = 0
    for kind, check in (("ok", check_ok), ("err", check_err)):
        for source in collect(kind):
            total += 1
            problems = check(source)
            status = "FAIL" if problems else "ok  "
            print(f"{status} {kind}/{source.stem}")
            if problems:
                failed.append((f"{kind}/{source.stem}", problems))
            if kind == "err":
                total += 1
                problems = check(source, optimize=True)
                print(f"{'FAIL' if problems else 'ok  '} {kind}/{source.stem} --optimize")
                if problems:
                    failed.append((f"{kind}/{source.stem} --optimize", problems))

    if LLI is None:
        print("programs: skipped, lli is not installed")
    for source in collect_programs() if LLI else []:
        for optimize in (False, True):
            total += 1
            name = f"programs/{source.stem}" + (" --optimize" if optimize else "")
            problems = check_program(source, optimize=optimize)
            print(f"{'FAIL' if problems else 'ok  '} {name}")
            if problems:
                failed.append((name, problems))

    for source in sorted(OPT.glob("*.mlang")):
        total += 1
        expected = source.with_suffix(".ast").read_text().rstrip("\n")
        result = subprocess.run(
            [sys.executable, str(COMPILER), "--optimize", "--ast", str(source)],
            capture_output=True,
            text=True,
        )
        problems = [] if result.stdout.rstrip("\n") == expected else ["optimized tree differs from the .ast file"]
        print(f"{'FAIL' if problems else 'ok  '} opt/{source.stem}")
        if problems:
            failed.append((f"opt/{source.stem}", problems))
        for optimize in (False, True) if LLI else ():
            total += 1
            name = f"opt/{source.stem}" + (" --optimize" if optimize else "")
            problems = check_program(source, optimize=optimize)
            print(f"{'FAIL' if problems else 'ok  '} {name}")
            if problems:
                failed.append((name, problems))

    print()
    if failed:
        print(f"{len(failed)} of {total} failed:")
        for name, problems in failed:
            print(f"  {name}")
            for problem in problems:
                print("    " + problem.replace("\n", "\n    "))
        sys.exit(1)
    print(f"all {total} passed")


if __name__ == "__main__":
    main()
