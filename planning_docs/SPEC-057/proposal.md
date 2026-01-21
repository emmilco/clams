# Technical Proposal: SPEC-057 - Add Validation to Remaining MCP Tool Parameters

## Problem Statement

The R4-A validation audit identified specific gaps in MCP tool parameter validation. While most tools have excellent validation (GHAP tools, most memory tools, git tools, learning tools, search tools), the following gaps could lead to cryptic errors, silent failures, or inconsistent user experience:

1. **Critical**: `assemble_context` has no validation for any parameter - silently ignores invalid context types (BUG-036 risk)
2. `retrieve_memories` missing `min_importance` range validation
3. `store_memory`/`list_memories` missing tags array validation (count and length)
4. `delete_memory` missing UUID format validation
5. `search_code` missing language validation
6. `index_codebase` missing project identifier format validation
7. `update_ghap` missing note length validation
8. `distribute_budget` missing max_tokens validation

## Proposed Solution

Add validation helpers to `src/clams/server/tools/validation.py` (new file) and integrate them into the affected tool handlers. This approach:

- Centralizes reusable validation logic
- Follows existing patterns from `enums.py`
- Maintains consistent error message format
- Enables comprehensive testing

## File-by-File Changes

### 1. New File: `src/clams/server/tools/validation.py`

Create a new validation module with reusable helper functions:

```python
"""Validation helpers for MCP tool parameters.

This module provides reusable validation functions that follow the
established patterns from enums.py - raising ValidationError with
descriptive messages that include valid options/ranges.
"""

import re
import uuid as uuid_lib
from typing import Sequence

from clams.server.tools.errors import ValidationError

# Valid context types for assemble_context
VALID_CONTEXT_TYPES = ["values", "experiences"]

# Supported languages for code search (lowercase)
SUPPORTED_LANGUAGES = [
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "java",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
]

# Project identifier pattern: alphanumeric, dashes, underscores
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
PROJECT_ID_MAX_LENGTH = 100


def validate_context_types(context_types: list[str]) -> None:
    """Validate context types for assemble_context.

    Args:
        context_types: List of context type strings

    Raises:
        ValidationError: If any context type is invalid
    """
    invalid = [t for t in context_types if t not in VALID_CONTEXT_TYPES]
    if invalid:
        raise ValidationError(
            f"Invalid context types: {invalid}. "
            f"Valid options: {', '.join(VALID_CONTEXT_TYPES)}"
        )


def validate_importance_range(importance: float, param_name: str = "importance") -> None:
    """Validate importance value is in range 0.0-1.0.

    Args:
        importance: Importance value to validate
        param_name: Parameter name for error message

    Raises:
        ValidationError: If importance is out of range
    """
    if not 0.0 <= importance <= 1.0:
        raise ValidationError(
            f"{param_name.capitalize()} {importance} out of range. "
            f"Must be between 0.0 and 1.0."
        )


def validate_tags(
    tags: Sequence[str] | None,
    max_count: int = 20,
    max_length: int = 50,
) -> None:
    """Validate tags array.

    Args:
        tags: List of tag strings (or None)
        max_count: Maximum number of tags allowed
        max_length: Maximum length per tag

    Raises:
        ValidationError: If tags exceed count or length limits
    """
    if tags is None:
        return

    if len(tags) > max_count:
        raise ValidationError(
            f"Too many tags: {len(tags)}. Maximum allowed: {max_count}"
        )

    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise ValidationError(
                f"Tag at index {i} must be a string, got {type(tag).__name__}"
            )
        if len(tag) > max_length:
            raise ValidationError(
                f"Tag at index {i} too long ({len(tag)} chars). "
                f"Maximum: {max_length} characters"
            )


def validate_uuid(value: str, param_name: str = "id") -> None:
    """Validate string is valid UUID format.

    Args:
        value: String to validate
        param_name: Parameter name for error message

    Raises:
        ValidationError: If value is not a valid UUID
    """
    try:
        uuid_lib.UUID(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {param_name}: '{value}' is not a valid UUID format"
        )


def validate_language(language: str | None) -> None:
    """Validate programming language for code search.

    Args:
        language: Language string (or None to skip)

    Raises:
        ValidationError: If language is not supported
    """
    if language is None:
        return

    lang_lower = language.lower()
    if lang_lower not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Unsupported language: '{language}'. "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )


def validate_project_id(project: str) -> None:
    """Validate project identifier format.

    Project IDs must be:
    - Alphanumeric with dashes and underscores
    - Start with alphanumeric character
    - Max 100 characters

    Args:
        project: Project identifier string

    Raises:
        ValidationError: If project format is invalid
    """
    if not project:
        raise ValidationError("Project identifier cannot be empty")

    if len(project) > PROJECT_ID_MAX_LENGTH:
        raise ValidationError(
            f"Project identifier too long ({len(project)} chars). "
            f"Maximum: {PROJECT_ID_MAX_LENGTH} characters"
        )

    if not PROJECT_ID_PATTERN.match(project):
        raise ValidationError(
            f"Invalid project identifier: '{project}'. "
            f"Must contain only alphanumeric characters, dashes, and underscores, "
            f"and start with an alphanumeric character"
        )


def validate_limit_range(
    limit: int,
    min_val: int,
    max_val: int,
    param_name: str = "limit",
) -> None:
    """Validate integer is within allowed range.

    Args:
        limit: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        param_name: Parameter name for error message

    Raises:
        ValidationError: If limit is out of range
    """
    if not min_val <= limit <= max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {limit} out of range. "
            f"Must be between {min_val} and {max_val}."
        )


def validate_positive_int(value: int, param_name: str, max_val: int | None = None) -> None:
    """Validate integer is positive (and optionally within max).

    Args:
        value: Value to validate
        param_name: Parameter name for error message
        max_val: Optional maximum value

    Raises:
        ValidationError: If value is not positive or exceeds max
    """
    if value < 1:
        raise ValidationError(
            f"{param_name.capitalize()} must be positive, got {value}"
        )
    if max_val is not None and value > max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {value} exceeds maximum of {max_val}"
        )


def validate_text_length(
    text: str | None,
    max_length: int,
    param_name: str,
    allow_empty: bool = True,
) -> None:
    """Validate text length.

    Args:
        text: Text to validate (or None to skip)
        max_length: Maximum allowed length
        param_name: Parameter name for error message
        allow_empty: Whether empty strings are allowed

    Raises:
        ValidationError: If text exceeds max length or is empty when not allowed
    """
    if text is None:
        return

    if not allow_empty and not text.strip():
        raise ValidationError(f"{param_name.capitalize()} cannot be empty")

    if len(text) > max_length:
        raise ValidationError(
            f"{param_name.capitalize()} too long ({len(text)} chars). "
            f"Maximum: {max_length} characters"
        )
```

