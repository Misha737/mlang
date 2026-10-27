import sys

from cases import collect, check_ok, check_err


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
