# MCP Tool Input Validation Audit

**Ticket**: R4-A (Audit Public Function Input Validation)
**Date**: 2024-12-14
**Status**: Complete

## Executive Summary

This document audits all MCP tool handler functions for input validation completeness.
Overall, the codebase has **good validation coverage** - most tools validate their inputs
with helpful error messages that list valid options. However, there are some gaps and
improvement opportunities identified below.

### Legend
- GOOD: Validation present with helpful error message
- PARTIAL: Some validation present but incomplete
- MISSING: No validation for this parameter
- N/A: Parameter doesn't require validation (e.g., optional booleans)

---

## 1. Memory Tools (`src/clams/server/tools/memory.py`)

### 1.1 `store_memory`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `content` | `str` | Max 10,000 chars | GOOD | Clear error message with limit |
| `category` | `str` | Against `VALID_CATEGORIES` | GOOD | Lists valid options in error |
| `importance` | `float` | Range 0.0-1.0 | GOOD | Clear range in error |
| `tags` | `list[str] \| None` | None | MISSING | No max count or tag length validation |

**Suggested Improvements**:
- Add validation for `tags`: max count (e.g., 20), max length per tag (e.g., 50 chars)
- Error message could clarify that empty strings are allowed in tags

### 1.2 `retrieve_memories`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `query` | `str` | Empty check (returns empty) | GOOD | Graceful handling |
| `limit` | `int` | Range 1-100 | GOOD | Clear range in error |
| `category` | `str \| None` | Against `VALID_CATEGORIES` | GOOD | Lists valid options |
| `min_importance` | `float` | None | MISSING | No range validation |

**Suggested Improvements**:
- Validate `min_importance` is in range 0.0-1.0

### 1.3 `list_memories`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `category` | `str \| None` | Against `VALID_CATEGORIES` | GOOD | Lists valid options |
| `tags` | `list[str] \| None` | None | MISSING | No validation |
| `limit` | `int` | Range 1-200 | GOOD | Clear range in error |
| `offset` | `int` | >= 0 | GOOD | Clear error message |

**Suggested Improvements**:
- Validate tags array similar to `store_memory`

### 1.4 `delete_memory`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `memory_id` | `str` | None | MISSING | No format validation |

**Suggested Improvements**:
- Validate `memory_id` is a valid UUID format
- Return clearer error if memory not found (currently returns `{deleted: false}`)

---

## 2. Code Tools (`src/clams/server/tools/code.py`)

### 2.1 `index_codebase`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `directory` | `str` | Path exists, is directory | GOOD | Clear error messages |
| `project` | `str` | None | MISSING | No format/length validation |
| `recursive` | `bool` | N/A | N/A | Boolean, no validation needed |

**Suggested Improvements**:
- Validate `project` identifier format (alphanumeric + dashes, max length)
- Validate `directory` is absolute path (helps prevent confusion)

### 2.2 `search_code`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `query` | `str` | Empty check (returns empty) | GOOD | Graceful handling |
| `project` | `str \| None` | None | MISSING | No validation |
| `language` | `str \| None` | None | MISSING | No validation against known languages |
| `limit` | `int` | Range 1-50 | GOOD | Clear range in error |

**Suggested Improvements**:
- Validate `language` against a list of supported languages
- Error message should list supported languages

### 2.3 `find_similar_code`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `snippet` | `str` | Max 5,000 chars, empty check | GOOD | Clear error messages |
| `project` | `str \| None` | None | MISSING | No validation |
| `limit` | `int` | Range 1-50 | GOOD | Clear range in error |

---

## 3. Git Tools (`src/clams/server/tools/git.py`)

### 3.1 `index_commits`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `since` | `str \| None` | ISO date format | GOOD | Suggests format in error |
| `limit` | `int \| None` | >= 1 | GOOD | Clear error |
| `force` | `bool` | N/A | N/A | Boolean |

### 3.2 `search_commits`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `query` | `str` | Empty check (returns empty) | GOOD | Graceful handling |
| `author` | `str \| None` | None | N/A | Free-form filter |
| `since` | `str \| None` | ISO date format | GOOD | Suggests format in error |
| `limit` | `int` | Range 1-50 | GOOD | Clear range in error |

### 3.3 `get_file_history`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `path` | `str` | File existence (from git) | GOOD | Converts to ValidationError |
| `limit` | `int` | Range 1-500 | GOOD | Clear range in error |

### 3.4 `get_churn_hotspots`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `days` | `int` | Range 1-365 | GOOD | Clear range in error |
| `limit` | `int` | Range 1-50 | GOOD | Clear range in error |

### 3.5 `get_code_authors`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `path` | `str` | File existence (from git) | GOOD | Converts to ValidationError |

---