### 2. Modify: `src/clams/server/tools/context.py`

Add validation at the start of `assemble_context`:

```python
# Add imports
from clams.server.tools.validation import (
    validate_context_types,
    validate_limit_range,
    validate_positive_int,
)

async def assemble_context(
    query: str,
    context_types: list[str] | None = None,
    limit: int = 10,
    max_tokens: int = 1500,
) -> dict[str, Any]:
    """Assemble relevant context for a user prompt."""

    # Validate parameters
    if context_types is not None:
        validate_context_types(context_types)
    else:
        context_types = ["values", "experiences"]

    validate_limit_range(limit, min_val=1, max_val=50, param_name="limit")
    validate_limit_range(max_tokens, min_val=100, max_val=10000, param_name="max_tokens")

    # Empty query returns empty result gracefully (not error)
    if not query.strip():
        return {
            "markdown": "",
            "token_count": 0,
            "item_count": 0,
            "truncated": False,
        }

    # ... rest of implementation
```

### 3. Modify: `src/clams/server/tools/memory.py`

Add validation for `min_importance`, `tags`, and `memory_id`:

```python
# Add imports
from clams.server.tools.validation import (
    validate_importance_range,
    validate_tags,
    validate_uuid,
)

# In retrieve_memories, add after existing validation:
async def retrieve_memories(
    query: str,
    limit: int = 10,
    category: str | None = None,
    min_importance: float = 0.0,
) -> dict[str, Any]:
    """Search memories semantically."""
    # ... existing validation ...

    # Add min_importance validation
    validate_importance_range(min_importance, "min_importance")

    # ... rest of implementation ...

# In store_memory, add tags validation:
async def store_memory(
    content: str,
    category: str,
    importance: float = 0.5,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Store a new memory with semantic embedding."""
    # ... existing validation ...

    # Add tags validation
    validate_tags(tags, max_count=20, max_length=50)

    # ... rest of implementation ...

# In list_memories, add tags validation:
async def list_memories(
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List memories with filters (non-semantic)."""
    # ... existing validation ...

    # Add tags validation
    validate_tags(tags, max_count=20, max_length=50)

    # ... rest of implementation ...

# In delete_memory, add UUID validation:
async def delete_memory(memory_id: str) -> dict[str, bool]:
    """Delete a memory by ID."""
    # Add UUID validation
    validate_uuid(memory_id, "memory_id")

    # ... rest of implementation ...
```

