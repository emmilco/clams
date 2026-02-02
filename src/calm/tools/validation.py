"""Validation utilities for MCP tools."""

import re
from uuid import UUID


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


def validate_uuid(value: str, field_name: str = "id") -> None:
    """Validate that a string is a valid UUID.

    Args:
        value: String to validate
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If value is not a valid UUID
    """
    try:
        UUID(value)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid UUID format for {field_name}: {value}") from e


def validate_query_string(
    query: str, max_length: int = 10000, field_name: str = "query"
) -> None:
    """Validate a query string.

    Args:
        query: Query string to validate
        max_length: Maximum allowed length
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If query exceeds max length
    """
    if len(query) > max_length:
        raise ValidationError(
            f"{field_name} too long ({len(query)} chars). "
            f"Maximum allowed is {max_length} characters."
        )


def validate_importance_range(value: float, field_name: str = "importance") -> None:
    """Validate that a value is in the 0.0-1.0 range.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If value is not in range
    """
    if not 0.0 <= value <= 1.0:
        raise ValidationError(
            f"{field_name} {value} out of range. Must be between 0.0 and 1.0."
        )


def validate_tags(
    tags: list[str] | None, max_count: int = 20, max_length: int = 50
) -> None:
    """Validate a list of tags.

    Args:
        tags: List of tags to validate
        max_count: Maximum number of tags allowed
        max_length: Maximum length per tag

    Raises:
        ValidationError: If tags are invalid
    """
    if tags is None:
        return

    if len(tags) > max_count:
        raise ValidationError(f"Too many tags ({len(tags)}). Maximum is {max_count}.")

    for tag in tags:
        if not isinstance(tag, str):
            raise ValidationError(f"Invalid tag type: {type(tag).__name__}")
        if len(tag) > max_length:
            raise ValidationError(
                f"Tag '{tag[:20]}...' too long ({len(tag)} chars). "
                f"Maximum is {max_length} characters."
            )
        if not re.match(r"^[\w\-\.]+$", tag):
            raise ValidationError(
                f"Invalid tag '{tag}'. Tags must contain only "
                "alphanumeric characters, hyphens, underscores, and dots."
            )