## 4. GHAP Tools (`src/clams/server/tools/ghap.py`)

### 4.1 `start_ghap`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `domain` | `str` | Against `DOMAINS` | GOOD | Uses `validate_domain()` |
| `strategy` | `str` | Against `STRATEGIES` | GOOD | Uses `validate_strategy()` |
| `goal` | `str` | Non-empty, max 1000 chars | GOOD | Clear error messages |
| `hypothesis` | `str` | Non-empty, max 1000 chars | GOOD | Clear error messages |
| `action` | `str` | Non-empty, max 1000 chars | GOOD | Clear error messages |
| `prediction` | `str` | Non-empty, max 1000 chars | GOOD | Clear error messages |

**Additional Logic**: Checks for existing active GHAP and returns specific error type
`active_ghap_exists` with actionable guidance. This addresses BUG-029.

### 4.2 `update_ghap`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `hypothesis` | `str \| None` | Max 1000 chars | GOOD | Clear error |
| `action` | `str \| None` | Max 1000 chars | GOOD | Clear error |
| `prediction` | `str \| None` | Max 1000 chars | GOOD | Clear error |
| `strategy` | `str \| None` | Against `STRATEGIES` | GOOD | Uses `validate_strategy()` |
| `note` | `str \| None` | None | MISSING | No length validation |

**Additional Logic**: Returns `not_found` error with guidance if no active GHAP.

**Suggested Improvements**:
- Add max length validation for `note` parameter

### 4.3 `resolve_ghap`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `status` | `str` | Against `OUTCOME_STATUS_VALUES` | GOOD | Lists valid options |
| `result` | `str` | Max 2000 chars | GOOD | Clear error |
| `surprise` | `str \| None` | Max 2000 chars, required if falsified | GOOD | Conditional validation |
| `root_cause` | `dict \| None` | Structure + category validation | GOOD | Validates nested fields |
| `lesson` | `dict \| None` | Structure validation | GOOD | Validates nested fields |

**Excellent validation** - validates conditional requirements (surprise/root_cause
required when status is "falsified") and nested object structures.

### 4.4 `get_active_ghap`

No parameters - no validation needed.

### 4.5 `list_ghap_entries`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `limit` | `int` | Range 1-100 | GOOD | Clear range in error |
| `domain` | `str \| None` | Against `DOMAINS` | GOOD | Uses `validate_domain()` |
| `outcome` | `str \| None` | Against `OUTCOME_STATUS_VALUES` | GOOD | Lists valid options |
| `since` | `str \| None` | ISO 8601 format | GOOD | Provides format example |

---

## 5. Learning Tools (`src/clams/server/tools/learning.py`)

### 5.1 `get_clusters`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `axis` | `str` | Against `VALID_AXES` | GOOD | Uses `validate_axis()` |

**Additional Logic**: Returns `insufficient_data` error if < 20 experiences exist.

### 5.2 `get_cluster_members`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `cluster_id` | `str` | Format validation + axis extraction | GOOD | Explains expected format |
| `limit` | `int` | Range 1-100 | GOOD | Clear range in error |

### 5.3 `validate_value`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `text` | `str` | Non-empty, max 500 chars | GOOD | Clear error messages |
| `cluster_id` | `str` | Format validation + axis extraction | GOOD | Explains expected format |

### 5.4 `store_value`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `text` | `str` | Non-empty, max 500 chars | GOOD | Clear error messages |
| `cluster_id` | `str` | Format validation | GOOD | Explains expected format |
| `axis` | `str` | Against `VALID_AXES` | GOOD | Uses `validate_axis()` |

### 5.5 `list_values`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `axis` | `str \| None` | Against `VALID_AXES` | GOOD | Uses `validate_axis()` |
| `limit` | `int` | Range 1-100 | GOOD | Clear range in error |

---

## 6. Search Tools (`src/clams/server/tools/search.py`)

### 6.1 `search_experiences`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `query` | `str` | Empty check (returns empty) | GOOD | Graceful handling |
| `axis` | `str` | Against `VALID_AXES` | GOOD | Uses `validate_axis()` |
| `domain` | `str \| None` | Against `DOMAINS` | GOOD | Uses `validate_domain()` |
| `outcome` | `str \| None` | Against `OUTCOME_STATUS_VALUES` | GOOD | Lists valid options |
| `limit` | `int` | Range 1-50 | GOOD | Clear range in error |

---

## 7. Context Tools (`src/clams/server/tools/context.py`)

### 7.1 `assemble_context`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `query` | `str` | None | MISSING | No empty check |
| `context_types` | `list[str] \| None` | None | **MISSING** | **BUG-036 risk** |
| `limit` | `int` | None | MISSING | No range validation |
| `max_tokens` | `int` | None | MISSING | No range validation |

