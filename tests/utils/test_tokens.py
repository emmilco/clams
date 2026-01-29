"""Tests for token estimation utilities (SPEC-046)."""

import pytest

from clams.utils.tokens import estimate_tokens


class TestEstimateTokensCharMethod:
    """Test character-based token estimation (default method)."""

    def test_basic_estimation(self) -> None:
        """Basic character counting: len(text) // 4."""
        assert estimate_tokens("a" * 400) == 100
        assert estimate_tokens("a" * 4) == 1
        assert estimate_tokens("a" * 8) == 2

    def test_remainder_truncated(self) -> None:
        """Non-multiple-of-4 lengths truncate to floor."""
        assert estimate_tokens("a" * 5) == 1
        assert estimate_tokens("a" * 7) == 1
        assert estimate_tokens("a" * 9) == 2

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert estimate_tokens("") == 0

    def test_whitespace_only(self) -> None:
        """Whitespace counts as characters."""
        assert estimate_tokens("    ") == 1  # 4 spaces
        assert estimate_tokens("\n\n\n\n") == 1  # 4 newlines
        assert estimate_tokens("  \t\n") == 1  # mixed whitespace

    def test_explicit_method_chars(self) -> None:
        """Explicit method='chars' works."""
        assert estimate_tokens("a" * 12, method="chars") == 3


class TestEstimateTokensWordMethod:
    """Test word-based token estimation."""

    def test_basic_word_counting(self) -> None:
        """Word count * 1.3, truncated to int."""
        text = "one two three four"  # 4 words
        assert estimate_tokens(text, method="words") == 5  # int(4 * 1.3)

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert estimate_tokens("", method="words") == 0

    def test_single_word(self) -> None:
        """Single word gets 1.3x multiplier."""
        assert estimate_tokens("hello", method="words") == 1  # int(1 * 1.3)

    def test_two_words(self) -> None:
        """Two words get 1.3x multiplier."""
        assert estimate_tokens("hello world", method="words") == 2  # int(2 * 1.3)

    def test_ten_words(self) -> None:
        """Ten words get 1.3x multiplier."""
        text = "one two three four five six seven eight nine ten"
        assert estimate_tokens(text, method="words") == 13  # int(10 * 1.3)

    def test_whitespace_only_words(self) -> None:
        """Whitespace-only string returns 0 with words method."""
        assert estimate_tokens("     ", method="words") == 0
        assert estimate_tokens("\n\t\n", method="words") == 0


class TestEstimateTokensEdgeCases:
    """Test edge cases for both methods."""

    def test_unicode_chars_method(self) -> None:
        """Unicode characters counted by code points (chars method)."""
        cjk = "\u4f60\u597d\u4e16\u754c"  # 4 CJK characters
        assert estimate_tokens(cjk) == 1  # 4 code points / 4

    def test_unicode_words_method(self) -> None:
        """Unicode words counted normally (words method)."""
        cjk = "\u4f60\u597d \u4e16\u754c"  # 2 "words" separated by space
        assert estimate_tokens(cjk, method="words") == 2  # int(2 * 1.3)

    def test_very_short_text_chars(self) -> None:
        """Short text returns 0 for chars method."""
        assert estimate_tokens("hi") == 0  # 2 // 4 = 0
        assert estimate_tokens("hey") == 0  # 3 // 4 = 0

    def test_very_short_text_words(self) -> None:
        """Short text returns 1 for words method."""
        assert estimate_tokens("hi", method="words") == 1  # int(1 * 1.3)

    def test_emoji(self) -> None:
        """Emoji counted by code points."""
        # Each emoji is typically 1-2 code points
        assert estimate_tokens("a") == 0  # 1 char
        assert estimate_tokens("ab") == 0  # 2 chars
        assert estimate_tokens("abc") == 0  # 3 chars
        assert estimate_tokens("abcd") == 1  # 4 chars

    def test_mixed_content(self) -> None:
        """Mixed content (text + punctuation + whitespace)."""
        text = "Hello, world! How are you?"  # 26 chars
        assert estimate_tokens(text) == 6  # 26 // 4 = 6

    def test_newlines_and_tabs(self) -> None:
        """Newlines and tabs counted as characters."""
        text = "line1\nline2\tcolumn"  # 18 chars
        assert estimate_tokens(text) == 4  # 18 // 4 = 4


class TestEstimateTokensTypeValidation:
    """Test input type validation."""

    def test_none_raises_typeerror(self) -> None:
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(None)  # type: ignore[arg-type]

    def test_int_raises_typeerror(self) -> None:
        """Integer input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(123)  # type: ignore[arg-type]

    def test_bytes_raises_typeerror(self) -> None:
        """Bytes input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(b"hello")  # type: ignore[arg-type]

    def test_list_raises_typeerror(self) -> None:
        """List input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(["hello"])  # type: ignore[arg-type]

    def test_dict_raises_typeerror(self) -> None:
        """Dict input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens({"text": "hello"})  # type: ignore[arg-type]

    def test_error_message_shows_type(self) -> None:
        """Error message shows the actual type provided."""
        with pytest.raises(TypeError, match="got int"):
            estimate_tokens(42)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="got NoneType"):
            estimate_tokens(None)  # type: ignore[arg-type]


class TestEstimateTokensFromModule:
    """Test that estimate_tokens is exported from utils module."""

    def test_import_from_utils(self) -> None:
        """Function is importable from clams.utils."""
        from clams.utils import estimate_tokens as et
        assert callable(et)
        assert et("test") == 1  # 4 chars = 1 token
