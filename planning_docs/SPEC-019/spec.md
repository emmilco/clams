# SPEC-019: Input Validation Test Suite for MCP Tools

## Overview

This specification defines a comprehensive test suite for validating MCP tool inputs. Multiple bugs (BUG-019, BUG-020, BUG-024, etc.) have been caused by missing or inconsistent input validation. This test suite ensures all tool inputs are properly validated with appropriate error messages.

## Background

### Problem Statement

The MCP tools in CLAMS accept various inputs with constraints (required fields, types, enums, ranges). When these constraints are violated, the behavior is inconsistent:

1. Some tools raise `ValidationError` with clear messages
2. Some tools return `{"error": {"type": "validation_error", ...}}` responses
3. Some tools return generic `internal_error` responses for validation failures
4. Some edge cases are not validated at all

This inconsistency leads to:
- Difficult debugging for API consumers
- Bugs that pass unit tests but fail in production (BUG-024: error message mismatch)
- Regressions when code changes (BUG-019, BUG-020)

### Solution

A systematic test suite that:
1. Tests every input parameter of every tool
2. Covers all validation categories (missing required, wrong type, invalid enum, out of range)
3. Verifies error messages are informative and consistent
4. Documents expected behavior as executable tests

## Tool Inventory

The following tools require input validation testing:

### Memory Tools (4 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `store_memory` | content, category | importance (0.0-1.0), tags |
| `retrieve_memories` | query | limit (1-100), category, min_importance (0.0-1.0) |
| `list_memories` | (none) | category, tags, limit (1-200), offset (>=0) |
| `delete_memory` | memory_id | (none) |

### Code Tools (3 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `index_codebase` | directory, project | recursive |
| `search_code` | query | project, language, limit (1-50) |
| `find_similar_code` | snippet | project, limit (1-50) |

### Git Tools (5 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `index_commits` | (none) | since (ISO date), limit (>=1), force |
| `search_commits` | query | author, since (ISO date), limit (1-50) |
| `get_file_history` | path | limit (1-500) |
| `get_churn_hotspots` | (none) | days (1-365), limit (1-50) |
| `get_code_authors` | path | (none) |

### GHAP Tools (5 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `start_ghap` | domain, strategy, goal, hypothesis, action, prediction | (none) |
| `update_ghap` | (none) | hypothesis, action, prediction, strategy, note (max 1000 chars each) |
| `resolve_ghap` | status, result | surprise, root_cause, lesson |
| `get_active_ghap` | (none) | (none) |
| `list_ghap_entries` | (none) | limit (1-100), domain, outcome, since (ISO date) |

### Learning Tools (5 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `get_clusters` | axis | (none) |
| `get_cluster_members` | cluster_id | limit (1-100) |
| `validate_value` | text, cluster_id | (none) |
| `store_value` | text, cluster_id, axis | (none) |
| `list_values` | (none) | axis, limit (1-100) |

### Search Tools (1 tool)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `search_experiences` | query | axis, domain, outcome, limit (1-50) |

### Session Tools (5 tools)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `start_session` | (none) | (none) |
| `get_orphaned_ghap` | (none) | (none) |
| `should_check_in` | (none) | frequency |
| `increment_tool_count` | (none) | (none) |
| `reset_tool_count` | (none) | (none) |

### Context Tools (1 tool)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `assemble_context` | query | context_types, limit, max_tokens |

### Utility Tools (1 tool)
| Tool | Required Fields | Optional Fields with Constraints |
|------|-----------------|----------------------------------|
| `ping` | (none) | (none) |

## Test Categories

### Category 1: Missing Required Fields

For each tool with required fields, test that calling without each required field results in:
- Either a `ValidationError` exception being raised
- Or an error response: `{"error": {"type": "validation_error", "message": "..."}}`

The error message MUST identify the missing field by name.

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_missing_{field}(fixtures):
    """Test that {tool} rejects calls missing required field '{field}'."""
    # Call tool without the required field
    # Assert ValidationError or error response
    # Assert field name appears in error message
```

### Category 2: Wrong Type

For each field with a specific type requirement, test that passing the wrong type results in a validation error.

**Type constraints by field:**

| Field Type | Example Fields | Invalid Inputs to Test |
|------------|----------------|------------------------|
| string | query, content, text | None, 123, [], {} |
| integer | limit, days, offset | "10", 10.5, None |
| float | importance, min_importance | "0.5", None |
| boolean | recursive, force | "true", 1, None |
| array[string] | tags, context_types | "tag", {"tag": 1} |
| object | root_cause, lesson | "string", [] |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_{field}_wrong_type(fixtures):
    """Test that {tool} rejects {field} with wrong type."""
    # Call tool with wrong type for field
    # Assert ValidationError or error response
    # Assert error message mentions type issue
```

