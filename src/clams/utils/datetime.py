"""Centralized datetime handling for consistent serialization.

This module provides a single source of truth for datetime serialization
and deserialization across the CLAMS codebase. All datetime storage and
retrieval should use these utilities to prevent format mismatches.

Reference: BUG-027 - datetime stored as ISO string but read expecting
numeric timestamp, causing deserialization failures.

Design decisions:
- Always serialize to ISO 8601 format with UTC timezone
- Accept both ISO strings and Unix timestamps for deserialization
- Naive datetimes are assumed to be UTC (not local time)
- All returned datetimes are timezone-aware (UTC)
"""

from datetime import UTC, datetime

__all__ = [
    "serialize_datetime",
    "deserialize_datetime",
    "serialize_datetime_optional",
    "deserialize_datetime_optional",
    "is_valid_datetime_format",
]


def serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO 8601 string with UTC timezone.

    Args:
        dt: Datetime to serialize. If naive (no timezone), assumes UTC.

    Returns:
        ISO 8601 formatted string (e.g., "2024-12-14T10:30:00+00:00")

    Examples:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        >>> serialize_datetime(dt)
        '2024-12-14T10:30:00+00:00'

        >>> # Naive datetime is assumed to be UTC
        >>> naive_dt = datetime(2024, 12, 14, 10, 30, 0)
        >>> serialize_datetime(naive_dt)
        '2024-12-14T10:30:00+00:00'
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def deserialize_datetime(value: str | float | int) -> datetime:
    """Deserialize datetime from various formats.

    Handles both ISO 8601 strings and Unix timestamps to provide
    backwards compatibility with existing data stored in different formats.

    Args:
        value: One of:
            - ISO 8601 string (e.g., "2024-12-14T10:30:00+00:00")
            - Unix timestamp as int (seconds since epoch)
            - Unix timestamp as float (seconds with microseconds)

    Returns:
        Timezone-aware datetime in UTC.

    Raises:
        ValueError: If value cannot be parsed as a datetime.
        TypeError: If value is not a str, int, or float.

    Examples:
        >>> # ISO string with timezone
        >>> deserialize_datetime("2024-12-14T10:30:00+00:00")
        datetime.datetime(2024, 12, 14, 10, 30, tzinfo=datetime.timezone.utc)

        >>> # ISO string without timezone (assumes UTC)
        >>> deserialize_datetime("2024-12-14T10:30:00")
        datetime.datetime(2024, 12, 14, 10, 30, tzinfo=datetime.timezone.utc)

        >>> # Unix timestamp (integer)
        >>> deserialize_datetime(1702551000)
        datetime.datetime(2023, 12, 14, 10, 30, tzinfo=datetime.timezone.utc)

        >>> # Unix timestamp (float with microseconds)
        >>> deserialize_datetime(1702551000.123456)
        datetime.datetime(2023, 12, 14, 10, 30, 0, 123456, tzinfo=datetime.timezone.utc)
    """
    if isinstance(value, str):
        # Handle ISO 8601 strings
        # fromisoformat handles both timezone-aware and naive strings
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as e:
            raise ValueError(f"Cannot parse ISO datetime string: {value!r}") from e

        # Ensure UTC timezone if naive
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    elif isinstance(value, (int, float)):
        # Handle Unix timestamps
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OSError, OverflowError, ValueError) as e:
            raise ValueError(
                f"Cannot parse Unix timestamp: {value!r}"
            ) from e

    else:
        raise TypeError(
            f"Cannot deserialize datetime from {type(value).__name__}: {value!r}. "
            f"Expected str (ISO 8601), int, or float (Unix timestamp)."
        )


def is_valid_datetime_format(value: str) -> bool:
    """Check if string is valid ISO 8601 format that can be parsed.

    Non-throwing validation - returns True if deserialize_datetime() would succeed
    on a string input. Useful for input validation before processing.

    Args:
        value: String to validate

    Returns:
        True if the string can be parsed as ISO 8601 by datetime.fromisoformat(),
        False otherwise

    Examples:
        >>> is_valid_datetime_format("2024-12-15T10:30:00+00:00")
        True
        >>> is_valid_datetime_format("2024-12-15T10:30:00")
        True
        >>> is_valid_datetime_format("2024-12-15")  # Date-only is valid
        True
        >>> is_valid_datetime_format("invalid")
        False
        >>> is_valid_datetime_format("")
        False

    Note:
        This function accepts any format that datetime.fromisoformat() accepts,
        which includes:
        - Full datetime with timezone: "2024-12-15T10:30:45+00:00"
        - Full datetime without timezone: "2024-12-15T10:30:45"
        - With microseconds: "2024-12-15T10:30:45.123456+00:00"
        - Z suffix (Python 3.11+): "2024-12-15T10:30:45Z"
        - Date only: "2024-12-15" (assumes midnight)
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

    Convenience wrapper for nullable datetime fields.

    Args:
        dt: Datetime to serialize, or None

    Returns:
        ISO 8601 string if dt is not None, else None

    Examples:
        >>> from datetime import datetime, UTC
        >>> serialize_datetime_optional(datetime(2024, 12, 15, 10, 30, tzinfo=UTC))
        '2024-12-15T10:30:00+00:00'
        >>> serialize_datetime_optional(None)
        None
    """
    if dt is None:
        return None
    return serialize_datetime(dt)


def deserialize_datetime_optional(value: str | float | int | None) -> datetime | None:
    """Deserialize optional datetime, returning None for None input.

    Convenience wrapper for nullable datetime fields.

    Args:
        value: Value to deserialize (ISO string, Unix timestamp), or None

    Returns:
        UTC datetime if value is not None, else None

    Raises:
        ValueError: If value is non-None and cannot be parsed
        TypeError: If value is non-None and wrong type

    Examples:
        >>> deserialize_datetime_optional("2024-12-15T10:30:00+00:00")
        datetime.datetime(2024, 12, 15, 10, 30, tzinfo=datetime.timezone.utc)
        >>> deserialize_datetime_optional(None)
        None
    """
    if value is None:
        return None
    return deserialize_datetime(value)
