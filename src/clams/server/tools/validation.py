"""Validation helpers for MCP tool parameters.

This module provides reusable validation functions that follow the
established patterns from enums.py - raising ValidationError with
descriptive messages that include valid options/ranges.
"""

import re
import uuid as uuid_lib
from collections.abc import Sequence

from clams.server.errors import ValidationError

# Valid context types for assemble_context
VALID_CONTEXT_TYPES = ["values", "experiences"]

# Supported languages for code search (lowercase)
SUPPORTED_LANGUAGES = [
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "java",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
]

# Project identifier pattern: alphanumeric, dashes, underscores
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
PROJECT_ID_MAX_LENGTH = 100


def validate_context_types(context_types: list[str]) -> None:
    """Validate context types for assemble_context.

    Args:
        context_types: List of context type strings

    Raises:
        ValidationError: If any context type is invalid
    """
    invalid = [t for t in context_types if t not in VALID_CONTEXT_TYPES]
    if invalid:
        raise ValidationError(
            f"Invalid context types: {invalid}. "
            f"Valid options: {', '.join(VALID_CONTEXT_TYPES)}"
        )


def validate_importance_range(
    importance: float, param_name: str = "importance"
) -> None:
    """Validate importance value is in range 0.0-1.0.

    Args:
        importance: Importance value to validate
        param_name: Parameter name for error message

    Raises:
        ValidationError: If importance is out of range
    """
    if not 0.0 <= importance <= 1.0:
        raise ValidationError(
            f"{param_name.capitalize()} {importance} out of range. "
            f"Must be between 0.0 and 1.0."
        )


def validate_tags(
    tags: Sequence[str] | None,
    max_count: int = 20,
    max_length: int = 50,
) -> None:
    """Validate tags array.

    Args:
        tags: List of tag strings (or None)
        max_count: Maximum number of tags allowed
        max_length: Maximum length per tag

    Raises:
        ValidationError: If tags exceed count or length limits
    """
    if tags is None:
        return

    if len(tags) > max_count:
        raise ValidationError(
            f"Too many tags: {len(tags)}. Maximum allowed: {max_count}"
        )

    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise ValidationError(
                f"Tag at index {i} must be a string, got {type(tag).__name__}"
            )
        if len(tag) > max_length:
            raise ValidationError(
                f"Tag at index {i} too long ({len(tag)} chars). "
                f"Maximum: {max_length} characters"
            )


def validate_uuid(value: str, param_name: str = "id") -> None:
    """Validate string is valid UUID format.

    Args:
        value: String to validate
        param_name: Parameter name for error message

    Raises:
        ValidationError: If value is not a valid UUID
    """
    try:
        uuid_lib.UUID(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {param_name}: '{value}' is not a valid UUID format"
        )


def validate_language(language: str | None) -> None:
    """Validate programming language for code search.

    Args:
        language: Language string (or None to skip)

    Raises:
        ValidationError: If language is not supported
    """
    if language is None:
        return

    lang_lower = language.lower()
    if lang_lower not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Unsupported language: '{language}'. "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )


def validate_project_id(project: str) -> None:
    """Validate project identifier format.

    Project IDs must be:
    - Alphanumeric with dashes and underscores
    - Start with alphanumeric character
    - Max 100 characters

    Args:
        project: Project identifier string

    Raises:
        ValidationError: If project format is invalid
    """
    if not project:
        raise ValidationError("Project identifier cannot be empty")

    if len(project) > PROJECT_ID_MAX_LENGTH:
        raise ValidationError(
            f"Project identifier too long ({len(project)} chars). "
            f"Maximum: {PROJECT_ID_MAX_LENGTH} characters"
        )

    if not PROJECT_ID_PATTERN.match(project):
        raise ValidationError(
            f"Invalid project identifier: '{project}'. "
            f"Must contain only alphanumeric characters, dashes, and underscores, "
            f"and start with an alphanumeric character"
        )


def validate_limit_range(
    limit: int,
    min_val: int,
    max_val: int,
    param_name: str = "limit",
) -> None:
    """Validate integer is within allowed range.

    Args:
        limit: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        param_name: Parameter name for error message

    Raises:
        ValidationError: If limit is out of range
    """
    if not min_val <= limit <= max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {limit} out of range. "
            f"Must be between {min_val} and {max_val}."
        )


def validate_positive_int(
    value: int, param_name: str, max_val: int | None = None
) -> None:
    """Validate integer is positive (and optionally within max).

    Args:
        value: Value to validate
        param_name: Parameter name for error message
        max_val: Optional maximum value

    Raises:
        ValidationError: If value is not positive or exceeds max
    """
    if value < 1:
        raise ValidationError(
            f"{param_name.capitalize()} must be positive, got {value}"
        )
    if max_val is not None and value > max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {value} exceeds maximum of {max_val}"
        )


def validate_text_length(
    text: str | None,
    max_length: int,
    param_name: str,
    allow_empty: bool = True,
) -> None:
    """Validate text length.

    Args:
        text: Text to validate (or None to skip)
        max_length: Maximum allowed length
        param_name: Parameter name for error message
        allow_empty: Whether empty strings are allowed

    Raises:
        ValidationError: If text exceeds max length or is empty when not allowed
    """
    if text is None:
        return

    if not allow_empty and not text.strip():
        raise ValidationError(f"{param_name.capitalize()} cannot be empty")

    if len(text) > max_length:
        raise ValidationError(
            f"{param_name.capitalize()} too long ({len(text)} chars). "
            f"Maximum: {max_length} characters"
        )
