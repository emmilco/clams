# SPEC-057: Technical Proposal

## Problem Statement

The CLAMS MCP server has 27 tools with various parameters. A thorough audit identified that most tools are already well-validated, but several gaps remain:

1. **4 unvalidated parameters** that accept any input without checking
2. **6 partially validated parameters** (query strings) that check for empty but have no length limits
3. **Inconsistent project ID validation** - `validate_project_id()` exists but isn't used for optional project filters

These gaps create inconsistent error handling and potential runtime issues (e.g., extremely long queries could cause embedding model failures or excessive memory usage).

## Audit Findings Summary

### Unvalidated Parameters

| Tool | Parameter | Issue |
|------|-----------|-------|
| `search_code` | `project` | No format validation when provided |
| `find_similar_code` | `project` | No format validation when provided |
| `search_commits` | `author` | No validation on author string |
| `should_check_in` | `frequency` | No range check, could be negative |

### Partially Validated Parameters (Missing Length Check)

| Tool | Parameter | Current | Needed |
|------|-----------|---------|--------|
| `retrieve_memories` | `query` | Empty check | Max length |
| `search_code` | `query` | Empty check | Max length |
| `search_commits` | `query` | Empty check | Max length |
| `search_experiences` | `query` | Empty check | Max length |
| `assemble_context` | `query` | Empty check | Max length |
| `index_commits` | `limit` | Min check (>= 1) | Max check |

### Path Parameters (No Change Needed)

| Tool | Parameter | Current | Decision |
|------|-----------|---------|----------|
| `get_file_history` | `path` | FileNotFoundError | Sufficient |
| `get_code_authors` | `path` | FileNotFoundError | Sufficient |

The path parameters rely on downstream `FileNotFoundError` which is appropriate - we don't need to add redundant empty checks since the file system will reject empty paths.

## Proposed New Validators

Add to `src/clams/server/tools/validation.py`:

### 1. `validate_query_string()`

For search queries across all tools. Validates:
- Not empty or whitespace-only
- Maximum length (10,000 chars - sufficient for any reasonable query)

```python
def validate_query_string(
    query: str,
    max_length: int = 10_000,
    param_name: str = "query",
) -> None:
    """Validate search query string.

    Args:
        query: Query string to validate
        max_length: Maximum allowed length (default 10,000)
        param_name: Parameter name for error message

    Raises:
        ValidationError: If query is empty or exceeds max length
    """
    if not query or not query.strip():
        raise ValidationError(f"{param_name.capitalize()} cannot be empty")

    if len(query) > max_length:
        raise ValidationError(
            f"{param_name.capitalize()} too long ({len(query)} chars). "
            f"Maximum: {max_length} characters"
        )
```

**Usage**: retrieve_memories, search_code, search_commits, search_experiences, assemble_context

### 2. `validate_optional_project_id()`

Wrapper around existing `validate_project_id()` for optional params:

```python
def validate_optional_project_id(project: str | None) -> None:
    """Validate optional project identifier.

    Args:
        project: Project identifier or None

    Raises:
        ValidationError: If project is provided but invalid
    """
    if project is not None:
        validate_project_id(project)
```

**Usage**: search_code, find_similar_code

### 3. `validate_frequency()`

For the session check-in frequency:

```python
def validate_frequency(
    frequency: int,
    min_val: int = 1,
    max_val: int = 1000,
    param_name: str = "frequency",
) -> None:
    """Validate frequency/interval value.

    Args:
        frequency: Frequency value to validate
        min_val: Minimum allowed value (default 1)
        max_val: Maximum allowed value (default 1000)
        param_name: Parameter name for error message

    Raises:
        ValidationError: If frequency is out of range
    """
    if not min_val <= frequency <= max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {frequency} out of range. "
            f"Must be between {min_val} and {max_val}."
        )
```

**Usage**: should_check_in

### 4. `validate_author_name()`

For git author filtering:

```python
def validate_author_name(author: str | None, max_length: int = 200) -> None:
    """Validate optional author name filter.

    Args:
        author: Author name or None
        max_length: Maximum allowed length

    Raises:
        ValidationError: If author is provided but invalid
    """
    if author is None:
        return

    if len(author) > max_length:
        raise ValidationError(
            f"Author name too long ({len(author)} chars). "
            f"Maximum: {max_length} characters"
        )
```

**Usage**: search_commits

## Implementation Plan

### Phase 1: Add New Validators to `validation.py`

1. Add `validate_query_string()`
2. Add `validate_optional_project_id()`
3. Add `validate_frequency()`
4. Add `validate_author_name()`

### Phase 2: Apply Validators to Tools

**memory.py**:
- `retrieve_memories`: Replace empty check with `validate_query_string(query)`

**code.py**:
- `search_code`: Replace empty check with `validate_query_string(query)`, add `validate_optional_project_id(project)`
- `find_similar_code`: Add `validate_optional_project_id(project)`

**git.py**:
- `index_commits`: Add upper bound check to limit (max 100,000)
- `search_commits`: Replace empty check with `validate_query_string(query)`, add `validate_author_name(author)`

**search.py**:
- `search_experiences`: Replace empty check with `validate_query_string(query)`

**context.py**:
- `assemble_context`: Replace empty check with `validate_query_string(query)`

**session.py**:
- `should_check_in`: Add `validate_frequency(frequency)`

### Phase 3: Add Tests

1. **Unit tests for new validators** in `tests/unit/server/tools/test_validation.py`:
   - Test valid inputs
   - Test boundary conditions
   - Test invalid inputs with expected error messages

2. **Integration tests** in `tests/integration/test_tool_validation.py`:
   - Test that tools return proper ValidationError for invalid params
   - Test that error messages follow the pattern

## Files to Modify

