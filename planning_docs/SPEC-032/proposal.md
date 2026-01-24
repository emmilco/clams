# SPEC-032: Type-Safe Datetime and Numeric Handling - Technical Proposal

**Author**: Architect (W-1769118153-29572)
**Created**: 2025-01-22
**Spec**: SPEC-032

---

## 1. Problem Statement

The CLAMS codebase has experienced format mismatch bugs where datetime and numeric data written in one format is read expecting another format. These bugs are subtle and often pass tests but fail in production.

**BUG-027**: `created_at` stored as ISO string but read with `datetime.fromtimestamp()` expecting numeric timestamp, causing `TypeError`.

**BUG-034**: Float timeout truncated via `int()` cast, where `int(0.5)` returns `0`, changing behavior semantically.

The existing `src/clams/utils/datetime.py` module (created after BUG-027) provides `serialize_datetime()` and `deserialize_datetime()` but is not universally adopted. The codebase has 35+ datetime serialization locations using various patterns.

---

## 2. Proposed Solution

### 2.1 Overview

1. **Extend datetime utilities** with optional helpers and validation
2. **Create numeric utilities** for type-safe conversions
3. **Add validation decorators** for function parameter validation
4. **Provide clear migration path** for existing code

### 2.2 Architecture

```
src/clams/utils/
  __init__.py         # Re-export all utilities
  datetime.py         # Extended datetime utilities (existing + additions)
  numeric.py          # NEW: Numeric type preservation utilities
  validation.py       # NEW: Type validation decorators
  README.md           # NEW: Documentation
```

---

## 3. Technical Approach

### 3.1 Datetime Utilities Module

**File**: `src/clams/utils/datetime.py`

The existing module already implements the core functions correctly. We add:

#### New Functions

```python
def is_valid_datetime_format(value: str) -> bool:
    """Check if string is valid ISO 8601 format that can be parsed.

    Non-throwing validation - returns True if deserialize_datetime() would succeed.
    Useful for input validation before processing.

    Args:
        value: String to validate

    Returns:
        True if the string can be parsed as ISO 8601, False otherwise

    Examples:
        >>> is_valid_datetime_format("2024-12-15T10:30:00+00:00")
        True
        >>> is_valid_datetime_format("invalid")
        False
        >>> is_valid_datetime_format("2024-12-15")  # Date-only is valid
        True
    """
```

```python
def serialize_datetime_optional(dt: datetime | None) -> str | None:
    """Serialize optional datetime, returning None for None input.

    Convenience wrapper for nullable datetime fields.

    Args:
        dt: Datetime to serialize, or None

    Returns:
        ISO 8601 string if dt is not None, else None

    Examples:
        >>> serialize_datetime_optional(datetime(2024, 12, 15, tzinfo=UTC))
        '2024-12-15T00:00:00+00:00'
        >>> serialize_datetime_optional(None)
        None
    """
```

```python
def deserialize_datetime_optional(value: str | float | int | None) -> datetime | None:
    """Deserialize optional datetime, returning None for None input.

    Convenience wrapper for nullable datetime fields.

    Args:
        value: Value to deserialize, or None

    Returns:
        UTC datetime if value is not None, else None

    Raises:
        ValueError: If value is non-None and cannot be parsed
        TypeError: If value is non-None and wrong type
    """
```

#### Implementation Notes

- `is_valid_datetime_format()` uses try/except internally to avoid regex complexity
- Optional wrappers are thin - they just add None handling
- All functions remain stateless with no initialization requirements

### 3.2 Numeric Utilities Module

**File**: `src/clams/utils/numeric.py` (new)

