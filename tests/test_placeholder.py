"""Placeholder test to verify test infrastructure."""


def test_placeholder() -> None:
    """Verify that the test framework is working."""
    assert True


def test_fixture(sample_fixture: str) -> None:
    """Verify that fixtures are working."""
    assert sample_fixture == "test_value"
