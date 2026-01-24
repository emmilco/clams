# SPEC-032: Type-Safe Datetime and Numeric Handling

**Status**: DRAFT
**Created**: 2024-12-15
**Author**: Spec Writer (W-1765802588-65736)

## Problem Statement

The CLAMS codebase has suffered from type coercion bugs where data written in one format is read expecting another format. These bugs are subtle, often passing tests but failing in production with cryptic TypeErrors deep in the call stack.

### Root Cause Analysis

**BUG-027 (Datetime Format Mismatch)**:
- Storage: `"created_at": entry.created_at.isoformat()` writes ISO string
- Reading: `datetime.fromtimestamp(r.payload["created_at"])` expects numeric timestamp
- Result: `TypeError: an integer is required (got type str)`
- Impact: `list_ghap_entries` tool completely broken for production use

**BUG-034 (Float Truncation)**:
- Storage: `timeout=int(self._timeout)` truncates float to integer
- Problem: `int(0.5)` returns `0`, changing a 500ms timeout to infinite wait
- Impact: Semantic change in behavior, potential hangs or resource exhaustion

### Pattern Analysis

From the bug pattern analysis (RESEARCH-bug-pattern-analysis.md), Theme T4 "Data Format/Parsing Mismatches" accounts for 8% of analyzed bugs, with the following characteristics:
- No enforced contract between writer and reader
- No round-trip tests to verify serialization/deserialization
- Inconsistent format choices across the codebase

Current codebase analysis reveals:
- 35+ locations using datetime serialization/deserialization
- Mixed use of `.isoformat()`, `.timestamp()`, `datetime.fromisoformat()`, and `datetime.fromtimestamp()`
- Existing utility module `src/clams/utils/datetime.py` created after BUG-027 but not universally adopted

---

## Goals

1. **Eliminate datetime format mismatches** by standardizing on a single serialization format
2. **Prevent numeric precision loss** by establishing clear rules for type preservation
3. **Provide type-safe utilities** that make the right thing easy and the wrong thing hard
4. **Enable static analysis** through proper type annotations
5. **Ensure backwards compatibility** with existing persisted data

---

## Non-Goals

- Changing the internal representation of datetime objects
- Supporting arbitrary datetime formats (e.g., human-readable strings like "yesterday")
- Timezone conversion for display purposes (out of scope for storage layer)
- Performance optimization of datetime operations

---

## Technical Design

### 0. Initialization Requirements

**All utility functions are stateless and require no initialization.** They can be imported and used immediately without any setup, configuration, or resource allocation. This ensures they are safe to use in any context, including during module initialization.

### 1. Standard Datetime Format

**Canonical Format**: ISO 8601 with explicit UTC timezone

```
2024-12-15T10:30:45+00:00
```

**Design Decisions**:

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Format | ISO 8601 | Human-readable, standard, sortable, parseable |
| Timezone | Preserved in output | Allows round-trip without data loss |
| Precision | Microseconds when available | Preserves full precision |
| Naive datetimes | Treat as UTC | Prevents implicit local time assumptions |
| Non-UTC timezone-aware | Preserved as-is | Timezone information is valuable; conversion can be done at display time |

**Timezone Handling**:
- **Naive datetimes**: Assumed to be UTC, serialized with `+00:00`
- **UTC timezone-aware**: Serialized as-is with `+00:00`
- **Non-UTC timezone-aware**: Preserved as-is (e.g., `datetime(2024, 12, 15, 16, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))` becomes `2024-12-15T16:00:00+05:30`)

**Why not Unix timestamps?**
- Less readable in logs and database inspection
- Timezone information lost (always UTC)
- Already have mixed usage causing BUG-027

**Why not store both formats?**
- Increases storage size
- Creates possibility of inconsistency
- More complex code paths

### 2. Serialization/Deserialization API

Extend the existing `src/clams/utils/datetime.py` module:

```python
from datetime import datetime

# Existing (keep as-is)
def serialize_datetime(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string. Naive datetimes assumed UTC."""
    ...

def deserialize_datetime(value: str | float | int) -> datetime:
    """Parse datetime from ISO string or Unix timestamp (backwards compatible)."""
    ...

# New additions
def is_valid_datetime_format(value: str) -> bool:
    """Check if string is valid ISO 8601 format that can be parsed.

    Returns True if the string can be successfully parsed by deserialize_datetime().
    Accepts any ISO 8601 variant including:
    - Full format: "2024-12-15T10:30:45+00:00"
    - With microseconds: "2024-12-15T10:30:45.123456+00:00"
    - Z suffix: "2024-12-15T10:30:45Z"
    - Date only: "2024-12-15" (assumes midnight UTC)

    Does NOT require the canonical format with explicit timezone.
    """
    ...

def serialize_datetime_optional(dt: datetime | None) -> str | None:
    """Serialize optional datetime, returning None for None input."""
    ...

def deserialize_datetime_optional(value: str | float | int | None) -> datetime | None:
    """Deserialize optional datetime, returning None for None input."""
    ...
```