```python
"""Numeric type preservation utilities.

This module provides utilities for safe numeric conversions that prevent
silent precision loss. It addresses BUG-034 where float-to-int truncation
caused semantic changes in behavior.

Design principles:
- Fail loudly on precision loss by default
- Opt-in to lossy conversions with explicit flags
- Preserve original type where possible
"""

from typing import TypeVar

T = TypeVar('T', int, float)

__all__ = ["safe_int", "clamp", "is_positive"]


def safe_int(value: int | float | str, *, round_floats: bool = False) -> int:
    """Convert to int, raising on precision loss unless round_floats=True.

    This function prevents the BUG-034 scenario where `int(0.5)` silently
    returns 0, changing a 500ms timeout to infinite wait.

    Args:
        value: Value to convert (int, float, or numeric string)
        round_floats: If True, round floats using standard rounding (round half to even).
                      If False (default), raise ValueError for floats with fractional parts.

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
        ValueError: Cannot convert 5.9 to int without precision loss. Use round_floats=True to round.
        >>> safe_int(5.9, round_floats=True)
        6
        >>> safe_int("42")
        42
        >>> safe_int(0.5)  # BUG-034 scenario - prevented
        ValueError: Cannot convert 0.5 to int without precision loss. Use round_floats=True to round.
    """


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
```

#### Implementation Notes

- `safe_int()` checks `value != int(value)` for precision loss detection
- `clamp()` uses `max(min_val, min(value, max_val))` pattern
- Type preservation in `clamp()` is natural since `min()`/`max()` preserve types

### 3.3 Validation Decorators Module

**File**: `src/clams/utils/validation.py` (new)

```python
"""Type validation decorators for function parameters.

These decorators enforce contracts at function boundaries, providing
clear error messages when inputs don't meet requirements. They are
designed to work with both sync and async functions.
"""

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from clams.utils.datetime import is_valid_datetime_format

P = ParamSpec('P')
R = TypeVar('R')

__all__ = ["validate_datetime_params", "validate_numeric_range"]


def validate_datetime_params(*param_names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate datetime string parameters are ISO 8601 format.

    Validates that specified parameters (when not None) are valid ISO 8601
    datetime strings that can be parsed by deserialize_datetime().

    Args:
        *param_names: Names of parameters to validate

    Returns:
        Decorator function

    Raises:
        ValueError: If a specified parameter is not valid ISO 8601 format

    Usage:
        @validate_datetime_params("since", "until")
        def query_events(since: str | None = None, until: str | None = None):
            ...

        @validate_datetime_params("timestamp")
        async def log_event(timestamp: str):
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        sig = inspect.signature(func)
        param_names_list = list(sig.parameters.keys())

        def validate_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            """Validate datetime parameters from args/kwargs."""
            # Build a mapping of param_name -> value
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            for param_name in param_names:
                if param_name not in bound.arguments:
                    continue
                value = bound.arguments[param_name]
                if value is None:
                    continue  # None is allowed for optional params
                if not isinstance(value, str):
                    raise ValueError(
                        f"Parameter '{param_name}' must be a string, got {type(value).__name__}"
                    )
                if not is_valid_datetime_format(value):
                    raise ValueError(
                        f"Parameter '{param_name}' must be ISO 8601 format "
                        f"(e.g., '2024-12-15T10:30:00+00:00'), got: '{value}'"
                    )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return await func(*args, **kwargs)
            return async_wrapper  # type: ignore[return-value]
        else:
            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return func(*args, **kwargs)
            return sync_wrapper  # type: ignore[return-value]

    return decorator


def validate_numeric_range(
    param_name: str,
    min_val: float,
    max_val: float
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate numeric parameter is in range.

    Validates that the specified parameter (when not None) is within
    the given range [min_val, max_val] inclusive.

    Args:
        param_name: Name of parameter to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        Decorator function

    Raises:
        ValueError: If parameter is outside the valid range

    Usage:
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0):
            ...

        @validate_numeric_range("limit", 1, 100)
        async def fetch_items(limit: int = 10):
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        sig = inspect.signature(func)

        def validate_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            """Validate numeric parameter from args/kwargs."""
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            if param_name not in bound.arguments:
                return
            value = bound.arguments[param_name]
            if value is None:
                return  # None is allowed for optional params
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Parameter '{param_name}' must be numeric, got {type(value).__name__}"
                )
            if not (min_val <= value <= max_val):
                raise ValueError(
                    f"Parameter '{param_name}' must be in range [{min_val}, {max_val}], got: {value}"
                )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return await func(*args, **kwargs)
            return async_wrapper  # type: ignore[return-value]
        else:
            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return func(*args, **kwargs)
            return sync_wrapper  # type: ignore[return-value]

    return decorator
```