### Category 3: Invalid Enum Values

For each field with enum constraints, test that passing an invalid value results in a validation error listing valid options.

**Enum fields:**

| Field | Valid Values |
|-------|-------------|
| category (memory) | preference, fact, event, workflow, context, error, decision |
| domain | debugging, refactoring, feature, testing, configuration, documentation, performance, security, integration |
| strategy | systematic-elimination, trial-and-error, research-first, divide-and-conquer, root-cause-analysis, copy-from-similar, check-assumptions, read-the-error, ask-user |
| status (resolve_ghap) | confirmed, falsified, abandoned |
| outcome | confirmed, falsified, abandoned |
| axis | full, strategy, surprise, root_cause |
| root_cause.category | wrong-assumption, missing-knowledge, oversight, environment-issue, misleading-symptom, incomplete-fix, wrong-scope, test-isolation, timing-issue |
| context_types items | values, experiences |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_invalid_{field}(fixtures):
    """Test that {tool} rejects invalid enum value for '{field}'."""
    # Call tool with invalid enum value
    # Assert ValidationError or error response
    # Assert error message lists valid options
```

### Category 4: Out of Range Values

For each field with numeric range constraints, test boundary conditions.

**Range constraints:**

| Field | Tool(s) | Valid Range | Test Values |
|-------|---------|-------------|-------------|
| importance | store_memory | 0.0-1.0 | -0.1, 1.1, 2.0 |
| min_importance | retrieve_memories | 0.0-1.0 | -0.1, 1.1 |
| limit | retrieve_memories | 1-100 | 0, 101, -1 |
| limit | list_memories | 1-200 | 0, 201, -1 |
| limit | search_code, find_similar_code | 1-50 | 0, 51, -1 |
| limit | get_file_history | 1-500 | 0, 501, -1 |
| limit | search_commits | 1-50 | 0, 51, -1 |
| limit | list_ghap_entries | 1-100 | 0, 101, -1 |
| limit | get_cluster_members, list_values | 1-100 | 0, 101, -1 |
| limit | search_experiences | 1-50 | 0, 51, -1 |
| days | get_churn_hotspots | 1-365 | 0, 366, -1 |
| offset | list_memories | >=0 | -1, -100 |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_{field}_out_of_range_{bound}(fixtures):
    """Test that {tool} rejects {field}={value} (out of range)."""
    # Call tool with out-of-range value
    # Assert ValidationError or error response
    # Assert error message mentions range
```

### Category 5: String Length Limits

For each field with max length constraints, test boundary conditions.

**Length constraints:**

| Field | Tool(s) | Max Length |
|-------|---------|------------|
| content | store_memory | 10,000 chars |
| snippet | find_similar_code | 5,000 chars |
| text | validate_value, store_value | 500 chars |
| goal, hypothesis, action, prediction | start_ghap, update_ghap | 1,000 chars |
| result | resolve_ghap | 2,000 chars |
| surprise | resolve_ghap | 2,000 chars |
| root_cause.description | resolve_ghap | 2,000 chars |
| lesson.what_worked | resolve_ghap | 2,000 chars |
| lesson.takeaway | resolve_ghap | 2,000 chars |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_{field}_too_long(fixtures):
    """Test that {tool} rejects {field} exceeding max length."""
    # Call tool with string exceeding max length
    # Assert ValidationError or error response
    # Assert error message mentions length limit
```

### Category 6: Format Validation

For fields with specific format requirements:

**Format constraints:**

| Field | Format | Tools |
|-------|--------|-------|
| since | ISO 8601 date (YYYY-MM-DD) | index_commits, search_commits, list_ghap_entries |
| cluster_id | "{axis}_{label}" format | get_cluster_members, validate_value, store_value |
| directory | Valid file system path | index_codebase |
| path | File path in repository | get_file_history, get_code_authors |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_{field}_invalid_format(fixtures):
    """Test that {tool} rejects {field} with invalid format."""
    # Call tool with malformed value
    # Assert ValidationError or error response
    # Assert error message describes expected format
```

### Category 7: Conditional Requirements

Some fields are required only under certain conditions:

| Tool | Condition | Required Field |
|------|-----------|----------------|
| resolve_ghap | status == "falsified" | surprise |
| resolve_ghap | status == "falsified" | root_cause |
| resolve_ghap | lesson provided | lesson.what_worked |
| resolve_ghap | root_cause provided | root_cause.category |
| resolve_ghap | root_cause provided | root_cause.description |

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_conditional_{field}_required(fixtures):
    """Test that {tool} requires {field} when condition is met."""
    # Call tool meeting condition but missing field
    # Assert ValidationError or error response
