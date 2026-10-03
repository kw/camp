from camp.engine.rules import decision


def assert_traceback(d: decision.Decision):
    """Assert that a traceback is present.

    We approximate this by checking that it's a string that contains the phrase "File".
    """
    assert isinstance(d.traceback, str)
    assert "File " in d.traceback


def test_failure_gets_traceback():
    """By default, a traceback is collected if success=False."""
    d = decision.Decision(success=False)
    assert_traceback(d)


def test_failure_tb_disabled():
    """Even on failure, traceback is not collected if False is passed in for it."""
    d = decision.Decision(success=False, traceback=False)
    assert d.traceback is None


def test_success_no_traceback():
    """On success, traceback is not normally collected."""
    d = decision.Decision(success=True)
    assert d.traceback is None


def test_success_tb_requested():
    """On success, traceback is collected if requested."""
    d = decision.Decision(success=True, traceback=True)
    assert_traceback(d)