#### Implementation Notes

- Uses `inspect.signature()` to introspect function parameters
- Uses `@wraps(func)` to preserve function metadata (name, docstring, annotations)
- Supports both sync and async functions via `asyncio.iscoroutinefunction()`
- `ParamSpec` preserves type signatures for IDE support
- Validates only when value is not None (optional params supported)

### 3.4 Exports and Integration

**File**: `src/clams/utils/__init__.py` (modified)

```python
"""CLAMS utility modules.

Provides centralized utilities for:
- datetime: Consistent datetime serialization/deserialization (R11-A)
- numeric: Type-safe numeric conversions (R11-B)
- validation: Function parameter validation decorators
"""

from clams.utils.datetime import (
    deserialize_datetime,
    deserialize_datetime_optional,
    is_valid_datetime_format,
    serialize_datetime,
    serialize_datetime_optional,
)
from clams.utils.numeric import (
    clamp,
    is_positive,
    safe_int,
)
from clams.utils.validation import (
    validate_datetime_params,
    validate_numeric_range,
)

__all__ = [
    # Datetime utilities
    "serialize_datetime",
    "deserialize_datetime",
    "serialize_datetime_optional",
    "deserialize_datetime_optional",
    "is_valid_datetime_format",
    # Numeric utilities
    "safe_int",
    "clamp",
    "is_positive",
    # Validation decorators
    "validate_datetime_params",
    "validate_numeric_range",
]
```

---

## 4. Alternative Approaches Considered

### 4.1 Runtime Type Checking Library (Pydantic)

**Considered**: Use Pydantic for automatic type coercion and validation.

**Rejected because**:
- Heavy dependency for simple use case
- Would require refactoring all data classes
- Current codebase uses dataclasses, not Pydantic models
- Overhead for simple function parameter validation

### 4.2 Custom Type System with NewType

**Considered**: Use `NewType` to create distinct types like `ISODatetimeStr`.

**Rejected because**:
- `NewType` is erased at runtime (no enforcement)
- Would only catch errors with type checkers, not at runtime
- Our bugs occurred at runtime with correct static types

### 4.3 Monkey-patching datetime Methods

**Considered**: Replace `datetime.isoformat()` and `datetime.fromisoformat()` globally.

**Rejected because**:
- Fragile and hard to debug
- Affects third-party libraries unexpectedly
- Not explicit about what's happening

### 4.4 Storing Both Formats

**Considered**: Store datetime as both ISO string and timestamp.

**Rejected because**:
- Doubles storage size
- Creates possibility of inconsistency between formats
- More complex code to maintain both

---

## 5. Migration Strategy

### Phase 1: Immediate (This Task)
- Implement new utilities
- All new code MUST use utilities
- No changes to existing code yet

### Phase 2: Future Task (SPEC-032-01)
- Audit all datetime serialization sites (35+ locations found)
- Replace direct `.isoformat()` with `serialize_datetime()`
- Replace direct `fromisoformat()`/`fromtimestamp()` with `deserialize_datetime()`
- Priority order:
  1. MCP tool handlers (user-facing)
  2. Observation models
  3. Storage layer
  4. Git analyzer

### Phase 3: Future Task (SPEC-032-02)
- Add round-trip tests for all datetime fields
- Add regression tests for BUG-027 and BUG-034 scenarios

---

## 6. File-by-File Implementation Plan

### 6.1 New Files