### 3. Numeric Type Preservation

**Principle**: Preserve the original numeric type unless explicit conversion is required.

| Source Type | Storage Type | Rationale |
|-------------|--------------|-----------|
| `float` (timeout) | `float` | Preserve precision (BUG-034 fix) |
| `int` (count) | `int` | No precision to lose |
| `float` (score) | `float` | Preserve decimal precision |
| `Decimal` (money) | `str` | Exact decimal representation |

**Numeric Utilities**:

```python
# src/clams/utils/numeric.py (new file)

from decimal import Decimal
from typing import TypeVar

T = TypeVar('T', int, float)

def safe_int(value: int | float | str, *, round_floats: bool = False) -> int:
    """Convert to int, raising on precision loss unless round_floats=True.

    Args:
        value: Value to convert
        round_floats: If True, round floats instead of raising

    Raises:
        ValueError: If float has non-zero decimal and round_floats=False

    Examples:
        >>> safe_int(5.0)  # No precision loss
        5
        >>> safe_int(5.9)  # Raises ValueError
        ValueError: Cannot convert 5.9 to int without precision loss
        >>> safe_int(5.9, round_floats=True)
        6
    """
    ...

def clamp(value: T, min_val: T, max_val: T) -> T:
    """Clamp value to range [min_val, max_val], preserving type."""
    ...

def is_positive(value: int | float) -> bool:
    """Check if value is positive (> 0)."""
    ...
```

### 4. Type Validation Decorators

For enforcing contracts at function boundaries:

```python
# src/clams/utils/validation.py (additions)

from functools import wraps
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec('P')
R = TypeVar('R')

def validate_datetime_params(*param_names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate datetime string parameters are ISO 8601 format.

    Usage:
        @validate_datetime_params("since", "until")
        def query_events(since: str | None = None, until: str | None = None):
            ...
    """
    ...

def validate_numeric_range(param_name: str, min_val: float, max_val: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate numeric parameter is in range.

    Usage:
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0):
            ...
    """
    ...
```

### 5. Migration Strategy

**Phase 1: Adopt utilities in new code** (immediate)
- All new datetime serialization uses `serialize_datetime()`
- All new datetime deserialization uses `deserialize_datetime()`
- All new numeric handling follows type preservation rules

**Phase 2: Audit and migrate existing code** (SPEC-032-01)
- Identify all datetime serialization/deserialization sites
- Replace direct `.isoformat()` with `serialize_datetime()`
- Replace direct `fromisoformat()`/`fromtimestamp()` with `deserialize_datetime()`
- Add `# type: ignore` comments only where absolutely necessary

**Phase 3: Add round-trip tests** (SPEC-032-02)
- For each data model with datetime fields, add test verifying serialize/deserialize round-trip
- For each numeric parameter, add test verifying no precision loss

### 6. Backwards Compatibility

The `deserialize_datetime()` function already accepts both ISO strings and Unix timestamps, ensuring backwards compatibility with data stored before standardization.

For existing persisted data:
- ISO strings: Parsed correctly (new standard)
- Unix timestamps: Parsed correctly (legacy support)
- No data migration required

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/clams/utils/numeric.py` | Numeric type preservation utilities |

### Modified Files

| File | Changes |
|------|---------|
| `src/clams/utils/datetime.py` | Add optional helpers, validation function |
| `src/clams/utils/validation.py` | Add type validation decorators |
| `src/clams/utils/__init__.py` | Export new utilities |

### Future Tasks (Migration)

| Task ID | Description |
|---------|-------------|
| SPEC-032-01 | Migrate all datetime serialization to use utilities |
| SPEC-032-02 | Add round-trip tests for all datetime fields |
| SPEC-032-03 | Remove `int()` casts on numeric parameters across codebase |

---

## Acceptance Criteria

### AC1: Datetime Utilities Complete
- [ ] `serialize_datetime()` converts datetime to ISO 8601 with UTC
- [ ] `deserialize_datetime()` handles ISO strings and Unix timestamps
- [ ] `serialize_datetime_optional()` and `deserialize_datetime_optional()` handle None
- [ ] `is_valid_datetime_format()` validates ISO 8601 without parsing
- [ ] All functions have comprehensive docstrings with examples
- [ ] Unit tests achieve 100% branch coverage

### AC2: Numeric Utilities Complete
- [ ] `safe_int()` raises on precision loss by default
- [ ] `safe_int(round_floats=True)` rounds instead of raising
- [ ] `clamp()` preserves input type (int stays int, float stays float)
- [ ] `is_positive()` works for int and float
- [ ] Unit tests cover edge cases (0, negative, float with no decimal, etc.)

### AC3: Validation Decorators Complete
- [ ] `@validate_datetime_params()` validates specified string params are ISO 8601
- [ ] `@validate_numeric_range()` validates numeric param is in specified range
- [ ] Decorators preserve function signatures for IDE support
- [ ] Decorators work with async functions
- [ ] Clear error messages follow this format:
  - Datetime: `"Parameter 'since' must be ISO 8601 format (e.g., '2024-12-15T10:30:00+00:00'), got: 'invalid'"`
  - Numeric range: `"Parameter 'timeout' must be in range [0.1, 300.0], got: 500.0"`

### AC4: Documentation
- [ ] Module docstrings explain the design decisions
- [ ] Functions have docstrings with Args, Returns, Raises, Examples
- [ ] `src/clams/utils/README.md` added documenting the utilities

### AC5: Type Safety
- [ ] All functions have complete type annotations
- [ ] `mypy --strict` passes on new/modified files
- [ ] No `# type: ignore` comments without explanation