```

### Category 8: Empty/Whitespace Strings

For required string fields, test that empty or whitespace-only values are rejected:

**Fields to test:**
- query (all search tools)
- content (store_memory)
- goal, hypothesis, action, prediction (start_ghap)
- text (validate_value, store_value)
- result (resolve_ghap)

**Test format:**
```python
@pytest.mark.asyncio
async def test_{tool}_{field}_empty(fixtures):
    """Test that {tool} rejects empty {field}."""
    # Call tool with empty string ""
    # Assert ValidationError or error response

@pytest.mark.asyncio
async def test_{tool}_{field}_whitespace(fixtures):
    """Test that {tool} rejects whitespace-only {field}."""
    # Call tool with "   "
    # Assert ValidationError or error response
```

## Error Message Requirements

All validation error messages MUST:

1. **Identify the problematic field**: Include the field name
2. **Describe the constraint**: Explain what is valid
3. **Show the invalid value**: When practical, show what was provided
4. **List valid options**: For enums, list all valid values

**Good examples:**
```
"Invalid category 'invalid'. Must be one of: context, decision, error, event, fact, preference, workflow"
"Limit 0 out of range. Must be between 1 and 100."
"Content too long (15000 chars). Maximum allowed is 10000 characters."
"Field 'goal' cannot be empty"
"Invalid cluster_id format: 'bad'. Expected format: 'axis_label' (e.g., 'full_0', 'strategy_2')"
```

**Bad examples:**
```
"Invalid input"
"Bad request"
"Validation failed"
"Internal server error"  # Should be validation_error, not internal_error
```

## Test File Organization

```
tests/server/tools/
    test_input_validation/
        __init__.py
        conftest.py                  # Shared fixtures
        test_memory_validation.py    # Memory tools
        test_code_validation.py      # Code tools
        test_git_validation.py       # Git tools
        test_ghap_validation.py      # GHAP tools
        test_learning_validation.py  # Learning tools
        test_search_validation.py    # Search tools
        test_session_validation.py   # Session tools
        test_context_validation.py   # Context tools
```

## Coverage Requirements

### Minimum Coverage Per Tool

Each tool with validation requirements MUST have:
- At least one test per required field (testing missing)
- At least one test per enum field (testing invalid value)
- At least one test per range-constrained field (testing out of range)
- At least one test per format-constrained field (testing invalid format)

### Coverage Metrics

The test suite MUST achieve:
- 100% of tools with required fields have "missing required" tests
- 100% of enum fields have "invalid enum" tests
- 100% of range-constrained fields have "out of range" tests
- 100% of format-constrained fields have "invalid format" tests

## Acceptance Criteria

1. **Comprehensive test file structure created**
   - All test files exist per the organization above
   - conftest.py provides mock fixtures matching existing test patterns

2. **All validation categories covered**
   - Tests exist for each category defined above
   - Each tool with constraints has corresponding validation tests

3. **Error message assertions**
   - Tests verify error message content, not just error type
   - Tests confirm field names appear in error messages

4. **Existing test patterns followed**
   - Tests use pytest.mark.asyncio
   - Tests use existing mock fixtures (mock_services, mock_search_result)
   - Tests follow naming conventions from existing test files

5. **All tests pass**
   - `pytest tests/server/tools/test_input_validation/ -v` passes
   - No skipped tests

6. **No regressions**
   - Full test suite still passes: `pytest -v`
   - Type checking passes: `mypy --strict src/clams/server/tools/`
   - Linting passes: `ruff check src/clams/server/tools/`

7. **Documentation**
   - Test docstrings explain what each test validates
   - Comments reference relevant bug IDs where applicable (BUG-019, BUG-020, BUG-024)

## Implementation Notes

### Existing Validation Infrastructure

The codebase already has:
- `ValidationError` class in `src/clams/server/tools/errors.py`
- Enum validators in `src/clams/server/tools/enums.py`:
  - `validate_domain()`
  - `validate_strategy()`
  - `validate_axis()`
  - `validate_outcome_status()`
  - `validate_root_cause_category()`

### Current Test Patterns

Refer to existing tests for patterns:
- `tests/server/tools/test_memory.py` - Shows validation test examples
- `tests/server/tools/test_learning.py` - Shows mock setup
- `tests/server/tools/conftest.py` - Provides mock_services fixture

### Bug References

This spec addresses issues from:
- **BUG-019**: validate_value returns internal server error
- **BUG-020**: store_value returns internal server error
- **BUG-024**: Error message mismatch between stores

## Out of Scope

The following are NOT covered by this spec:
- Business logic validation (e.g., "cluster has no members")
- Authentication/authorization
- Rate limiting
- Performance testing
- Integration testing with real services
