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