| File | Description | Lines (est.) |
|------|-------------|--------------|
| `src/clams/utils/numeric.py` | Numeric utilities | ~120 |
| `src/clams/utils/validation.py` | Validation decorators | ~150 |
| `src/clams/utils/README.md` | Module documentation | ~100 |
| `tests/utils/test_numeric.py` | Numeric utility tests | ~200 |
| `tests/utils/test_validation.py` | Validation decorator tests | ~250 |

### 6.2 Modified Files

| File | Changes |
|------|---------|
| `src/clams/utils/datetime.py` | Add 3 new functions (~50 lines) |
| `src/clams/utils/__init__.py` | Re-export new utilities |
| `tests/utils/test_datetime.py` | Add tests for new functions (~80 lines) |

### 6.3 Detailed Changes

#### `src/clams/utils/datetime.py`

Add after line 109 (end of current file):

```python
def is_valid_datetime_format(value: str) -> bool:
    """Check if string is valid ISO 8601 format that can be parsed.

    ... (full docstring)
    """
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def serialize_datetime_optional(dt: datetime | None) -> str | None:
    """Serialize optional datetime, returning None for None input.

    ... (full docstring)
    """
    if dt is None:
        return None
    return serialize_datetime(dt)


def deserialize_datetime_optional(value: str | float | int | None) -> datetime | None:
    """Deserialize optional datetime, returning None for None input.

    ... (full docstring)
    """
    if value is None:
        return None
    return deserialize_datetime(value)
```

Update `__all__`:
```python
__all__ = [
    "serialize_datetime",
    "deserialize_datetime",
    "serialize_datetime_optional",
    "deserialize_datetime_optional",
    "is_valid_datetime_format",
]
```

#### `src/clams/utils/numeric.py`

Complete implementation:

```python
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
        round_floats: If True, round floats using standard rounding (round half to even).
                      If False (default), raise ValueError for floats with fractional parts.

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
        raise ValueError(
            f"min_val ({min_val}) must be <= max_val ({max_val})"
        )
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
```

#### `src/clams/utils/validation.py`

Complete implementation as shown in section 3.3.

---

## 7. Testing Strategy

### 7.1 Unit Tests

#### `tests/utils/test_datetime.py` (additions)

```python
class TestIsValidDatetimeFormat:
    """Tests for is_valid_datetime_format function."""

    def test_valid_iso_with_timezone(self) -> None:
        """Valid ISO 8601 with timezone returns True."""
        assert is_valid_datetime_format("2024-12-15T10:30:00+00:00") is True

    def test_valid_iso_without_timezone(self) -> None:
        """Valid ISO 8601 without timezone returns True."""
        assert is_valid_datetime_format("2024-12-15T10:30:00") is True

    def test_valid_date_only(self) -> None:
        """Date-only format returns True."""
        assert is_valid_datetime_format("2024-12-15") is True

    def test_invalid_string(self) -> None:
        """Invalid string returns False."""
        assert is_valid_datetime_format("invalid") is False

    def test_empty_string(self) -> None:
        """Empty string returns False."""
        assert is_valid_datetime_format("") is False


class TestSerializeDatetimeOptional:
    """Tests for serialize_datetime_optional function."""

    def test_none_returns_none(self) -> None:
        """None input returns None output."""
        assert serialize_datetime_optional(None) is None

    def test_datetime_returns_string(self) -> None:
        """Datetime input returns ISO string."""
        dt = datetime(2024, 12, 15, 10, 30, 0, tzinfo=UTC)
        result = serialize_datetime_optional(dt)
        assert result == "2024-12-15T10:30:00+00:00"


class TestDeserializeDatetimeOptional:
    """Tests for deserialize_datetime_optional function."""

    def test_none_returns_none(self) -> None:
        """None input returns None output."""
        assert deserialize_datetime_optional(None) is None

    def test_string_returns_datetime(self) -> None:
        """ISO string returns datetime."""
        result = deserialize_datetime_optional("2024-12-15T10:30:00+00:00")
        assert result == datetime(2024, 12, 15, 10, 30, 0, tzinfo=UTC)

    def test_invalid_raises(self) -> None:
        """Invalid value raises ValueError."""
        with pytest.raises(ValueError):
            deserialize_datetime_optional("invalid")
```