### AC6: Integration
- [ ] New utilities exported from `src/clams/utils/__init__.py`
- [ ] Existing `deserialize_datetime()` behavior unchanged (backwards compatible)
- [ ] Can import utilities without heavy dependencies (no torch, numpy imports)

---

## Testing Strategy

### Unit Tests

```python
# tests/utils/test_datetime.py

class TestSerializeDatetime:
    def test_utc_datetime(self):
        """UTC datetime serializes with +00:00 suffix."""
        dt = datetime(2024, 12, 15, 10, 30, 0, tzinfo=UTC)
        assert serialize_datetime(dt) == "2024-12-15T10:30:00+00:00"

    def test_naive_datetime_assumes_utc(self):
        """Naive datetime is treated as UTC."""
        dt = datetime(2024, 12, 15, 10, 30, 0)
        assert "+00:00" in serialize_datetime(dt)

    def test_microseconds_preserved(self):
        """Microsecond precision is preserved."""
        dt = datetime(2024, 12, 15, 10, 30, 0, 123456, tzinfo=UTC)
        result = serialize_datetime(dt)
        assert "123456" in result

class TestDeserializeDatetime:
    def test_iso_string(self):
        """ISO string deserializes correctly."""
        result = deserialize_datetime("2024-12-15T10:30:00+00:00")
        assert result.year == 2024
        assert result.tzinfo == UTC

    def test_unix_timestamp_int(self):
        """Unix timestamp (int) deserializes correctly."""
        result = deserialize_datetime(1702638600)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_unix_timestamp_float(self):
        """Unix timestamp (float) preserves microseconds."""
        result = deserialize_datetime(1702638600.123456)
        assert result.microsecond == 123456

    def test_roundtrip(self):
        """Serialize then deserialize returns equivalent datetime."""
        original = datetime.now(UTC)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        assert original == deserialized

class TestSafeInt:
    def test_int_passthrough(self):
        """Integer values pass through unchanged."""
        assert safe_int(5) == 5

    def test_float_no_decimal(self):
        """Float with no decimal converts to int."""
        assert safe_int(5.0) == 5

    def test_float_with_decimal_raises(self):
        """Float with decimal raises ValueError by default."""
        with pytest.raises(ValueError, match="precision loss"):
            safe_int(5.9)

    def test_float_with_decimal_rounds(self):
        """Float with decimal rounds when round_floats=True."""
        assert safe_int(5.9, round_floats=True) == 6

    def test_truncation_bug_prevented(self):
        """BUG-034 scenario: 0.5 does not become 0."""
        with pytest.raises(ValueError):
            safe_int(0.5)
```

### Integration Tests

```python
# tests/integration/test_datetime_roundtrip.py

class TestGHAPDatetimeRoundtrip:
    """Regression tests for BUG-027."""

    async def test_ghap_entry_created_at_roundtrip(self):
        """GHAP entry created_at survives persist/retrieve."""
        # Create GHAP entry
        entry = await start_ghap(...)

        # Retrieve entries
        entries = await list_ghap_entries(limit=1)

        # Verify created_at is valid ISO format
        created_at = entries["entries"][0]["created_at"]
        assert isinstance(created_at, str)
        dt = deserialize_datetime(created_at)
        assert dt.tzinfo == UTC
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing persisted data | Low | High | `deserialize_datetime()` already handles both formats |
| Performance regression | Low | Low | Simple string operations, negligible overhead |
| Migration incomplete | Medium | Medium | Lint rule to flag direct `isoformat()`/`fromtimestamp()` |
| Decorator breaks function signatures | Low | Medium | Use `functools.wraps` and ParamSpec |

---

## Open Questions

1. **Should we add a lint rule?** A custom pylint/ruff rule could flag direct use of `datetime.isoformat()` and `datetime.fromtimestamp()` to encourage use of the centralized utilities.

2. **Should Decimal support be included?** The current spec focuses on float/int. If monetary values are added later, Decimal support may be needed.

3. **Should validation decorators be mandatory?** Could add to the reviewer checklist or make them required for MCP tool handlers.

---

## References

- BUG-027: TypeError in list_ghap_entries datetime parsing
- BUG-034: Float timeout truncation in QdrantVectorStore
- RESEARCH-bug-pattern-analysis.md: Theme T4 (Data Format/Parsing Mismatches)
- Recommendation R11: Type-Safe Datetime/Numeric Handling
- Existing utility: `src/clams/utils/datetime.py`
