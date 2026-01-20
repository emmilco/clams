# SPEC-057: Add Validation to Remaining MCP Tool Parameters

## Problem Statement

BUG-036 showed `distribute_budget()` raised cryptic `KeyError` on invalid input instead of a helpful error listing valid options. BUG-029 showed `start_ghap` with an active entry returned generic "internal_error" instead of actionable guidance.

While these specific bugs have been fixed, a systematic audit (R4-A) identified that many MCP tools still lack comprehensive input validation with helpful error messages.

**Reference**: R4-E from bug pattern analysis (Theme T5: Missing Input Validation)

## Proposed Solution

Apply consistent input validation pattern to all MCP tools:
1. Validate enum parameters against valid values
2. Validate numeric constraints (min/max)
3. Return structured errors with valid options listed
4. Never raise uncaught exceptions for invalid user input

## Acceptance Criteria

- [ ] All MCP tools validate enum parameters with helpful errors
- [ ] All MCP tools validate numeric constraints (e.g., `limit > 0`, `limit <= max`)
- [ ] Error responses include:
  - `error`: Error type (e.g., `"invalid_parameter"`)
  - `message`: Human-readable message listing valid options
  - `parameter`: Which parameter was invalid
- [ ] No uncaught `KeyError`, `ValueError`, or similar for user input
- [ ] Test coverage for invalid inputs on each tool

### Tools to Update

Based on R4-A audit, these tools need validation improvements:

**Memory Tools** (`server/tools/memory.py`):
- [ ] `store_memory`: Validate `category` against valid categories
- [ ] `retrieve_memories`: Validate `category` if provided
- [ ] `list_memories`: Validate `category`, `limit` (1-200), `offset` (>= 0)

**Code Tools** (`server/tools/code.py`):
- [ ] `search_code`: Validate `limit` (1-50)
- [ ] `find_similar_code`: Validate `limit` (1-50), `snippet` length

**Git Tools** (`server/tools/git.py`):
- [ ] `search_commits`: Validate `limit` (1-50)
- [ ] `get_file_history`: Validate `limit` (1-500)
- [ ] `get_churn_hotspots`: Validate `days` (1-365), `limit` (1-50)

**Learning Tools** (`server/tools/learning.py`):
- [ ] `get_clusters`: Validate `axis` against valid axes
- [ ] `search_experiences`: Validate `axis`, `domain`, `outcome`, `limit`
- [ ] `validate_value`: Validate `cluster_id` format
- [ ] `store_value`: Validate `axis`, `cluster_id`, `text` length

**Context Tools** (`server/tools/context.py`):
- [ ] `assemble_context`: Validate `context_types` against valid types

## Implementation Notes

Standard validation pattern:
```python
from clams.server.tools.enums import VALID_CATEGORIES, VALID_AXES

async def tool_impl(category: str | None = None, limit: int = 10) -> dict:
    # Validate enum parameter
    if category is not None and category not in VALID_CATEGORIES:
        return {
            "error": "invalid_parameter",
            "parameter": "category",
            "message": f"Invalid category '{category}'. Valid options: {', '.join(sorted(VALID_CATEGORIES))}",
        }

    # Validate numeric constraint
    if limit < 1 or limit > 100:
        return {
            "error": "invalid_parameter",
            "parameter": "limit",
            "message": f"limit must be between 1 and 100, got {limit}",
        }

    # Normal processing...
```

Error response format (consistent across all tools):
```json
{
    "error": "invalid_parameter",
    "parameter": "category",
    "message": "Invalid category 'invalid'. Valid options: decision, error, event, fact, preference, workflow"
}
```

## Testing Requirements

- Each tool has at least one invalid enum input test
- Each tool has at least one invalid numeric constraint test
- Tests verify error messages list valid options
- Tests verify error includes parameter name
- No uncaught exceptions from any invalid input
- Add tests to `tests/server/tools/test_input_validation.py`

## Out of Scope

- Validation of business logic (e.g., "can't start GHAP with active entry" - already done)
- Schema-level validation (JSON schema already validates types)
- Performance optimization of validation
