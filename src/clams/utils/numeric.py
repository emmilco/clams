"""Numeric type preservation utilities.

This module provides utilities for safe numeric conversions that prevent
silent precision loss. It addresses BUG-034 where float-to-int truncation
caused semantic changes in behavior.

Design principles:
- Fail loudly on precision loss by default
- Opt-in to lossy conversions with explicit flags
- Preserve original type where possible

Reference: BUG-034 - Float timeout truncation in QdrantVectorStore
"""

from typing import TypeVar

__all__ = ["safe_int", "clamp", "is_positive"]

T = TypeVar("T", int, float)


def safe_int(value: int | float | str, *, round_floats: bool = False) -> int:
    """Convert to int, raising on precision loss unless round_floats=True.

    This function prevents the BUG-034 scenario where `int(0.5)` silently
    returns 0, changing a 500ms timeout to infinite wait.

    Args:
        value: Value to convert (int, float, or numeric string)
        round_floats: If True, round floats using standard rounding
                      (round half to even). If False (default), raise
                      ValueError for floats with fractional parts.

    Returns:
        Integer value

    Raises:
        ValueError: If float has non-zero fractional part and round_floats=False
        ValueError: If string cannot be parsed as a number
        TypeError: If value is not int, float, or str

    Examples:
        >>> safe_int(5)
        5
        >>> safe_int(5.0)  # No precision loss
        5
        >>> safe_int(5.9)  # Raises ValueError
        Traceback (most recent call last):
            ...
        ValueError: Cannot convert 5.9 to int without precision loss...
        >>> safe_int(5.9, round_floats=True)
        6
        >>> safe_int("42")
        42
        >>> safe_int(0.5)  # BUG-034 scenario - prevented
        Traceback (most recent call last):
            ...
        ValueError: Cannot convert 0.5 to int without precision loss...
    """
    if isinstance(value, str):
        # Parse string to float first, then validate
        try:
            value = float(value)
        except ValueError as e:
            raise ValueError(f"Cannot parse '{value}' as a number") from e

    if not isinstance(value, (int, float)):
        raise TypeError(
            f"Expected int, float, or str, got {type(value).__name__}: {value!r}"
        )

    if isinstance(value, int):
        return value

    # value is float
    int_val = int(value)
    if value != int_val:
        if round_floats:
            return round(value)
        raise ValueError(
            f"Cannot convert {value} to int without precision loss. "
            f"Use round_floats=True to round."
        )
    return int_val


def clamp(value: T, min_val: T, max_val: T) -> T:
    """Clamp value to range [min_val, max_val], preserving type.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        Value clamped to range, preserving original type

    Raises:
        ValueError: If min_val > max_val

    Examples:
        >>> clamp(5, 0, 10)
        5
        >>> clamp(-5, 0, 10)
        0
        >>> clamp(15, 0, 10)
        10
        >>> clamp(5.5, 0.0, 10.0)  # Float stays float
        5.5
    """
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) must be <= max_val ({max_val})")
    return max(min_val, min(value, max_val))


def is_positive(value: int | float) -> bool:
    """Check if value is positive (> 0).

    Args:
        value: Numeric value to check

    Returns:
        True if value > 0, False otherwise

    Examples:
        >>> is_positive(1)
        True
        >>> is_positive(0)
        False
        >>> is_positive(-1)
        False
        >>> is_positive(0.001)
        True
    """
    return value > 0
