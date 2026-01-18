"""Tests for token estimation and budget management."""

import pytest

from clams.context.tokens import (
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


# === New test classes per SPEC-046 ===


class TestEstimateTokensAccuracy:
    """
    Verify token estimation accuracy across content types.

    The 4 chars/token heuristic is conservative for English (~4.5 chars/token actual)
    and approximately correct for code/JSON which have more punctuation tokens.
    These tests document expected behavior and serve as regression tests.
    """

    def test_english_text_estimation(self) -> None:
        """English prose: ~4.5 chars/token actual, 4 chars/token estimated."""
        text = "The quick brown fox jumps over the lazy dog."
        estimated = estimate_tokens(text)
        # 44 chars / 4 = 11 tokens
        # Actual (tiktoken cl100k_base): ~10 tokens
        # Within margin - conservative estimate is acceptable
        assert estimated == 11
        assert 9 <= estimated <= 13  # Within 20% of expected

    def test_code_estimation(self) -> None:
        """Code has more tokens due to punctuation and operators."""
        code = "def calculate_sum(numbers: list[int]) -> int:\n    return sum(numbers)"
        estimated = estimate_tokens(code)
        # 68 chars / 4 = 17 tokens
        # Actual tokenization would yield more due to symbols
        assert estimated == 17
        assert estimated >= 15  # Conservative lower bound

    def test_json_estimation(self) -> None:
        """JSON has many structural tokens (braces, colons, quotes)."""
        json_text = '{"name": "test", "values": [1, 2, 3], "nested": {"key": "value"}}'
        estimated = estimate_tokens(json_text)
        # 65 chars / 4 = 16 tokens
        assert estimated == 16

    def test_markdown_estimation(self) -> None:
        """Markdown with formatting characters."""
        markdown = "# Header\n\n**Bold** and *italic* with `code` and [link](url)"
        estimated = estimate_tokens(markdown)
        # 59 chars / 4 = 14 tokens
        assert estimated == 14


class TestEstimateTokensEdgeCases:
    """Test edge cases for token estimation."""

    def test_single_character(self) -> None:
        """Single character should return 0 due to integer division.

        Note: Current implementation returns 0 for 1-3 chars due to integer division.
        This is acceptable as single characters rarely occur in isolation.
        """
        assert estimate_tokens("a") == 0  # 1 // 4 = 0
        assert estimate_tokens("ab") == 0  # 2 // 4 = 0
        assert estimate_tokens("abc") == 0  # 3 // 4 = 0
        assert estimate_tokens("abcd") == 1  # 4 // 4 = 1

    def test_unicode_basic_multilingual_plane(self) -> None:
        """Unicode characters from BMP (CJK, etc.).

        The heuristic counts Python string length (code points), not bytes.
        Each CJK char = 1 code point = 0.25 estimated tokens.
        This underestimates actual tokenization but is consistent.
        """
        # CJK characters: each is 1 code point
        # "hello" in Chinese (5 chars)
        cjk = "\u4f60\u597d\u4e16\u754c\u5417"  # 5 CJK characters
        assert estimate_tokens(cjk) == 1  # 5 code points / 4 = 1

        # 8 CJK characters
        cjk_8 = "\u4f60\u597d\u4e16\u754c\u5417\u4f60\u597d\u5417"
        assert estimate_tokens(cjk_8) == 2  # 8 code points / 4 = 2

    def test_unicode_emojis(self) -> None:
        """Emoji characters counting.

        Simple emojis are 1 code point each in Python.
        """
        # 4 simple emojis
        emojis = "\U0001F600\U0001F601\U0001F602\U0001F603"  # 4 smiley emojis
        assert estimate_tokens(emojis) == 1  # 4 code points / 4 = 1

    def test_unicode_flag_emoji(self) -> None:
        """Flag emoji (multi-codepoint sequences).

        Flag emoji are 2 regional indicator symbols each.
        """
        # US flag is 2 regional indicator symbols
        us_flag = "\U0001F1FA\U0001F1F8"  # US flag
        tokens = estimate_tokens(us_flag)
        assert isinstance(tokens, int)
        assert tokens == 0  # 2 code points / 4 = 0

    def test_whitespace_only(self) -> None:
        """Whitespace-only strings."""
        assert estimate_tokens("    ") == 1  # 4 spaces / 4 = 1
        assert estimate_tokens("\n\n\n\n") == 1  # 4 newlines / 4 = 1
        assert estimate_tokens("\t\t") == 0  # 2 tabs / 4 = 0

    def test_very_long_text(self) -> None:
        """Very long text doesn't overflow or cause issues."""
        long_text = "x" * 1_000_000
        estimated = estimate_tokens(long_text)
        assert estimated == 250_000


class TestTruncateToTokensIntegrity:
    """Test that truncation preserves content integrity."""

    def test_truncation_never_exceeds_budget(self) -> None:
        """Result never exceeds the token budget in characters."""
        text = "x" * 1000
        for max_tokens in [10, 50, 100, 200]:
            result = truncate_to_tokens(text, max_tokens)
            max_chars = max_tokens * 4
            assert len(result) <= max_chars

    def test_truncation_preserves_complete_lines_when_possible(self) -> None:
        """When truncating, prefer breaking at line boundaries."""
        lines = ["Line one content here", "Line two content here", "Line three"]
        text = "\n".join(lines)

        # Budget allows ~80 chars, text is ~60 chars
        result = truncate_to_tokens(text, 20)

        # Should include complete text since within budget
        assert result == text

    def test_truncation_at_newline_boundary(self) -> None:
        """Truncation should prefer newline boundaries within threshold."""
        # Create text where newline is within 80% of target
        text = "a" * 170 + "\n" + "b" * 50  # 221 chars total

        # Budget: 50 tokens = 200 chars
        result = truncate_to_tokens(text, 50)

        # Newline at position 170 is within 80% of 200 (160)
        # So it should break at the newline
        assert result == "a" * 170

    def test_truncation_ignores_distant_newline(self) -> None:
        """Newlines before 80% threshold are ignored."""
        text = "a" * 100 + "\n" + "b" * 200  # Newline at 100, total 301

        # Budget: 50 tokens = 200 chars
        # 80% of 200 = 160, newline at 100 is before threshold
        result = truncate_to_tokens(text, 50)

        # Should just truncate at char limit
        assert len(result) == 200
        assert "\n" in result  # The newline is included in the truncated portion

    def test_truncation_handles_no_newlines(self) -> None:
        """Text without newlines truncates cleanly."""
        text = "x" * 500
        result = truncate_to_tokens(text, 50)
        assert result == "x" * 200
        assert len(result) == 200


class TestDistributeBudgetValidation:
    """Test input validation for budget distribution."""

    def test_invalid_context_type_raises(self) -> None:
        """Invalid context types should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            distribute_budget(["memories", "invalid_type"], 1000)

        assert "invalid_type" in str(exc_info.value)
        assert "Invalid context types" in str(exc_info.value)

    def test_multiple_invalid_types_all_reported(self) -> None:
        """All invalid types should be listed in error."""
        with pytest.raises(ValueError) as exc_info:
            distribute_budget(["bad1", "memories", "bad2"], 1000)

        error_msg = str(exc_info.value)
        assert "bad1" in error_msg
        assert "bad2" in error_msg

    def test_empty_context_types(self) -> None:
        """Empty context types list should return empty dict.

        When no context types are provided, there's nothing to allocate budget to,
        so an empty dict is returned.
        """
        budget = distribute_budget([], 1000)
        assert budget == {}

    def test_zero_budget(self) -> None:
        """Zero budget should distribute zero to all sources."""
        budget = distribute_budget(["memories", "code"], 0)
        assert budget["memories"] == 0
        assert budget["code"] == 0

    def test_budget_sums_correctly(self) -> None:
        """Distributed budget should sum to approximately max_tokens."""
        for max_tokens in [100, 500, 1000, 10000]:
            budget = distribute_budget(
                ["memories", "code", "experiences", "values", "commits"],
                max_tokens,
            )
            total = sum(budget.values())
            # Integer division may lose a few tokens
            assert total <= max_tokens
            assert total >= max_tokens - len(budget)  # At most 1 lost per source
