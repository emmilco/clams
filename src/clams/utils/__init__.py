"""CLAMS utility modules.

Provides centralized utilities for:
- datetime: Consistent datetime serialization/deserialization (R11-A)
- numeric: Type-safe numeric conversions (R11-B)
- validation: Function parameter validation decorators
- platform: Platform capability detection (SPEC-033)
- schema: JSON Schema generation from Python Enum classes (SPEC-016)
- tokens: Token estimation for budget and size assertions (SPEC-046)
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
from clams.utils.platform import (
    PlatformInfo,
    check_requirements,
    format_report,
    get_platform_info,
)
from clams.utils.schema import (
    enum_schema,
    enum_schema_from_list,
    get_enum_diff,
    get_enum_values,
    validate_enum_schema,
)
from clams.utils.tokens import (
    estimate_tokens,
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
    # Platform utilities (SPEC-033)
    "PlatformInfo",
    "get_platform_info",
    "check_requirements",
    "format_report",
    # Schema utilities (SPEC-016)
    "get_enum_values",
    "enum_schema",
    "validate_enum_schema",
    "get_enum_diff",
    "enum_schema_from_list",
    # Validation decorators
    "validate_datetime_params",
    "validate_numeric_range",
    # Token utilities (SPEC-046)
    "estimate_tokens",
]
