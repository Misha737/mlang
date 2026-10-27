import pytest

from programs import LLI, collect_programs, check_program


@pytest.mark.skipif(LLI is None, reason="lli is not installed")
@pytest.mark.parametrize("source", collect_programs(), ids=lambda p: p.stem)
def test_program_output(source):
    problems = check_program(source)
    assert not problems, "\n".join(problems)