#### `tests/utils/test_numeric.py` (new)

```python
"""Tests for numeric type preservation utilities.

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

    def test_float_no_decimal(self) -> None:
        """Float with no decimal part converts to int."""
        assert safe_int(5.0) == 5
        assert safe_int(-5.0) == -5

    def test_float_with_decimal_raises(self) -> None:
        """Float with decimal part raises ValueError by default."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(5.9)

    def test_float_with_decimal_rounds(self) -> None:
        """Float with decimal rounds when round_floats=True."""
        assert safe_int(5.9, round_floats=True) == 6
        assert safe_int(5.4, round_floats=True) == 5
        # Banker's rounding (round half to even)
        assert safe_int(5.5, round_floats=True) == 6
        assert safe_int(6.5, round_floats=True) == 6

    def test_bug_034_scenario_prevented(self) -> None:
        """BUG-034 scenario: 0.5 does not silently become 0."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(0.5)
        # With explicit rounding, it rounds to 0 (or 1, depending on rounding)
        assert safe_int(0.5, round_floats=True) == 0  # Banker's rounding

    def test_string_int(self) -> None:
        """Numeric string parses to int."""
        assert safe_int("42") == 42
        assert safe_int("-42") == -42

    def test_string_float_no_decimal(self) -> None:
        """Float string with no decimal converts."""
        assert safe_int("5.0") == 5

    def test_string_float_with_decimal_raises(self) -> None:
        """Float string with decimal raises ValueError."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int("5.9")

    def test_invalid_string_raises(self) -> None:
        """Non-numeric string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse"):
            safe_int("not a number")

    def test_invalid_type_raises(self) -> None:
        """Non-numeric type raises TypeError."""
        with pytest.raises(TypeError):
            safe_int([1, 2, 3])  # type: ignore[arg-type]


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

    def test_int_type_preserved(self) -> None:
        """Int type is preserved."""
        result = clamp(5, 0, 10)
        assert result == 5
        assert isinstance(result, int)

    def test_invalid_range_raises(self) -> None:
        """min_val > max_val raises ValueError."""
        with pytest.raises(ValueError, match="min_val.*must be <= max_val"):
            clamp(5, 10, 0)


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

    def test_zero(self) -> None:
        """Zero returns False."""
        assert is_positive(0) is False
        assert is_positive(0.0) is False

    def test_negative(self) -> None:
        """Negative values return False."""
        assert is_positive(-1) is False
        assert is_positive(-0.001) is False
```

#### `tests/utils/test_validation.py` (new)