### 4. Modify: `src/clams/server/tools/code.py`

Add validation for `language` and `project`:

```python
# Add imports
from clams.server.tools.validation import (
    validate_language,
    validate_project_id,
)

# In search_code, add language validation:
async def search_code(
    query: str,
    project: str | None = None,
    language: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search indexed code semantically."""
    # ... existing validation ...

    # Add language validation
    validate_language(language)

    # ... rest of implementation ...

# In index_codebase, add project validation:
async def index_codebase(
    directory: str,
    project: str,
    recursive: bool = True,
) -> dict[str, Any]:
    """Index a directory of source code for semantic search."""
    # ... existing directory validation ...

    # Add project format validation
    validate_project_id(project)

    # ... rest of implementation ...
```

### 5. Modify: `src/clams/server/tools/ghap.py`

Add note length validation in `update_ghap`:

```python
# Add import (or use existing ValidationError)
from clams.server.tools.validation import validate_text_length

# In update_ghap, add note validation:
async def update_ghap(
    hypothesis: str | None = None,
    action: str | None = None,
    prediction: str | None = None,
    strategy: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Update the current GHAP entry."""
    # ... existing validation ...

    # Add note length validation (consistent with other 2000-char fields)
    validate_text_length(note, max_length=2000, param_name="note")

    # ... rest of implementation ...
```

### 6. Modify: `src/clams/context/tokens.py`

Add `max_tokens` validation in `distribute_budget`:

```python
def distribute_budget(
    context_types: list[str],
    max_tokens: int,
) -> dict[str, int]:
    """Distribute token budget across requested context types."""

    # Existing context_types validation
    invalid = [t for t in context_types if t not in SOURCE_WEIGHTS]
    if invalid:
        raise ValueError(
            f"Invalid context types: {invalid}. Valid: {list(SOURCE_WEIGHTS.keys())}"
        )

    # Add max_tokens validation
    if max_tokens < 1:
        raise ValueError(
            f"max_tokens must be positive, got {max_tokens}"
        )
    if max_tokens > 100000:
        raise ValueError(
            f"max_tokens {max_tokens} exceeds maximum of 100000"
        )

    # ... rest of implementation ...
```

**Note**: `distribute_budget` uses `ValueError` (not `ValidationError`) because it's an internal function in the `context` module, not an MCP tool handler. This is consistent with the existing pattern.

## Error Response Format

All validation errors follow the existing pattern:

```python
# For tool-level errors (via ValidationError exception)
raise ValidationError(
    f"Invalid {param}: {value}. Valid options: {', '.join(valid)}"
)
```

The tool dispatcher catches `ValidationError` and formats it appropriately for MCP responses. This is already implemented and consistent across the codebase.

## Testing Strategy

### New Test File: `tests/server/tools/test_input_validation.py`

This single file tests all new validation. Organize by tool:

