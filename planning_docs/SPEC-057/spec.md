# SPEC-057: Add Validation to Remaining MCP Tool Parameters (R4-E)

## Overview

Audit all MCP tools and add input validation to any parameters that currently lack proper validation, ensuring consistent error handling across the API.

## Background

Some MCP tool parameters may accept invalid inputs without proper validation. This creates inconsistent behavior and potential runtime errors. All parameters should be validated with helpful error messages.

### Existing Infrastructure

The codebase already has validation infrastructure:
- `clams/server/errors.py`: Defines `ValidationError` exception
- `clams/server/tools/validation.py`: Shared validators for common patterns

### MCP Tools to Audit

Located in `clams/server/tools/`:
- `memory.py`: store_memory, retrieve_memories, list_memories, delete_memory
- `code.py`: index_codebase, search_code, find_similar_code
- `git.py`: index_commits, search_commits, get_file_history, get_churn_hotspots, get_code_authors
- `ghap.py`: start_ghap, update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
- `learning.py`: get_clusters, get_cluster_members, validate_value, store_value, list_values
- `context.py`: assemble_context
- `search.py`: search_experiences
- `session.py`: start_session, get_orphaned_ghap, should_check_in, increment_tool_count, reset_tool_count
- `__init__.py`: ping (health check, no parameters)

## Requirements

### Functional Requirements

1. Audit each MCP tool and document validation status of all parameters
2. Add validation for any unvalidated parameters using `ValidationError`
3. Use shared validators from `validation.py` where applicable
4. Create new shared validators for patterns used 2+ times

### Non-Functional Requirements

1. Validation fails fast (check before processing)
2. Error messages include: parameter name, invalid value, valid options/range
3. Use existing `ValidationError` pattern consistently

## Validation Patterns

New validators use this pattern (matching existing code):
```python
from clams.server.errors import ValidationError

def validate_example(value: str, param_name: str = "example") -> None:
    if not is_valid(value):
        raise ValidationError(f"{param_name} must be XYZ, got: {value}")
```

Error messages must include:
- Parameter name
- What was expected (valid values/range)
- What was received (the actual invalid value)

## Acceptance Criteria

- [ ] Audit document created: `planning_docs/SPEC-057/audit.md` listing each tool/parameter and validation status
- [ ] All parameters in audit document have validation (existing or new)
- [ ] New validators added to `clams/server/tools/validation.py` for reusable patterns
- [ ] All new validation uses `ValidationError` from `clams/server/errors.py`
- [ ] Error messages follow pattern: "{param} must be {expected}, got: {actual}"
- [ ] Unit tests added for each new validator
- [ ] Integration tests verify validation errors returned correctly from tools
- [ ] All existing tests continue to pass
- [ ] No breaking changes to valid API calls

## Out of Scope

- Changing existing validation behavior
- Adding new parameters to tools
- Schema documentation updates (separate task)
- Validation of MCP schema types (handled by FastMCP framework)
