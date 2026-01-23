"""Tests for numeric type preservation utilities.

Reference: R11-B - Type-Safe Numeric Handling
Reference: BUG-034 - Float timeout truncation
"""

import pytest

from clams.utils.numeric import clamp, is_positive, safe_int


class TestSafeInt:
    """Tests for safe_int function."""

    def test_int_passthrough(self) -> None:
        """Integer values pass through unchanged."""
        assert safe_int(5) == 5
        assert safe_int(0) == 0
        assert safe_int(-5) == -5

    def test_large_int(self) -> None:
        """Large integers pass through unchanged."""
        large = 10**18
        assert safe_int(large) == large

    def test_float_no_decimal(self) -> None:
        """Float with no decimal part converts to int."""
        assert safe_int(5.0) == 5
        assert safe_int(-5.0) == -5
        assert safe_int(0.0) == 0

    def test_float_with_decimal_raises(self) -> None:
        """Float with decimal part raises ValueError by default."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(5.9)

    def test_float_with_decimal_raises_small(self) -> None:
        """Small fractional part still raises ValueError."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(5.001)

    def test_float_with_decimal_rounds(self) -> None:
        """Float with decimal rounds when round_floats=True."""
        assert safe_int(5.9, round_floats=True) == 6
        assert safe_int(5.4, round_floats=True) == 5

    def test_bankers_rounding(self) -> None:
        """Uses banker's rounding (round half to even)."""
        # Round half to even (Python's default round behavior)
        assert safe_int(5.5, round_floats=True) == 6  # 5.5 -> 6 (nearest even)
        assert safe_int(6.5, round_floats=True) == 6  # 6.5 -> 6 (nearest even)
        assert safe_int(4.5, round_floats=True) == 4  # 4.5 -> 4 (nearest even)

    def test_bug_034_scenario_prevented(self) -> None:
        """BUG-034 scenario: 0.5 does not silently become 0."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(0.5)
        # With explicit rounding, banker's rounding gives 0
        assert safe_int(0.5, round_floats=True) == 0  # Banker's rounding

    def test_string_int(self) -> None:
        """Numeric string parses to int."""
        assert safe_int("42") == 42
        assert safe_int("-42") == -42
        assert safe_int("0") == 0

    def test_string_float_no_decimal(self) -> None:
        """Float string with no decimal converts."""
        assert safe_int("5.0") == 5
        assert safe_int("-5.0") == -5

    def test_string_float_with_decimal_raises(self) -> None:
        """Float string with decimal raises ValueError."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int("5.9")

    def test_string_float_with_decimal_rounds(self) -> None:
        """Float string with decimal rounds when requested."""
        assert safe_int("5.9", round_floats=True) == 6

    def test_invalid_string_raises(self) -> None:
        """Non-numeric string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse"):
            safe_int("not a number")

    def test_empty_string_raises(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse"):
            safe_int("")

    def test_whitespace_string_raises(self) -> None:
        """Whitespace string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse"):
            safe_int("   ")

    def test_invalid_type_raises(self) -> None:
        """Non-numeric type raises TypeError."""
        with pytest.raises(TypeError):
            safe_int([1, 2, 3])  # type: ignore[arg-type]

    def test_none_raises(self) -> None:
        """None raises TypeError."""
        with pytest.raises(TypeError):
            safe_int(None)  # type: ignore[arg-type]

    def test_dict_raises(self) -> None:
        """Dict raises TypeError."""
        with pytest.raises(TypeError):
            safe_int({"value": 5})  # type: ignore[arg-type]

    def test_negative_float_with_decimal(self) -> None:
        """Negative float with decimal raises."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(-5.9)

    def test_negative_float_rounds(self) -> None:
        """Negative float rounds correctly."""
        assert safe_int(-5.9, round_floats=True) == -6
        assert safe_int(-5.4, round_floats=True) == -5


class TestClamp:
    """Tests for clamp function."""

    def test_value_in_range(self) -> None:
        """Value in range returns unchanged."""
        assert clamp(5, 0, 10) == 5

    def test_value_below_min(self) -> None:
        """Value below min returns min."""
        assert clamp(-5, 0, 10) == 0

    def test_value_above_max(self) -> None:
        """Value above max returns max."""
        assert clamp(15, 0, 10) == 10

    def test_value_at_min(self) -> None:
        """Value at min boundary returns unchanged."""
        assert clamp(0, 0, 10) == 0

    def test_value_at_max(self) -> None:
        """Value at max boundary returns unchanged."""
        assert clamp(10, 0, 10) == 10

    def test_float_type_preserved(self) -> None:
        """Float type is preserved."""
        result = clamp(5.5, 0.0, 10.0)
        assert result == 5.5
        assert isinstance(result, float)

    def test_float_clamped_to_min(self) -> None:
        """Float clamped to min preserves type."""
        result = clamp(-5.5, 0.0, 10.0)
        assert result == 0.0
        assert isinstance(result, float)

    def test_float_clamped_to_max(self) -> None:
        """Float clamped to max preserves type."""
        result = clamp(15.5, 0.0, 10.0)
        assert result == 10.0
        assert isinstance(result, float)

    def test_int_type_preserved(self) -> None:
        """Int type is preserved."""
        result = clamp(5, 0, 10)
        assert result == 5
        assert isinstance(result, int)

    def test_int_clamped_to_min(self) -> None:
        """Int clamped to min preserves type."""
        result = clamp(-5, 0, 10)
        assert result == 0
        assert isinstance(result, int)

    def test_int_clamped_to_max(self) -> None:
        """Int clamped to max preserves type."""
        result = clamp(15, 0, 10)
        assert result == 10
        assert isinstance(result, int)

    def test_invalid_range_raises(self) -> None:
        """min_val > max_val raises ValueError."""
        with pytest.raises(ValueError, match="min_val.*must be <= max_val"):
            clamp(5, 10, 0)

    def test_equal_min_max(self) -> None:
        """Equal min and max is valid."""
        assert clamp(5, 5, 5) == 5
        assert clamp(3, 5, 5) == 5
        assert clamp(7, 5, 5) == 5

    def test_negative_range(self) -> None:
        """Negative range works correctly."""
        assert clamp(-5, -10, -1) == -5
        assert clamp(-15, -10, -1) == -10
        assert clamp(0, -10, -1) == -1

    def test_large_values(self) -> None:
        """Large values work correctly."""
        large = 10**18
        assert clamp(large, 0, large + 1) == large
        assert clamp(large + 5, 0, large) == large


class TestIsPositive:
    """Tests for is_positive function."""

    def test_positive_int(self) -> None:
        """Positive integer returns True."""
        assert is_positive(1) is True
        assert is_positive(100) is True

    def test_positive_float(self) -> None:
        """Positive float returns True."""
        assert is_positive(0.001) is True
        assert is_positive(1.5) is True
        assert is_positive(100.0) is True

    def test_zero_int(self) -> None:
        """Zero integer returns False."""
        assert is_positive(0) is False

    def test_zero_float(self) -> None:
        """Zero float returns False."""
        assert is_positive(0.0) is False

    def test_negative_int(self) -> None:
        """Negative integer returns False."""
        assert is_positive(-1) is False
        assert is_positive(-100) is False

    def test_negative_float(self) -> None:
        """Negative float returns False."""
        assert is_positive(-0.001) is False
        assert is_positive(-1.5) is False

    def test_very_small_positive(self) -> None:
        """Very small positive value returns True."""
        assert is_positive(1e-10) is True

    def test_very_small_negative(self) -> None:
        """Very small negative value returns False."""
        assert is_positive(-1e-10) is False
