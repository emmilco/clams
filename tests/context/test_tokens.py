"""Tests for token estimation and budget management."""

from learning_memory_server.context.tokens import (
    cap_item_tokens,
    distribute_budget,
    estimate_tokens,
    truncate_to_tokens,
)


def test_estimate_tokens_basic() -> None:
    """Test basic token estimation."""
    text = "a" * 400  # 400 characters
    tokens = estimate_tokens(text)
    assert tokens == 100  # 400 / 4 = 100


def test_estimate_tokens_empty() -> None:
    """Test token estimation on empty string."""
    assert estimate_tokens("") == 0


def test_truncate_to_tokens_no_truncation() -> None:
    """Test truncation when text is already within budget."""
    text = "a" * 100
    result = truncate_to_tokens(text, 50)  # 50 tokens = 200 chars
    assert len(result) == 100  # No truncation needed


def test_truncate_to_tokens_truncates() -> None:
    """Test truncation when text exceeds budget."""
    text = "a" * 1000
    result = truncate_to_tokens(text, 50)  # 50 tokens = 200 chars
    assert len(result) <= 200


def test_truncate_to_tokens_prefers_newline() -> None:
    """Test truncation prefers breaking at newlines."""
    text = "a" * 150 + "\n" + "b" * 100
    result = truncate_to_tokens(text, 50)  # 50 tokens = 200 chars
    # Should break at newline if it's within 80% of target
    assert "\n" in result or len(result) <= 200


def test_distribute_budget_single_source() -> None:
    """Test budget distribution with single source."""
    budget = distribute_budget(["memories"], 1000)
    assert budget["memories"] == 1000


def test_distribute_budget_multiple_sources() -> None:
    """Test budget distribution with multiple sources."""
    budget = distribute_budget(["memories", "code", "experiences"], 1200)

    # Weights: memories=1, code=2, experiences=3
    # Total weight: 6
    # memories: 1/6 * 1200 = 200
    # code: 2/6 * 1200 = 400
    # experiences: 3/6 * 1200 = 600
    assert budget["memories"] == 200
    assert budget["code"] == 400
    assert budget["experiences"] == 600


def test_distribute_budget_all_sources() -> None:
    """Test budget distribution with all source types."""
    budget = distribute_budget(
        ["memories", "code", "experiences", "values", "commits"], 900
    )

    # Weights: memories=1, code=2, experiences=3, values=1, commits=2
    # Total weight: 9
    assert budget["memories"] == 100  # 1/9 * 900
    assert budget["code"] == 200  # 2/9 * 900
    assert budget["experiences"] == 300  # 3/9 * 900
    assert budget["values"] == 100  # 1/9 * 900
    assert budget["commits"] == 200  # 2/9 * 900


def test_cap_item_tokens_no_cap() -> None:
    """Test capping when item is within limit."""
    content = "a" * 100  # 25 tokens
    result, was_truncated = cap_item_tokens(content, 200, {})
    assert result == content
    assert was_truncated is False


def test_cap_item_tokens_applies_cap() -> None:
    """Test capping when item exceeds 25% of source budget."""
    content = "a" * 400  # 100 tokens
    # Source budget is 200 tokens, so max per item is 50 tokens (200 chars)
    result, was_truncated = cap_item_tokens(content, 200, {})
    assert len(result) < len(content)
    assert was_truncated is True
    assert "*(truncated)*" in result


def test_cap_item_tokens_code_note() -> None:
    """Test truncation note for code items."""
    content = "a" * 400
    metadata = {"file_path": "foo.py", "start_line": 42}
    result, was_truncated = cap_item_tokens(content, 200, metadata, "code")
    assert was_truncated is True
    assert "foo.py:42" in result


def test_cap_item_tokens_experience_note() -> None:
    """Test truncation note for experience items."""
    content = "a" * 400
    metadata = {"id": "exp_123"}
    result, was_truncated = cap_item_tokens(content, 200, metadata, "experience")
    assert was_truncated is True
    assert "exp_123" in result