```python
"""Input validation tests for SPEC-057.

Tests cover the validation gaps identified in the R4-A audit:
- assemble_context: context_types, limit, max_tokens, empty query handling
- retrieve_memories: min_importance range
- store_memory/list_memories: tags array validation
- delete_memory: UUID format
- search_code: language validation
- index_codebase: project format
- update_ghap: note length
- distribute_budget: max_tokens
"""

import pytest
from clams.server.tools.errors import ValidationError


class TestAssembleContextValidation:
    """Critical: assemble_context has complete lack of validation."""

    @pytest.mark.asyncio
    async def test_invalid_context_type_raises_error(self, context_tools):
        """Invalid context_type should error, not silently ignore."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError, match="Invalid context types"):
            await tool(query="test", context_types=["invalid"])

    @pytest.mark.asyncio
    async def test_invalid_context_type_lists_valid_options(self, context_tools):
        """Error message should list valid options."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(query="test", context_types=["wrong"])
        assert "values" in str(exc_info.value)
        assert "experiences" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_limit_below_range(self, context_tools):
        """limit=0 should error."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=0)

    @pytest.mark.asyncio
    async def test_limit_above_range(self, context_tools):
        """limit=100 should error (max is 50)."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=100)

    @pytest.mark.asyncio
    async def test_max_tokens_below_range(self, context_tools):
        """max_tokens=50 should error (min is 100)."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError, match="Max_tokens.*out of range"):
            await tool(query="test", max_tokens=50)

    @pytest.mark.asyncio
    async def test_max_tokens_above_range(self, context_tools):
        """max_tokens=20000 should error (max is 10000)."""
        tool = context_tools["assemble_context"]
        with pytest.raises(ValidationError, match="Max_tokens.*out of range"):
            await tool(query="test", max_tokens=20000)

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_result(self, context_tools):
        """Empty query should return empty result, not error."""
        tool = context_tools["assemble_context"]
        result = await tool(query="")
        assert result["item_count"] == 0
        assert result["markdown"] == ""


class TestRetrieveMemoriesValidation:
    """min_importance range validation."""

    @pytest.mark.asyncio
    async def test_min_importance_below_range(self, memory_tools):
        """min_importance=-0.5 should error."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Min_importance.*out of range"):
            await tool(query="test", min_importance=-0.5)

    @pytest.mark.asyncio
    async def test_min_importance_above_range(self, memory_tools):
        """min_importance=1.5 should error."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Min_importance.*out of range"):
            await tool(query="test", min_importance=1.5)

    @pytest.mark.asyncio
    async def test_min_importance_at_boundaries(self, memory_tools):
        """min_importance=0.0 and 1.0 should be accepted."""
        tool = memory_tools["retrieve_memories"]
        # Should not raise
        await tool(query="test", min_importance=0.0)
        await tool(query="test", min_importance=1.0)


class TestStoreMemoryTagsValidation:
    """Tags array validation."""

    @pytest.mark.asyncio
    async def test_too_many_tags(self, memory_tools):
        """More than 20 tags should error."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Too many tags"):
            await tool(
                content="test",
                category="fact",
                tags=["tag"] * 25,
            )

    @pytest.mark.asyncio
    async def test_tag_too_long(self, memory_tools):
        """Tag longer than 50 chars should error."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Tag.*too long"):
            await tool(
                content="test",
                category="fact",
                tags=["x" * 60],
            )

    @pytest.mark.asyncio
    async def test_tags_at_limits_accepted(self, memory_tools):
        """20 tags of 50 chars each should be accepted."""
        tool = memory_tools["store_memory"]
        result = await tool(
            content="test",
            category="fact",
            tags=["x" * 50] * 20,
        )
        assert "id" in result


class TestListMemoriesTagsValidation:
    """Tags array validation for list_memories."""

    @pytest.mark.asyncio
    async def test_too_many_tags(self, memory_tools):
        """More than 20 tags should error."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Too many tags"):
            await tool(tags=["tag"] * 25)


class TestDeleteMemoryValidation:
    """UUID format validation."""

    @pytest.mark.asyncio
    async def test_invalid_uuid_format(self, memory_tools):
        """Non-UUID string should error."""
        tool = memory_tools["delete_memory"]
        with pytest.raises(ValidationError, match="not a valid UUID"):
            await tool(memory_id="not-a-uuid")

    @pytest.mark.asyncio
    async def test_valid_uuid_accepted(self, memory_tools, mock_vector_store):
        """Valid UUID format should be accepted."""
        tool = memory_tools["delete_memory"]
        # Should not raise ValidationError (may raise other error from mock)
        result = await tool(memory_id="12345678-1234-1234-1234-123456789012")
        # Just checking it didn't raise ValidationError


class TestSearchCodeValidation:
    """Language validation."""

    @pytest.mark.asyncio
    async def test_invalid_language(self, code_tools):
        """Unsupported language should error."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Unsupported language"):
            await tool(query="test", language="brainfuck")

    @pytest.mark.asyncio
    async def test_invalid_language_lists_supported(self, code_tools):
        """Error message should list supported languages."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(query="test", language="invalid")
        assert "python" in str(exc_info.value)
        assert "typescript" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["python", "Python", "PYTHON"])
    async def test_valid_language_case_insensitive(self, code_tools, language):
        """Language validation should be case-insensitive."""
        tool = code_tools["search_code"]
        # Should not raise
        result = await tool(query="test", language=language)
        assert "results" in result


class TestIndexCodebaseValidation:
    """Project identifier format validation."""

    @pytest.mark.asyncio
    async def test_project_with_spaces(self, code_tools, tmp_path):
        """Project with spaces should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(directory=str(tmp_path), project="has spaces")

    @pytest.mark.asyncio
    async def test_project_with_special_chars(self, code_tools, tmp_path):
        """Project with special chars should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(directory=str(tmp_path), project="has@special!")

    @pytest.mark.asyncio
    async def test_project_too_long(self, code_tools, tmp_path):
        """Project > 100 chars should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="too long"):
            await tool(directory=str(tmp_path), project="x" * 101)

    @pytest.mark.asyncio
    async def test_valid_project_identifiers(self, code_tools, tmp_path, mock_services):
        """Valid project formats should be accepted."""
        from unittest.mock import MagicMock
        mock_stats = MagicMock()
        mock_stats.files_indexed = 0
        mock_stats.units_indexed = 0
        mock_stats.files_skipped = 0
        mock_stats.errors = []
        mock_stats.duration_ms = 1
        mock_services.code_indexer.index_directory.return_value = mock_stats

        tool = code_tools["index_codebase"]
        # All these should be accepted
        for project in ["my-project", "my_project", "MyProject123", "test"]:
            result = await tool(directory=str(tmp_path), project=project)
            assert result["project"] == project


class TestUpdateGhapValidation:
    """Note length validation."""

    @pytest.mark.asyncio
    async def test_note_too_long(self, ghap_tools, mock_collector_with_active):
        """Note > 2000 chars should error."""
        tool = ghap_tools["update_ghap"]
        result = await tool(note="x" * 3000)
        assert result.get("error", {}).get("type") == "validation_error"
        assert "2000" in result.get("error", {}).get("message", "")

    @pytest.mark.asyncio
    async def test_note_at_limit_accepted(self, ghap_tools, mock_collector_with_active):
        """Note of exactly 2000 chars should be accepted."""
        tool = ghap_tools["update_ghap"]
        result = await tool(note="x" * 2000)
        assert "success" in result or "error" not in result


class TestDistributeBudgetValidation:
    """max_tokens validation in distribute_budget."""

    def test_max_tokens_negative(self):
        """Negative max_tokens should error."""
        from clams.context.tokens import distribute_budget
        with pytest.raises(ValueError, match="must be positive"):
            distribute_budget(["memories"], max_tokens=-1)

    def test_max_tokens_zero(self):
        """Zero max_tokens should error."""
        from clams.context.tokens import distribute_budget
        with pytest.raises(ValueError, match="must be positive"):
            distribute_budget(["memories"], max_tokens=0)

    def test_max_tokens_too_large(self):
        """max_tokens > 100000 should error."""
        from clams.context.tokens import distribute_budget
        with pytest.raises(ValueError, match="exceeds maximum"):
            distribute_budget(["memories"], max_tokens=200000)

    def test_max_tokens_at_boundaries(self):
        """max_tokens=1 and max_tokens=100000 should be accepted."""
        from clams.context.tokens import distribute_budget
        # Should not raise
        distribute_budget(["memories"], max_tokens=1)
        distribute_budget(["memories"], max_tokens=100000)
```

