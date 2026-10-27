import pytest

from cases import collect, check_ok, check_err


@pytest.mark.parametrize("source", collect("ok"), ids=lambda p: p.stem)
def test_valid_program(source):
    problems = check_ok(source)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("source", collect("err"), ids=lambda p: p.stem)
def test_invalid_program(source):
    problems = check_err(source)
    assert not problems, "\n".join(problems)