1. `src/clams/server/tools/validation.py` - Add 4 new validators
2. `src/clams/server/tools/memory.py` - Update retrieve_memories query validation
3. `src/clams/server/tools/code.py` - Add query and optional project validation
4. `src/clams/server/tools/git.py` - Add query, author, and limit max validation
5. `src/clams/server/tools/search.py` - Update search_experiences query validation
6. `src/clams/server/tools/context.py` - Update assemble_context query validation
7. `src/clams/server/tools/session.py` - Add frequency validation
8. `tests/unit/server/tools/test_validation.py` - Add unit tests for new validators
9. `tests/integration/test_tool_validation.py` - Add integration tests

## Backwards Compatibility

All changes are additive - they add validation to previously unvalidated parameters. This could technically be a "breaking change" if anyone was relying on being able to pass invalid values, but:

1. Invalid values would have caused downstream errors anyway
2. The new validation provides clearer, earlier error messages
3. The spec explicitly says "No breaking changes to valid API calls"

Valid API calls will continue to work identically. Only invalid calls will now get proper validation errors instead of downstream failures.

## Error Message Format

Per spec, all error messages follow the pattern:
```
"{param} must be {expected}, got: {actual}"
```

Or for range/length errors (existing pattern):
```
"{Param} {value} out of range. Must be between {min} and {max}."
"{Param} too long ({len} chars). Maximum: {max} characters"
```

## Testing Strategy

### Unit Tests for Validators (`tests/unit/server/tools/test_validation.py`)

```python
class TestValidateQueryString:
    def test_valid_query(self):
        validate_query_string("test query")

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_query_string("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_query_string("   ")

    def test_too_long_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_query_string("x" * 10001)

    def test_at_max_length_accepted(self):
        validate_query_string("x" * 10000)


class TestValidateOptionalProjectId:
    def test_none_allowed(self):
        validate_optional_project_id(None)

    def test_valid_project(self):
        validate_optional_project_id("my-project")

    def test_invalid_project_raises(self):
        with pytest.raises(ValidationError, match="Invalid project"):
            validate_optional_project_id("has spaces")


class TestValidateFrequency:
    def test_valid_frequency(self):
        validate_frequency(10)

    def test_negative_raises(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_frequency(-1)

    def test_zero_raises(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_frequency(0)

    def test_too_large_raises(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_frequency(1001)


class TestValidateAuthorName:
    def test_none_allowed(self):
        validate_author_name(None)

    def test_valid_author(self):
        validate_author_name("John Doe")

    def test_too_long_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_author_name("x" * 201)
```

### Integration Tests (`tests/integration/test_tool_validation.py`)

```python
class TestQueryValidation:
    """Test query validation across tools."""

    @pytest.mark.asyncio
    async def test_search_code_empty_query_error(self, code_tools):
        with pytest.raises(ValidationError, match="cannot be empty"):
            await code_tools["search_code"](query="")

    @pytest.mark.asyncio
    async def test_retrieve_memories_query_too_long(self, memory_tools):
        with pytest.raises(ValidationError, match="too long"):
            await memory_tools["retrieve_memories"](query="x" * 10001)


class TestProjectValidation:
    """Test optional project validation."""

    @pytest.mark.asyncio
    async def test_search_code_invalid_project(self, code_tools):
        with pytest.raises(ValidationError, match="Invalid project"):
            await code_tools["search_code"](query="test", project="has spaces")


class TestFrequencyValidation:
    """Test frequency validation in session tools."""

    @pytest.mark.asyncio
    async def test_should_check_in_negative_frequency(self, session_tools):
        with pytest.raises(ValidationError, match="out of range"):
            await session_tools["should_check_in"](frequency=-1)
```

## Existing Validation Infrastructure

The codebase already has excellent validation infrastructure:

**In `validation.py`:**
- `validate_context_types()` - Context types array
- `validate_importance_range()` - Float 0.0-1.0
- `validate_tags()` - Tags array count/length
- `validate_uuid()` - UUID format
- `validate_language()` - Programming language
- `validate_project_id()` - Project identifier format (required)
- `validate_limit_range()` - Integer range
- `validate_positive_int()` - Positive integer with optional max
- `validate_text_length()` - Text length with optional empty check

**In `enums.py`:**
- `validate_domain()` - Domain enum
- `validate_strategy()` - Strategy enum
- `validate_axis()` - Clustering axis enum
- `validate_outcome_status()` - Outcome status enum
- `validate_root_cause_category()` - Root cause category enum

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Query length limit too restrictive | 10,000 chars is generous; most queries are < 500 chars |
| Frequency limit too restrictive | 1-1000 range covers all reasonable use cases |
| Missing edge cases | Comprehensive test coverage with boundary testing |

## Acceptance Criteria Mapping

| Spec Criterion | Implementation |
|----------------|----------------|
| Audit document created | `planning_docs/SPEC-057/audit.md` |
| All parameters validated | This proposal covers all gaps |
| Reusable validators added | 4 new validators in `validation.py` |
| Uses ValidationError | All validators raise ValidationError |
| Error message pattern | Follows "{param} must be {expected}, got: {actual}" |
| Unit tests | Test file for each new validator |
| Integration tests | Test file for tool validation |
| Existing tests pass | No changes to existing behavior |
| No breaking changes | Only adds validation to previously unvalidated params |

## Decision Point for Human Review

The audit found that **query string validation** is the most impactful change, affecting 5 tools. The current behavior for empty queries is to return empty results gracefully. Two options:

1. **Keep current behavior** (empty returns empty) - Add only length validation
2. **Strict validation** - Raise ValidationError on empty query

Recommendation: Option 1 (keep graceful empty handling, add length check only). This preserves backwards compatibility while preventing the real risk (excessively long queries).