```python
"""Tests for validation decorators.

Tests that decorators work with both sync and async functions,
preserve function signatures, and provide clear error messages.
"""

import pytest

from clams.utils.validation import validate_datetime_params, validate_numeric_range


class TestValidateDatetimeParams:
    """Tests for validate_datetime_params decorator."""

    def test_valid_datetime_passes(self) -> None:
        """Valid ISO 8601 datetime passes validation."""
        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query("2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    def test_invalid_datetime_raises(self) -> None:
        """Invalid datetime raises ValueError with clear message."""
        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        with pytest.raises(ValueError) as exc_info:
            query("invalid")
        assert "since" in str(exc_info.value)
        assert "ISO 8601" in str(exc_info.value)

    def test_none_allowed(self) -> None:
        """None value is allowed for optional params."""
        @validate_datetime_params("since")
        def query(since: str | None = None) -> str | None:
            return since

        assert query(None) is None
        assert query() is None

    def test_multiple_params(self) -> None:
        """Multiple params can be validated."""
        @validate_datetime_params("since", "until")
        def query(since: str | None = None, until: str | None = None) -> tuple[str | None, str | None]:
            return (since, until)

        result = query("2024-01-01", "2024-12-31")
        assert result == ("2024-01-01", "2024-12-31")

    def test_preserves_function_name(self) -> None:
        """Decorator preserves function name."""
        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        assert query.__name__ == "query"

    @pytest.mark.asyncio
    async def test_async_function(self) -> None:
        """Decorator works with async functions."""
        @validate_datetime_params("since")
        async def query(since: str) -> str:
            return since

        result = await query("2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    @pytest.mark.asyncio
    async def test_async_function_invalid(self) -> None:
        """Async function raises on invalid datetime."""
        @validate_datetime_params("since")
        async def query(since: str) -> str:
            return since

        with pytest.raises(ValueError, match="since"):
            await query("invalid")


class TestValidateNumericRange:
    """Tests for validate_numeric_range decorator."""

    def test_value_in_range_passes(self) -> None:
        """Value in range passes validation."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        assert connect(30.0) == 30.0
        assert connect(0.1) == 0.1
        assert connect(300.0) == 300.0

    def test_value_below_range_raises(self) -> None:
        """Value below range raises ValueError."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError) as exc_info:
            connect(0.0)
        assert "timeout" in str(exc_info.value)
        assert "[0.1, 300.0]" in str(exc_info.value)

    def test_value_above_range_raises(self) -> None:
        """Value above range raises ValueError."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError) as exc_info:
            connect(500.0)
        assert "timeout" in str(exc_info.value)
        assert "500.0" in str(exc_info.value)

    def test_none_allowed(self) -> None:
        """None value is allowed for optional params."""
        @validate_numeric_range("limit", 1, 100)
        def fetch(limit: int | None = None) -> int | None:
            return limit

        assert fetch(None) is None
        assert fetch() is None

    def test_preserves_function_name(self) -> None:
        """Decorator preserves function name."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        assert connect.__name__ == "connect"

    @pytest.mark.asyncio
    async def test_async_function(self) -> None:
        """Decorator works with async functions."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        async def connect(timeout: float = 30.0) -> float:
            return timeout

        result = await connect(30.0)
        assert result == 30.0

    @pytest.mark.asyncio
    async def test_async_function_invalid(self) -> None:
        """Async function raises on invalid value."""
        @validate_numeric_range("timeout", 0.1, 300.0)
        async def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError, match="timeout"):
            await connect(0.0)
```

### 7.2 Integration Tests

Integration tests verifying end-to-end behavior are deferred to SPEC-032-02 (migration task), as they require modifying existing code to use the utilities.

### 7.3 Coverage Target

- 100% branch coverage on all new utility functions
- 100% branch coverage on validation decorators
- Tests for both sync and async code paths

---

## 8. Documentation

### 8.1 Module README

**File**: `src/clams/utils/README.md`

```markdown
# CLAMS Utilities

Centralized utilities for type-safe data handling across the CLAMS codebase.

## Datetime Utilities

Prevent format mismatch bugs (like BUG-027) by using centralized serialization.

### Usage

```python
from clams.utils import serialize_datetime, deserialize_datetime

# Serialize datetime to ISO 8601 string
dt = datetime.now(UTC)
iso_string = serialize_datetime(dt)  # "2024-12-15T10:30:00+00:00"

# Deserialize from ISO string or Unix timestamp
dt = deserialize_datetime("2024-12-15T10:30:00+00:00")
dt = deserialize_datetime(1702638600)  # Unix timestamp also works

# Optional helpers for nullable fields
serialize_datetime_optional(None)  # Returns None
deserialize_datetime_optional(None)  # Returns None
```

### Design Decisions

- **Always UTC**: All serialization outputs UTC timezone
- **Naive = UTC**: Naive datetimes are assumed to be UTC
- **Backwards compatible**: `deserialize_datetime()` accepts both ISO strings and Unix timestamps

## Numeric Utilities

Prevent precision loss bugs (like BUG-034) by using safe conversions.

### Usage

```python
from clams.utils import safe_int, clamp, is_positive

