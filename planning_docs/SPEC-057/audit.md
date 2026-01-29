# SPEC-057: Validation Audit

## Summary

This audit documents the validation status of all MCP tool parameters across the CLAMS codebase. Parameters are marked as:
- **Validated**: Has explicit validation with `ValidationError`
- **Schema-only**: Validated by MCP JSON schema (enum, type) but no runtime check
- **Unvalidated**: No validation - potential for invalid inputs

---

## Memory Tools (`memory.py`)

### store_memory

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `content` | str | Yes | Validated | Length check (max 10,000 chars) |
| `category` | str | Yes | Validated | Enum check against `VALID_CATEGORIES` |
| `importance` | float | No | Validated | Range check (0.0-1.0) |
| `tags` | list[str] | No | Validated | Uses `validate_tags()` - count and length limits |

### retrieve_memories

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `query` | str | Yes | **Partial** | Empty check only (returns empty results), no length validation |
| `limit` | int | No | Validated | Range check (1-100) |
| `category` | str | No | Validated | Enum check against `VALID_CATEGORIES` |
| `min_importance` | float | No | Validated | Uses `validate_importance_range()` |

### list_memories

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `category` | str | No | Validated | Enum check against `VALID_CATEGORIES` |
| `tags` | list[str] | No | Validated | Uses `validate_tags()` |
| `limit` | int | No | Validated | Range check (1-200) |
| `offset` | int | No | Validated | Non-negative check |

### delete_memory

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `memory_id` | str | Yes | Validated | Uses `validate_uuid()` |

---

## Code Tools (`code.py`)

### index_codebase

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `directory` | str | Yes | Validated | Path existence and directory check |
| `project` | str | Yes | Validated | Uses `validate_project_id()` |
| `recursive` | bool | No | Schema-only | Boolean - no runtime validation needed |

### search_code

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `query` | str | Yes | **Partial** | Empty check only (returns empty results), no length validation |
| `project` | str | No | **Unvalidated** | No format validation when provided |
| `language` | str | No | Validated | Uses `validate_language()` |
| `limit` | int | No | Validated | Range check (1-50) |

### find_similar_code

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `snippet` | str | Yes | Validated | Length check (max 5,000 chars), empty check |
| `project` | str | No | **Unvalidated** | No format validation when provided |
| `limit` | int | No | Validated | Range check (1-50) |

---

## Git Tools (`git.py`)

### index_commits

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `since` | str | No | Validated | ISO date format check |
| `limit` | int | No | **Partial** | Only checks `< 1`, no upper bound |
| `force` | bool | No | Schema-only | Boolean - no runtime validation needed |

### search_commits

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `query` | str | Yes | **Partial** | Empty check only (returns empty results), no length validation |
| `author` | str | No | **Unvalidated** | No validation on author string |
| `since` | str | No | Validated | ISO date format check |
| `limit` | int | No | Validated | Range check (1-50) |

### get_file_history

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `path` | str | Yes | **Partial** | Existence check via FileNotFoundError, no format validation |
| `limit` | int | No | Validated | Range check (1-500) |

### get_churn_hotspots

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `days` | int | No | Validated | Range check (1-365) |
| `limit` | int | No | Validated | Range check (1-50) |

### get_code_authors

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `path` | str | Yes | **Partial** | Existence check via FileNotFoundError, no format validation |

---

## GHAP Tools (`ghap.py`)

### start_ghap

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `domain` | str | Yes | Validated | Uses `validate_domain()` |
| `strategy` | str | Yes | Validated | Uses `validate_strategy()` |
| `goal` | str | Yes | Validated | Empty check, length check (max 1,000 chars) |
| `hypothesis` | str | Yes | Validated | Empty check, length check (max 1,000 chars) |
| `action` | str | Yes | Validated | Empty check, length check (max 1,000 chars) |
| `prediction` | str | Yes | Validated | Empty check, length check (max 1,000 chars) |

### update_ghap

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `hypothesis` | str | No | Validated | Length check (max 1,000 chars) |
| `action` | str | No | Validated | Length check (max 1,000 chars) |
| `prediction` | str | No | Validated | Length check (max 1,000 chars) |
| `strategy` | str | No | Validated | Uses `validate_strategy()` |
| `note` | str | No | Validated | Uses `validate_text_length()` (max 2,000 chars) |

### resolve_ghap

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `status` | str | Yes | Validated | Uses `validate_outcome_status()` |
| `result` | str | Yes | Validated | Length check (max 2,000 chars) |
| `surprise` | str | No | Validated | Length check (max 2,000 chars), required if status=falsified |
| `root_cause` | dict | No | Validated | Structure check, category uses `validate_root_cause_category()` |
| `lesson` | dict | No | Validated | Structure check, field length checks |

