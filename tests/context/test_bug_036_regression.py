"""Regression test for BUG-036: KeyError in distribute_budget on invalid source type.

This test ensures that distribute_budget raises a clear ValueError with helpful
information when called with invalid context types, rather than an unhelpful KeyError.
"""

import pytest

from clams.context.tokens import distribute_budget


def test_bug_036_invalid_context_type() -> None:
    """Test that invalid context type raises ValueError with helpful message.

    Before the fix, this would raise:
        KeyError: 'invalid_type'

    After the fix, this raises:
        ValueError: Invalid context types: ['invalid_type']. Valid: [...]
    """
    with pytest.raises(ValueError, match="Invalid context types"):
        distribute_budget(context_types=["invalid_type"], max_tokens=1000)


def test_bug_036_multiple_invalid_types() -> None:
    """Test error message lists all invalid types."""
    with pytest.raises(ValueError, match=r"Invalid context types: \['bad1', 'bad2'\]"):
        distribute_budget(context_types=["bad1", "bad2"], max_tokens=1000)


def test_bug_036_mixed_valid_and_invalid() -> None:
    """Test error raised when mix of valid and invalid types."""
    with pytest.raises(ValueError, match="Invalid context types"):
        distribute_budget(context_types=["memories", "invalid_type"], max_tokens=1000)


def test_bug_036_error_shows_valid_types() -> None:
    """Test error message includes list of valid types."""
    with pytest.raises(ValueError, match="Valid:"):
        distribute_budget(context_types=["invalid_type"], max_tokens=1000)
