"""Schema generation utilities for MCP tool definitions.

This module provides functions that generate JSON Schema property definitions
from the canonical enum values in enums.py. Using these functions ensures
schemas stay in sync with validation code.

Example:
    from clams.server.tools.schema import domain_schema, strategy_schema

    Tool(
        name="start_ghap",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": domain_schema(),
                "strategy": strategy_schema(),
                ...
            },
        },
    )
"""

from typing import Any

from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)

__all__ = [
    "axis_schema",
    "domain_schema",
    "outcome_status_schema",
    "root_cause_category_schema",
    "root_cause_object_schema",
    "strategy_schema",
]


def domain_schema() -> dict[str, Any]:
    """Generate JSON Schema property for domain field.

    Returns:
        JSON Schema property definition with:
        - type: "string"
        - description: Human-readable field description
        - enum: Valid domain values from DOMAINS
    """
    return {
        "type": "string",
        "description": "Task domain (debugging, refactoring, feature, etc.)",
        "enum": DOMAINS,
    }


def strategy_schema() -> dict[str, Any]:
    """Generate JSON Schema property for strategy field.

    Returns:
        JSON Schema property definition with:
        - type: "string"
        - description: Human-readable field description
        - enum: Valid strategy values from STRATEGIES
    """
    return {
        "type": "string",
        "description": "Problem-solving strategy",
        "enum": STRATEGIES,
    }


def axis_schema(*, include_default: bool = False) -> dict[str, Any]:
    """Generate JSON Schema property for clustering axis field.

    Args:
        include_default: If True, include default value of "full"

    Returns:
        JSON Schema property definition with:
        - type: "string"
        - description: Human-readable field description
        - enum: Valid axis values from VALID_AXES
        - default: "full" (only if include_default=True)
    """
    schema: dict[str, Any] = {
        "type": "string",
        "description": "Clustering axis (full, strategy, surprise, root_cause)",
        "enum": VALID_AXES,
    }
    if include_default:
        schema["default"] = "full"
    return schema


def outcome_status_schema() -> dict[str, Any]:
    """Generate JSON Schema property for outcome status field.

    Returns:
        JSON Schema property definition with:
        - type: "string"
        - description: Human-readable field description
        - enum: Valid status values from OUTCOME_STATUS_VALUES
    """
    return {
        "type": "string",
        "description": "Resolution status (confirmed, falsified, abandoned)",
        "enum": OUTCOME_STATUS_VALUES,
    }


def root_cause_category_schema() -> dict[str, Any]:
    """Generate JSON Schema property for root cause category field.

    Returns:
        JSON Schema property definition with:
        - type: "string"
        - description: Human-readable field description
        - enum: Valid category values from ROOT_CAUSE_CATEGORIES
    """
    return {
        "type": "string",
        "description": "Root cause category",
        "enum": ROOT_CAUSE_CATEGORIES,
    }


def root_cause_object_schema() -> dict[str, Any]:
    """Generate JSON Schema for root_cause object property.

    The root_cause object contains:
    - category: Root cause category enum
    - description: Free-text description

    Returns:
        JSON Schema object definition for root_cause
    """
    return {
        "type": "object",
        "description": "Why hypothesis was wrong (required for falsified)",
        "properties": {
            "category": root_cause_category_schema(),
            "description": {"type": "string"},
        },
    }