**Critical Finding**: This function lacks validation for `context_types`. While it
defaults to `["values", "experiences"]`, if the user passes an invalid type like
`["invalid"]`, it will silently skip that type without error. This is inconsistent
with the `distribute_budget()` function which DOES validate context types.

**Suggested Improvements**:
- Validate `context_types` against known types ("values", "experiences")
- Add limit range validation (1-50)
- Add max_tokens validation (reasonable min/max, e.g., 100-10000)
- Add empty query handling (return empty result or error)

---

## 8. Token Management (`src/clams/context/tokens.py`)

### 8.1 `distribute_budget`

| Parameter | Type | Validation | Status | Notes |
|-----------|------|------------|--------|-------|
| `context_types` | `list[str]` | Against `SOURCE_WEIGHTS` keys | GOOD | **Fixed after BUG-036** |
| `max_tokens` | `int` | None | MISSING | No validation |

The `distribute_budget()` function was fixed in BUG-036 to validate context types:
```python
invalid = [t for t in context_types if t not in SOURCE_WEIGHTS]
if invalid:
    raise ValueError(
        f"Invalid context types: {invalid}. Valid: {list(SOURCE_WEIGHTS.keys())}"
    )
```

**Suggested Improvements**:
- Add `max_tokens` validation (must be positive, reasonable upper bound)
- The error message could be more specific about what `SOURCE_WEIGHTS` contains

---

## Priority Rankings

### Highest Priority (Most User-Facing)

1. **`assemble_context`** - Called on every user prompt, missing validation
2. **`search_experiences`** - Primary search interface, but validation is good
3. **`store_memory`** / `retrieve_memories` - Frequently used, missing tags validation
4. **`start_ghap`** - Entry point for all GHAP tracking, but validation is excellent

### Medium Priority

5. **`search_code`** - Missing language validation
6. **`index_codebase`** - Missing project format validation
7. **`update_ghap`** - Missing note length validation
8. **`delete_memory`** - Missing UUID format validation

### Lower Priority (Less User-Facing)

9. **`find_similar_code`** - Project validation
10. **Internal functions** - Already well-validated through enums

---

## Error Messages to Improve

### Generic "internal_error" Messages

Several tools catch all unexpected exceptions and return generic `"internal_error"`:
- All GHAP tools
- All learning tools
- Search tools
- Context tools

While this is good for security (not leaking stack traces), consider:
1. Logging the actual error for debugging
2. Including a reference ID in the error response for support

### Error Messages Missing Valid Options

The following should list valid options but don't:

1. **`search_code` language parameter** - Should list supported languages
2. **`assemble_context` context_types** - Should validate and list options

### Error Messages Lacking Context

1. **`delete_memory`** - Returns `{deleted: false}` without explanation
2. **Collection not found errors** - Good that they return empty results gracefully

---

## Validation Patterns in Use

### Good Patterns

1. **Centralized enum validation** (`enums.py`):
   - `validate_domain()`, `validate_strategy()`, `validate_axis()`, etc.
   - All raise `ValidationError` with valid options listed

2. **Range validation with clear messages**:
   ```python
   if not 1 <= limit <= 50:
       raise ValidationError(f"Limit {limit} out of range. Must be between 1 and 50.")
   ```

3. **Conditional validation** (`resolve_ghap`):
   - Validates `surprise` and `root_cause` are required when `status == "falsified"`

4. **Nested object validation** (`resolve_ghap`):
   - Validates `root_cause.category`, `root_cause.description`, `lesson.what_worked`

### Patterns to Adopt More Widely

1. **Validate string format patterns** (UUID, identifiers)
2. **Validate array contents** (tags, context_types)
3. **Consistent error typing** (use `ValidationError` everywhere, not mix of `ValueError`)

---

## Recommendations

### Immediate Actions (R4-B, R4-C)

1. **Add validation to `assemble_context`** for context_types parameter
2. **Review GHAP error messages** - ensure no generic "internal_error" for known conditions

### Follow-up Tasks (R4-E)

1. Add tags validation to memory tools
2. Add language validation to code tools
3. Add UUID format validation to delete operations
4. Add max_tokens validation to budget distribution
5. Create unified validation test suite

---

## Appendix: Validation Functions Location

| Function | File | Parameters Validated |
|----------|------|---------------------|
| `validate_domain` | `enums.py` | domain |
| `validate_strategy` | `enums.py` | strategy |
| `validate_axis` | `enums.py` | axis |
| `validate_outcome_status` | `enums.py` | status |
| `validate_root_cause_category` | `enums.py` | category |
| `VALID_CATEGORIES` | `memory.py` | category (local) |
| `SOURCE_WEIGHTS` | `tokens.py` | context_types |
