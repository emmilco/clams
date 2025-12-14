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

from datetime import datetime, timezone
from typing import Union

__all__ = ["serialize_datetime", "deserialize_datetime"]


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
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def deserialize_datetime(value: Union[str, float, int]) -> datetime:
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
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    elif isinstance(value, (int, float)):
        # Handle Unix timestamps
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError) as e:
            raise ValueError(
                f"Cannot parse Unix timestamp: {value!r}"
            ) from e

    else:
        raise TypeError(
            f"Cannot deserialize datetime from {type(value).__name__}: {value!r}. "
            f"Expected str (ISO 8601), int, or float (Unix timestamp)."
        )