### get_active_ghap

No parameters - no validation needed.

### list_ghap_entries

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `limit` | int | No | Validated | Range check (1-100) |
| `domain` | str | No | Validated | Uses `validate_domain()` |
| `outcome` | str | No | Validated | Uses `validate_outcome_status()` |
| `since` | str | No | Validated | ISO 8601 date format check |

---

## Learning Tools (`learning.py`)

### get_clusters

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `axis` | str | Yes | Validated | Uses `validate_axis()` |

### get_cluster_members

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `cluster_id` | str | Yes | Validated | Format check (axis_label), axis validation |
| `limit` | int | No | Validated | Range check (1-100) |

### validate_value

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `text` | str | Yes | Validated | Empty check, length check (max 500 chars) |
| `cluster_id` | str | Yes | Validated | Format check (axis_label), axis validation |

### store_value

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `text` | str | Yes | Validated | Empty check, length check (max 500 chars) |
| `cluster_id` | str | Yes | Validated | Format check (axis_label) |
| `axis` | str | Yes | Validated | Uses `validate_axis()` |

### list_values

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `axis` | str | No | Validated | Uses `validate_axis()` |
| `limit` | int | No | Validated | Range check (1-100) |

---

## Search Tools (`search.py`)

### search_experiences

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `query` | str | Yes | **Partial** | Empty check only (returns empty results), no length validation |
| `axis` | str | No | Validated | Uses `validate_axis()` |
| `domain` | str | No | Validated | Uses `validate_domain()` |
| `outcome` | str | No | Validated | Uses `validate_outcome_status()` |
| `limit` | int | No | Validated | Range check (1-50) |

---

## Context Tools (`context.py`)

### assemble_context

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `query` | str | Yes | **Partial** | Empty check only (returns empty results), no length validation |
| `context_types` | list[str] | No | Validated | Uses `validate_context_types()` |
| `limit` | int | No | Validated | Uses `validate_limit_range()` (1-50) |
| `max_tokens` | int | No | Validated | Uses `validate_limit_range()` (100-10,000) |

---

## Session Tools (`session.py`)

### start_session

No parameters - no validation needed.

### get_orphaned_ghap

No parameters - no validation needed.

### should_check_in

| Parameter | Type | Required | Validation Status | Notes |
|-----------|------|----------|-------------------|-------|
| `frequency` | int | No | **Unvalidated** | No range check, could be negative |

### increment_tool_count

No parameters - no validation needed.

### reset_tool_count

No parameters - no validation needed.

---

## Ping Tool (`__init__.py`)

### ping

No parameters - no validation needed.

---

## Summary of Unvalidated/Partially Validated Parameters

### Unvalidated Parameters (need validation added)

1. **search_code.project** - Optional project filter has no format validation
2. **find_similar_code.project** - Optional project filter has no format validation
3. **search_commits.author** - No validation on author string
4. **should_check_in.frequency** - No range check, could be negative or zero

### Partially Validated Parameters (need length validation)

These parameters check for empty strings but have no length limits, which could cause issues with embedding models or storage:

1. **retrieve_memories.query** - No max length
2. **search_code.query** - No max length
3. **search_commits.query** - No max length
4. **search_experiences.query** - No max length
5. **assemble_context.query** - No max length
6. **index_commits.limit** - Only checks `< 1`, no upper bound

### Parameters with Incomplete Range Validation

1. **git.get_file_history.path** - Only validates existence, not empty string
2. **git.get_code_authors.path** - Only validates existence, not empty string

---

## Patterns Found for Reuse

The following validation patterns appear 2+ times and should have shared validators:

1. **Query string validation** - 5 tools have query parameters needing empty + length validation
2. **Project ID validation (optional)** - Already exists but not used consistently for optional params
3. **Positive integer with upper bound** - Common for limit parameters (already has `validate_limit_range`)
4. **File path validation** - 2 tools validate file paths

---

## Existing Validators in `validation.py`

- `validate_context_types()` - Context types array
- `validate_importance_range()` - Float 0.0-1.0
- `validate_tags()` - Tags array count/length
- `validate_uuid()` - UUID format
- `validate_language()` - Programming language
- `validate_project_id()` - Project identifier format
- `validate_limit_range()` - Integer range
- `validate_positive_int()` - Positive integer with optional max
- `validate_text_length()` - Text length with optional empty check

## Existing Validators in `enums.py`

- `validate_domain()` - Domain enum
- `validate_strategy()` - Strategy enum
- `validate_axis()` - Clustering axis enum
- `validate_outcome_status()` - Outcome status enum
- `validate_root_cause_category()` - Root cause category enum