### Test Fixtures

The tests use existing fixtures from `conftest.py`:
- `memory_tools`: Memory tool implementations with mocked services
- `code_tools`: Code tool implementations with mocked services
- `context_tools`: Context tool implementations with mocked dependencies
- `ghap_tools`: GHAP tool implementations with mocked collector/persister
- `mock_vector_store`: Mocked vector store for delete operations
- `mock_services`: Mocked service container
- `mock_collector_with_active`: Mock collector with an active GHAP entry

### Additional Unit Tests for Validation Module

Create `tests/server/tools/test_validation.py` to test the validation helpers directly:

```python
"""Unit tests for validation helper functions."""

import pytest
from clams.server.tools.validation import (
    validate_context_types,
    validate_importance_range,
    validate_tags,
    validate_uuid,
    validate_language,
    validate_project_id,
    validate_limit_range,
    validate_positive_int,
    validate_text_length,
)
from clams.server.tools.errors import ValidationError


class TestValidateContextTypes:
    def test_valid_types(self):
        validate_context_types(["values"])
        validate_context_types(["experiences"])
        validate_context_types(["values", "experiences"])

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Invalid context types"):
            validate_context_types(["invalid"])

    def test_empty_list(self):
        validate_context_types([])  # Empty is allowed


class TestValidateImportanceRange:
    def test_valid_range(self):
        validate_importance_range(0.0)
        validate_importance_range(0.5)
        validate_importance_range(1.0)

    def test_below_range(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_importance_range(-0.1)

    def test_above_range(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_importance_range(1.1)


class TestValidateTags:
    def test_none_allowed(self):
        validate_tags(None)

    def test_empty_list(self):
        validate_tags([])

    def test_valid_tags(self):
        validate_tags(["tag1", "tag2", "tag3"])

    def test_too_many(self):
        with pytest.raises(ValidationError, match="Too many tags"):
            validate_tags(["t"] * 25)

    def test_tag_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_tags(["x" * 60])


class TestValidateUuid:
    def test_valid_uuid(self):
        validate_uuid("12345678-1234-5678-1234-567812345678")

    def test_invalid_format(self):
        with pytest.raises(ValidationError, match="not a valid UUID"):
            validate_uuid("not-a-uuid")


class TestValidateLanguage:
    def test_none_allowed(self):
        validate_language(None)

    def test_valid_languages(self):
        validate_language("python")
        validate_language("Python")
        validate_language("TYPESCRIPT")

    def test_invalid_language(self):
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language("brainfuck")


class TestValidateProjectId:
    def test_valid_ids(self):
        validate_project_id("my-project")
        validate_project_id("my_project")
        validate_project_id("Project123")

    def test_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_project_id("")

    def test_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_project_id("x" * 101)

    def test_invalid_chars(self):
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            validate_project_id("has spaces")
```

## Implementation Order

1. **Create `validation.py`** - All helper functions in one commit
2. **Update `context.py`** - Critical priority (BUG-036 risk)
3. **Update `memory.py`** - min_importance, tags, UUID validation
4. **Update `code.py`** - language, project validation
5. **Update `ghap.py`** - note length validation
6. **Update `tokens.py`** - max_tokens validation
7. **Add tests** - Both unit tests for helpers and integration tests for tools

## Spec Refinements

The spec is accurate and complete. No refinements needed.

One clarification on error message format: The spec suggests:
```python
f"Invalid {param}: {value}. Valid options: {', '.join(valid)}"
```

The implementation should adapt this pattern based on context:
- For enum validation: list valid options
- For range validation: show valid range
- For format validation: describe expected format
- For length validation: show maximum allowed

This is consistent with existing patterns in the codebase.

## Out of Scope

Per the spec:
- Validation that already exists (enums, existing limit/offset checks)
- Changing error message format beyond what's specified
- Adding validation to tools not in the audit
- Performance optimization of validation
- Schema-level validation (JSON schema handles basic types)
