"""Schema generation utilities for JSON Schema from Python Enum classes.

This module provides functions to generate or validate JSON schema enum
definitions from Python Enum classes. It supports both standard Enum classes
and str-based enums.

Example:
    from enum import Enum
    from clams.utils.schema import enum_schema, validate_enum_schema

    class Status(Enum):
        PENDING = "pending"
        ACTIVE = "active"
        COMPLETED = "completed"

    # Generate a JSON schema property definition
    schema = enum_schema(Status, description="Task status")
    # Returns: {"type": "string", "description": "Task status",
    #           "enum": ["pending", "active", "completed"]}

    # Validate that a schema matches an enum
    is_valid = validate_enum_schema(Status, existing_schema)
"""

from enum import Enum
from typing import Any


def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """Extract string values from an Enum class.

    Args:
        enum_class: A Python Enum class to extract values from.

    Returns:
        A list of string values from the enum members.

    Raises:
        TypeError: If enum_class is not an Enum type.
        ValueError: If enum values are not strings.

    Example:
        >>> class Color(Enum):
        ...     RED = "red"
        ...     GREEN = "green"
        >>> get_enum_values(Color)
        ['red', 'green']
    """
    if not isinstance(enum_class, type) or not issubclass(enum_class, Enum):
        raise TypeError(f"Expected Enum class, got {type(enum_class).__name__}")

    values: list[str] = []
    for member in enum_class:
        if not isinstance(member.value, str):
            raise ValueError(
                f"Enum {enum_class.__name__}.{member.name} has non-string value: "
                f"{type(member.value).__name__}"
            )
        values.append(member.value)
    return values


def enum_schema(
    enum_class: type[Enum],
    *,
    description: str | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """Generate a JSON Schema property definition from an Enum class.

    Args:
        enum_class: A Python Enum class to generate schema from.
        description: Optional human-readable description for the field.
        default: Optional default value (must be a valid enum value).

    Returns:
        A JSON Schema property definition with type, enum, and optional
        description/default fields.

    Raises:
        TypeError: If enum_class is not an Enum type.
        ValueError: If enum values are not strings or default is invalid.

    Example:
        >>> class Priority(Enum):
        ...     LOW = "low"
        ...     MEDIUM = "medium"
        ...     HIGH = "high"
        >>> enum_schema(Priority, description="Task priority", default="medium")
        {'type': 'string', 'description': 'Task priority',
         'enum': ['low', 'medium', 'high'], 'default': 'medium'}
    """
    values = get_enum_values(enum_class)

    if default is not None and default not in values:
        raise ValueError(
            f"Default '{default}' is not a valid value for {enum_class.__name__}. "
            f"Valid values: {values}"
        )

    schema: dict[str, Any] = {
        "type": "string",
        "enum": values,
    }

    if description is not None:
        schema["description"] = description

    if default is not None:
        schema["default"] = default

    return schema


def validate_enum_schema(
    enum_class: type[Enum],
    schema: dict[str, Any],
) -> bool:
    """Validate that a JSON schema's enum values match a Python Enum class.

    This function checks whether the 'enum' array in a JSON schema definition
    contains exactly the same values (in any order) as the Python Enum class.

    Args:
        enum_class: A Python Enum class to validate against.
        schema: A JSON Schema property definition with an 'enum' key.

    Returns:
        True if the schema's enum values match the Enum class values.
        False if they don't match or if schema lacks 'enum' key.

    Example:
        >>> class Status(Enum):
        ...     ACTIVE = "active"
        ...     INACTIVE = "inactive"
        >>> schema = {"type": "string", "enum": ["active", "inactive"]}
        >>> validate_enum_schema(Status, schema)
        True
        >>> bad_schema = {"type": "string", "enum": ["active", "unknown"]}
        >>> validate_enum_schema(Status, bad_schema)
        False
    """
    if "enum" not in schema:
        return False

    schema_values = set(schema["enum"])
    enum_values = set(get_enum_values(enum_class))

    return schema_values == enum_values


def get_enum_diff(
    enum_class: type[Enum],
    schema: dict[str, Any],
) -> dict[str, list[str]]:
    """Get the difference between a Python Enum and a JSON schema's enum values.

    Args:
        enum_class: A Python Enum class to compare.
        schema: A JSON Schema property definition with an 'enum' key.

    Returns:
        A dict with two keys:
        - 'missing_in_schema': Values in the Enum but not in the schema
        - 'extra_in_schema': Values in the schema but not in the Enum

    Raises:
        KeyError: If schema lacks 'enum' key.

    Example:
        >>> class Status(Enum):
        ...     ACTIVE = "active"
        ...     PENDING = "pending"
        >>> schema = {"type": "string", "enum": ["active", "unknown"]}
        >>> get_enum_diff(Status, schema)
        {'missing_in_schema': ['pending'], 'extra_in_schema': ['unknown']}
    """
    if "enum" not in schema:
        raise KeyError("Schema does not contain 'enum' key")

    schema_values = set(schema["enum"])
    enum_values = set(get_enum_values(enum_class))

    return {
        "missing_in_schema": sorted(enum_values - schema_values),
        "extra_in_schema": sorted(schema_values - enum_values),
    }


def enum_schema_from_list(
    values: list[str],
    *,
    description: str | None = None,
    default: str | None = None,
) -> dict[str, Any]:
    """Generate a JSON Schema property definition from a list of values.

    This is a convenience function for cases where enum values are already
    defined as lists (not Enum classes).

    Args:
        values: A list of string values for the enum.
        description: Optional human-readable description for the field.
        default: Optional default value (must be in the values list).

    Returns:
        A JSON Schema property definition with type, enum, and optional
        description/default fields.

    Raises:
        ValueError: If values is empty or default is not in values.
        TypeError: If values contains non-strings.

    Example:
        >>> values = ["low", "medium", "high"]
        >>> enum_schema_from_list(values, description="Priority level")
        {'type': 'string', 'enum': ['low', 'medium', 'high'],
         'description': 'Priority level'}
    """
    if not values:
        raise ValueError("Values list cannot be empty")

    for v in values:
        if not isinstance(v, str):
            raise TypeError(f"All values must be strings, got {type(v).__name__}")

    if default is not None and default not in values:
        raise ValueError(
            f"Default '{default}' is not in values list. Valid values: {values}"
        )

    schema: dict[str, Any] = {
        "type": "string",
        "enum": list(values),  # Make a copy to avoid mutation
    }

    if description is not None:
        schema["description"] = description

    if default is not None:
        schema["default"] = default

    return schema