# safe_int prevents silent truncation
safe_int(5.0)  # 5 (no precision loss)
safe_int(5.9)  # Raises ValueError
safe_int(5.9, round_floats=True)  # 6 (explicit rounding)

# clamp preserves type
clamp(15, 0, 10)  # 10 (int)
clamp(15.0, 0.0, 10.0)  # 10.0 (float)

# is_positive for validation
is_positive(1)  # True
is_positive(0)  # False
```

## Validation Decorators

Enforce parameter contracts at function boundaries.

### Usage

```python
from clams.utils import validate_datetime_params, validate_numeric_range

@validate_datetime_params("since", "until")
def query(since: str | None = None, until: str | None = None):
    ...

@validate_numeric_range("timeout", 0.1, 300.0)
async def connect(timeout: float = 30.0):
    ...
```

### Error Messages

Clear, actionable error messages:
- `"Parameter 'since' must be ISO 8601 format (e.g., '2024-12-15T10:30:00+00:00'), got: 'invalid'"`
- `"Parameter 'timeout' must be in range [0.1, 300.0], got: 500.0"`
```

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Decorator breaks IDE autocomplete | Low | Medium | Use `@wraps`, `ParamSpec` for signature preservation |
| Validation overhead in hot paths | Low | Low | Decorators are for boundary validation, not inner loops |
| Migration incomplete | Medium | Medium | Tracked as separate task (SPEC-032-01) with audit |
| Type errors in decorator implementation | Low | Medium | Comprehensive test coverage, mypy --strict |

---

## 10. Dependencies

No new external dependencies required. Uses only Python standard library:
- `datetime` (UTC, datetime, timezone, timedelta)
- `typing` (ParamSpec, TypeVar, Callable, Any)
- `functools` (wraps)
- `asyncio` (iscoroutinefunction)
- `inspect` (signature, bind_partial)

---

## 11. Open Questions (Resolved)

1. **Should we add a lint rule?** - Deferred to future task. Can add ruff custom rule to flag direct `isoformat()`/`fromtimestamp()`.

2. **Should Decimal support be included?** - Not included in this scope. Can add if monetary values are needed later.

3. **Should validation decorators be mandatory?** - Not mandatory, but recommended for MCP tool handlers. Can add to reviewer checklist.

---

## 12. Review Checklist

Before implementation:
- [x] Proposal addresses all spec acceptance criteria
- [x] No ambiguous decisions left
- [x] Implementation path is clear
- [x] Edge cases identified
- [x] Error handling approach defined
- [x] Testability considered

---

## Appendix A: Migration Sites

### Datetime Serialization Sites (to migrate in SPEC-032-01)

| File | Line | Pattern | Priority |
|------|------|---------|----------|
| `server/tools/ghap.py` | 451, 544, 549 | Mixed isoformat/fromisoformat/fromtimestamp | High |
| `server/tools/git.py` | 57, 135, 161, 226, 296, 344, 345 | fromisoformat for input validation | High |
| `server/tools/memory.py` | 122 | isoformat for output | High |
| `server/tools/learning.py` | 430 | fromtimestamp | High |
| `observation/persister.py` | 311, 312 | isoformat for storage | Medium |
| `observation/models.py` | 112, 145, 197 | isoformat with Z suffix | Medium |
| `storage/metadata.py` | 149, 150, 176, 177, etc. | isoformat/fromisoformat | Medium |
| `git/analyzer.py` | 301, 307, 390 | Mixed patterns | Medium |
| `indexers/indexer.py` | 150, 227 | fromtimestamp/isoformat | Low |
| `values/store.py` | 284 | isoformat | Low |

Total: 35+ locations across 12 files
