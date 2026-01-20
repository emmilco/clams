# SPEC-057: Add Validation to Remaining MCP Tool Parameters

## Problem Statement

The R4-A validation audit (see `planning_docs/RESEARCH-validation-audit.md`) identified that while most MCP tools have good validation, there are specific gaps that could lead to cryptic errors or silent failures.

**What's already validated** (no work needed):
- All GHAP tools - excellent validation including conditional requirements
- Memory tools - category, importance, limit/offset validation
- Git tools - date format, limit ranges
- Learning tools - axis, cluster_id format, text lengths
- Search tools - axis, domain, outcome, limit

**Actual gaps identified in audit**:
- `assemble_context` - missing validation for all parameters (Critical - BUG-036 risk)
- `retrieve_memories` - missing `min_importance` range validation
- `store_memory`/`list_memories` - missing tags array validation
- `delete_memory` - missing UUID format validation
- `search_code` - missing language validation
- `index_codebase` - missing project format validation
- `update_ghap` - missing note length validation
- `distribute_budget` - missing max_tokens validation

**Reference**: R4-E from bug pattern analysis (Theme T5: Missing Input Validation)

## Proposed Solution

Add validation to the specific parameters identified as gaps, following the existing validation patterns in the codebase.

## Acceptance Criteria

### Critical: assemble_context (`src/clams/server/tools/context.py`)

- [ ] Validate `context_types` against known types: `["values", "experiences"]`
- [ ] Invalid types return error listing valid options
- [ ] Validate `limit` range (1-50)
- [ ] Validate `max_tokens` range (100-10000)
- [ ] Empty `query` returns empty result gracefully (not error)

### Memory Tools (`src/clams/server/tools/memory.py`)

- [ ] `retrieve_memories`: Validate `min_importance` in range 0.0-1.0
- [ ] `store_memory`: Validate `tags` max count (20) and max tag length (50 chars)
- [ ] `list_memories`: Validate `tags` same as store_memory
- [ ] `delete_memory`: Validate `memory_id` is valid UUID format

### Code Tools (`src/clams/server/tools/code.py`)

- [ ] `search_code`: Validate `language` against supported list with helpful error
- [ ] `index_codebase`: Validate `project` format (alphanumeric, dashes, underscores, max 100 chars)

### GHAP Tools (`src/clams/server/tools/ghap.py`)

- [ ] `update_ghap`: Validate `note` max length (2000 chars, consistent with other fields)

### Token Management (`src/clams/context/tokens.py`)

- [ ] `distribute_budget`: Validate `max_tokens` is positive and reasonable (1-100000)

### Error Format

Use the existing error format pattern from the codebase:
```python
# For tool-level errors (returned to user)
return {
    "error": "validation_error",
    "message": f"Invalid {param}: {value}. Valid options: {', '.join(valid)}"
}

# For internal validation (raise exception)
raise ValidationError(f"Invalid {param}: {value}. Valid options: {', '.join(valid)}")
```

## Implementation Notes

**Validation helper for arrays** (add to `enums.py` or create `validation.py`):
```python
def validate_tags(tags: list[str] | None, max_count: int = 20, max_length: int = 50) -> None:
    """Validate tags array."""
    if tags is None:
        return
    if len(tags) > max_count:
        raise ValidationError(f"Too many tags: {len(tags)}. Maximum: {max_count}")
    for i, tag in enumerate(tags):
        if len(tag) > max_length:
            raise ValidationError(
                f"Tag {i} too long: {len(tag)} chars. Maximum: {max_length}"
            )
```

**UUID validation**:
```python
import uuid

def validate_uuid(value: str, param_name: str) -> None:
    """Validate string is valid UUID format."""
    try:
        uuid.UUID(value)
    except ValueError:
        raise ValidationError(f"Invalid {param_name}: must be a valid UUID")
```

**Supported languages for search_code** (check actual implementation):
```python
SUPPORTED_LANGUAGES = ["python", "typescript", "javascript", "rust", "go", "java", ...]
```

## Testing Requirements

Create new test file `tests/server/tools/test_input_validation.py`:

- [ ] Test: `assemble_context` with invalid context_type returns error listing valid options
- [ ] Test: `assemble_context` with limit=0 or limit=100 returns range error
- [ ] Test: `assemble_context` with empty query returns empty result (not error)
- [ ] Test: `retrieve_memories` with min_importance=1.5 returns range error
- [ ] Test: `store_memory` with 25 tags returns count error
- [ ] Test: `store_memory` with 60-char tag returns length error
- [ ] Test: `delete_memory` with "not-a-uuid" returns format error
- [ ] Test: `search_code` with language="invalid" returns error listing supported languages
- [ ] Test: `index_codebase` with project="has spaces!" returns format error
- [ ] Test: `update_ghap` with 3000-char note returns length error
- [ ] Test: `distribute_budget` with max_tokens=-1 returns error
- [ ] All error messages include valid options or acceptable ranges

## Out of Scope

- Validation that already exists (see "What's already validated" above)
- Changing error message format (use existing patterns)
- Adding validation to tools not in the audit
- Performance optimization of validation
- Schema-level validation (JSON schema already handles basic types)
