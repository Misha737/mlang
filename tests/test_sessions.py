import pytest

from programs import CAN_RUN_SESSIONS, check_session, collect_sessions


@pytest.mark.skipif(not CAN_RUN_SESSIONS, reason="neither llc with clang nor lli is installed")
@pytest.mark.parametrize("optimize", [False, True], ids=["plain", "optimized"])
@pytest.mark.parametrize("session", collect_sessions(), ids=lambda p: p.stem)
def test_session(session, optimize):
    problems = check_session(session, optimize=optimize)
    assert not problems, "\n".join(problems)
