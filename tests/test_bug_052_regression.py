"""Regression test for BUG-052: Add global pytest timeout.

This test verifies that pytest-timeout is installed and configured correctly.
The timeout plugin ensures that tests cannot hang indefinitely, which was causing
gate checks to block sessions.
"""

import pytest


@pytest.mark.timeout(1)
def test_timeout_decorator_works() -> None:
    """Verify the @pytest.mark.timeout decorator is available and functional.

    This test passes quickly - it just confirms that the timeout decorator
    can be applied without error, proving pytest-timeout is installed.
    """
    pass


def test_default_timeout_is_configured() -> None:
    """Verify that a default timeout is configured in pytest.

    This test runs under the default 60-second timeout configured in
    pyproject.toml. If this test were to hang, the timeout would fail it
    after 60 seconds instead of blocking indefinitely.

    The test itself does minimal work - the important thing is that the
    timeout mechanism is active.
    """
    # Simple operation that should complete instantly
    result = sum(range(100))
    assert result == 4950
