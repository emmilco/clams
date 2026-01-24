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

# Validate without parsing (non-throwing)
if is_valid_datetime_format(user_input):
    dt = deserialize_datetime(user_input)
```

### Design Decisions

- **Always UTC**: All serialization outputs UTC timezone for naive datetimes
- **Naive = UTC**: Naive datetimes are assumed to be UTC
- **Backwards compatible**: `deserialize_datetime()` accepts both ISO strings and Unix timestamps
- **Non-UTC preserved**: Timezone-aware datetimes with non-UTC timezones are preserved as-is

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

### Design Decisions

- **Fail loudly**: `safe_int()` raises by default on precision loss
- **Explicit opt-in**: Use `round_floats=True` to explicitly request rounding
- **Type preservation**: `clamp()` preserves the input numeric type

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

### Features

- Works with both sync and async functions
- Preserves function signatures for IDE support
- None values are allowed for optional parameters
- Clear, actionable error messages

### Error Messages

```
Parameter 'since' must be ISO 8601 format (e.g., '2024-12-15T10:30:00+00:00'), got: 'invalid'
Parameter 'timeout' must be in range [0.1, 300.0], got: 500.0
```

## API Reference

### Datetime Functions

| Function | Description |
|----------|-------------|
| `serialize_datetime(dt)` | Convert datetime to ISO 8601 string |
| `deserialize_datetime(value)` | Parse datetime from ISO string or Unix timestamp |
| `serialize_datetime_optional(dt)` | Serialize with None passthrough |
| `deserialize_datetime_optional(value)` | Deserialize with None passthrough |
| `is_valid_datetime_format(value)` | Check if string is valid ISO 8601 (non-throwing) |

### Numeric Functions

| Function | Description |
|----------|-------------|
| `safe_int(value, round_floats=False)` | Convert to int with precision loss protection |
| `clamp(value, min_val, max_val)` | Clamp to range, preserving type |
| `is_positive(value)` | Check if value > 0 |

### Validation Decorators

| Decorator | Description |
|-----------|-------------|
| `@validate_datetime_params(*names)` | Validate ISO 8601 string parameters |
| `@validate_numeric_range(name, min, max)` | Validate numeric parameter in range |

## References

- BUG-027: TypeError in list_ghap_entries datetime parsing
- BUG-034: Float timeout truncation in QdrantVectorStore
- R11: Type-Safe Datetime/Numeric Handling recommendation
