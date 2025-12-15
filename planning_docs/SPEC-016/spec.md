# SPEC-016: Schema Generation Utility for JSON Schema Enums

## Background

BUG-026 identified and fixed a critical issue where JSON schema enum definitions in MCP tool definitions drifted from the actual validation code in `enums.py`. The fix replaced 17 hardcoded enum arrays with references to constants defined in `enums.py`, establishing a single source of truth.

However, the current solution has limitations:
1. Enum values are defined as Python lists, not Python `Enum` classes
2. Schema property definitions (enum, description) are still manually written inline
3. No automated verification that schemas stay in sync with validation logic

## Problem Statement

### Current State

Enum values are defined in `src/clams/server/tools/enums.py` as lists:

```python
DOMAINS = [
    "debugging",
    "refactoring",
    "feature",
    ...
]

STRATEGIES = [
    "systematic-elimination",
    "trial-and-error",
    ...
]
```

These lists are imported into `src/clams/server/tools/__init__.py` and used in tool definitions:

```python
Tool(
    name="start_ghap",
    inputSchema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Task domain",
                "enum": DOMAINS,  # <-- references the list
            },
            ...
        },
    },
)
```

### Problems

1. **Manual schema definition**: Even though `DOMAINS` is imported, the schema property shape (type, description, enum) is still manually written in every tool definition.

2. **Repeated schema fragments**: The same enum schema appears in multiple tools:
   - `domain` appears in `start_ghap`, `list_ghap_entries`, `search_experiences` (3 tools)
   - `strategy` appears in `start_ghap`, `update_ghap` (2 tools)
   - `axis` appears in `get_clusters`, `store_value`, `list_values`, `search_experiences` (4 tools)

3. **Inconsistent descriptions**: Each occurrence may have different descriptions for the same enum field.

4. **No compile-time verification**: If a new enum value is added, nothing verifies the description is updated or that all usages are consistent.

## Goals

1. **Single source of truth**: Define enum schemas once, use everywhere
2. **Consistent descriptions**: Same enum field has same description across all tools
3. **Easy maintenance**: Add new enum values in one place, schemas update automatically
4. **Type safety**: Use Python `Enum` classes where appropriate for validation

## Non-Goals

- Migrating existing list-based enums to `Enum` classes (deferred, optional enhancement)
- Auto-generating tool descriptions from code comments
- Schema validation at import time (runtime is sufficient)

## Solution Overview

Create a schema generation utility module that:

1. Defines reusable schema property fragments for each enum type
2. Provides helper functions to generate complete enum schema properties
3. Can be imported wherever tool schemas are defined

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   enums.py                  schema.py                       │
│   ┌──────────────┐         ┌──────────────────────────┐    │
│   │ DOMAINS      │────────>│ domain_schema()          │    │
│   │ STRATEGIES   │         │ strategy_schema()        │    │
│   │ VALID_AXES   │         │ axis_schema()            │    │
│   │ ...          │         │ ...                      │    │
│   └──────────────┘         └──────────────────────────┘    │
│                                    │                        │
│                                    v                        │
│                            ┌──────────────────────────┐    │
│                            │ __init__.py              │    │
│                            │ Tool definitions use     │    │
│                            │ schema functions         │    │
│                            └──────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Design

### 1. Schema Module (`src/clams/server/tools/schema.py`)

Create a new module that defines schema property generators:

```python
"""Schema generation utilities for MCP tool definitions.

This module provides functions that generate JSON Schema property definitions
from the canonical enum values in enums.py. Using these functions ensures
schemas stay in sync with validation code.
"""

from typing import Any

from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)


def domain_schema(required: bool = True) -> dict[str, Any]:
    """Generate JSON Schema property for domain field.

    Args:
        required: Whether field is required (affects description)

    Returns:
        JSON Schema property definition
    """
    return {
        "type": "string",
        "description": "Task domain (debugging, refactoring, feature, etc.)",
        "enum": DOMAINS,
    }


def strategy_schema() -> dict[str, Any]:
    """Generate JSON Schema property for strategy field."""
    return {
        "type": "string",
        "description": "Problem-solving strategy",
        "enum": STRATEGIES,
    }


def axis_schema(include_default: bool = False) -> dict[str, Any]:
    """Generate JSON Schema property for clustering axis field.

    Args:
        include_default: Whether to include default value

    Returns:
        JSON Schema property definition
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
    """Generate JSON Schema property for outcome status field."""
    return {
        "type": "string",
        "description": "Resolution status (confirmed, falsified, abandoned)",
        "enum": OUTCOME_STATUS_VALUES,
    }


def root_cause_category_schema() -> dict[str, Any]:
    """Generate JSON Schema property for root cause category field."""
    return {
        "type": "string",
        "description": "Root cause category",
        "enum": ROOT_CAUSE_CATEGORIES,
    }
```

### 2. Usage in Tool Definitions

Update `src/clams/server/tools/__init__.py` to use the schema functions:

**Before (current, with raw lists):**
```python
from clams.server.tools.enums import (
    DOMAINS,
    STRATEGIES,
    ...
)

Tool(
    name="start_ghap",
    inputSchema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Task domain",
                "enum": DOMAINS,
            },
            "strategy": {
                "type": "string",
                "description": "Problem-solving strategy",
                "enum": STRATEGIES,
            },
            ...
        },
    },
)
```

**After (with schema functions):**
```python
from clams.server.tools.schema import (
    domain_schema,
    strategy_schema,
    axis_schema,
    outcome_status_schema,
    root_cause_category_schema,
)

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
```

### 3. Benefits

1. **DRY**: Each enum property is defined once with its description
2. **Consistent**: Same field always has same description
3. **Maintainable**: Change description in one place, all tools update
4. **Clear intent**: Function name documents what the property is for
5. **Parameterizable**: Functions can accept options (e.g., `include_default`)

### 4. Enum Schema Registry (Optional Enhancement)

For more complex scenarios, a registry pattern could be used:

```python
from enum import Enum
from typing import Any

# Could convert list-based enums to Enum classes
class Domain(str, Enum):
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    FEATURE = "feature"
    ...

# Registry maps Enum classes to schema generators
ENUM_SCHEMAS: dict[type, dict[str, Any]] = {
    Domain: {
        "type": "string",
        "description": "Task domain",
        "enum": [e.value for e in Domain],
    },
    ...
}

def schema_for_enum(enum_class: type, **overrides: Any) -> dict[str, Any]:
    """Get JSON Schema for an Enum class with optional overrides."""
    base = ENUM_SCHEMAS[enum_class].copy()
    base.update(overrides)
    return base
```

This pattern is more powerful but requires migrating from lists to Enum classes. Recommended as a future enhancement, not for initial implementation.

## Migration Plan

### Phase 1: Create Schema Module (This Spec)

1. Create `src/clams/server/tools/schema.py` with schema generator functions
2. Add unit tests for schema generators
3. No changes to existing tool definitions yet

### Phase 2: Migrate Tool Definitions (Follow-up Task)

1. Update tool definitions to use schema functions
2. Remove direct imports of enum lists (except where still needed)
3. Verify all tests pass

### Phase 3: Add Sync Verification Test (Follow-up Task)

1. Create regression test that verifies schemas match validation
2. Test iterates all tool definitions, extracts enums, compares to `enums.py`
3. Fails if any mismatch detected

## Acceptance Criteria

### Schema Module

- [ ] `src/clams/server/tools/schema.py` exists with schema generator functions
- [ ] Functions provided for all existing enum types:
  - `domain_schema()`
  - `strategy_schema()`
  - `axis_schema()`
  - `outcome_status_schema()`
  - `root_cause_category_schema()`
- [ ] Each function returns a valid JSON Schema property definition
- [ ] Returned schemas include `type`, `description`, and `enum` keys
- [ ] Enum values in returned schemas match the source lists in `enums.py`

### Type Safety

- [ ] Module passes `mypy --strict` type checking
- [ ] All functions have proper type annotations
- [ ] Return types are `dict[str, Any]` (JSON Schema is dynamic)

### Testing

- [ ] Unit tests verify each schema function returns expected structure
- [ ] Unit tests verify enum values match source lists
- [ ] Tests verify schema functions are importable without side effects

### Documentation

- [ ] Module has docstring explaining its purpose
- [ ] Each function has docstring explaining its usage
- [ ] Example usage shown in docstrings

## Future Enhancements (Out of Scope)

1. **Enum class migration**: Convert list-based enums to Python `Enum` classes
2. **Schema registry**: Central registry mapping Enum classes to schemas
3. **Validation at import**: Raise errors if schema/validation mismatch detected at module load
4. **Auto-generated descriptions**: Derive descriptions from Enum member docstrings

## Open Questions

1. **Default values**: Should schema functions handle `default` uniformly, or per-function?
   - **Recommendation**: Per-function with optional parameter (e.g., `axis_schema(include_default=True)`)

2. **Required vs optional**: Should schema functions indicate if field is required?
   - **Recommendation**: No, `required` is specified at the tool level, not property level in JSON Schema

3. **Nested objects**: How to handle `root_cause` which is an object with a `category` enum inside?
   - **Recommendation**: Provide `root_cause_object_schema()` that returns the full nested structure
