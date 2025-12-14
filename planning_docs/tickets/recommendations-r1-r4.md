# Recommendation Tickets: R1-R4

## R1: Single Source of Truth for Types

**Summary**: Consolidate duplicate type definitions and ensure concrete implementations inherit from abstract base classes. The codebase currently has multiple locations defining the same types with incompatible implementations.

**Bug References**: BUG-040, BUG-041, BUG-026

---

### R1-A: Audit and Document Current Type Duplications

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
Before consolidation, we need a complete inventory of all type duplications. BUG-040 found `CodeResult` defined twice with different field names (`start_line`/`end_line` vs `line_start`/`line_end`). BUG-041 found the abstract `Searcher` in `context/searcher_types.py` is not inherited by the concrete `Searcher` in `search/searcher.py`. There may be other duplications we haven't discovered.

**Acceptance Criteria**:
- [ ] Document all duplicate type definitions in `planning_docs/type-audit.md`
- [ ] For each duplicate, note: location, field differences, and which is canonical
- [ ] Identify all classes that should inherit from ABCs but don't
- [ ] Create a mapping of "delete" vs "keep" for each duplicate

**Implementation Notes**:
Files to audit:
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/context/searcher_types.py` - abstract Searcher, re-exports result types
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/results.py` - canonical result dataclasses
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/searcher.py` - concrete Searcher
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/enums.py` - enum lists
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/store.py` - has `VALID_AXES`

Search patterns:
```bash
grep -r "class.*Result" src/clams --include="*.py"
grep -r "@dataclass" src/clams --include="*.py"
grep -r "VALID_AXES\|DOMAINS\|STRATEGIES" src/clams --include="*.py"
```

**Testing Requirements**:
- Audit document is complete and accurate (manual verification)
- All files in the audit exist and definitions match documented state

---

### R1-B: Consolidate Result Type Definitions

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R1-A

**Problem Statement**:
BUG-040 revealed `CodeResult` was defined twice with incompatible field names. The fix was to make `context/searcher_types.py` re-export from `search/results.py` instead of defining its own types. This pattern should be applied to all result types and verified complete.

**Acceptance Criteria**:
- [ ] `search/results.py` is the single canonical location for all result dataclasses
- [ ] `context/searcher_types.py` only re-exports from `search/results.py` (no local definitions)
- [ ] All imports of result types come from one of these two locations
- [ ] `mypy --strict` passes with no type errors

**Implementation Notes**:
Current state (after BUG-040 fix) shows `context/searcher_types.py` already re-exports:
```python
from clams.search.results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)
```

Verify no other files define competing result types. Check:
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/clustering/types.py`
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/types.py`
- Any other `**/types.py` files

**Testing Requirements**:
- `mypy --strict src/clams` passes
- Unit tests pass: `pytest tests/`
- Add test verifying `searcher_types.CodeResult is results.CodeResult` (identity check)

---

### R1-C: Enforce Searcher ABC Inheritance

**Type**: bug
**Priority**: P0
**Estimated Complexity**: Medium
**Dependencies**: R1-B

**Problem Statement**:
BUG-041 found that concrete `Searcher` in `search/searcher.py` does not inherit from abstract `Searcher` ABC in `context/searcher_types.py`. The concrete implementation already matches the interface (the fix was done), but we need to add a test to prevent regression.

**Acceptance Criteria**:
- [ ] `clams.search.searcher.Searcher` inherits from `clams.context.searcher_types.Searcher`
- [ ] Test exists verifying `isinstance(Searcher(...), SearcherABC)`
- [ ] All abstract methods are implemented with matching signatures
- [ ] `mypy --strict` validates the inheritance relationship

**Implementation Notes**:
Current state (after BUG-041 fix) in `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/searcher.py`:
```python
from clams.context.searcher_types import Searcher as SearcherABC
...
class Searcher(SearcherABC):
```

Add test in `tests/search/test_searcher.py`:
```python
def test_searcher_inherits_from_abc():
    """Verify Searcher implements the abstract interface."""
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    # Verify inheritance
    assert issubclass(Searcher, SearcherABC)

    # Verify abstract methods are implemented
    abstract_methods = getattr(SearcherABC, '__abstractmethods__', set())
    for method in abstract_methods:
        assert hasattr(Searcher, method), f"Missing implementation: {method}"
```

**Testing Requirements**:
- New test passes
- Existing tests continue to pass
- `mypy --strict` passes

---

### R1-D: Consolidate Enum/Constant Definitions

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R1-A

**Problem Statement**:
BUG-026 found enum values defined in JSON schemas (in `tools/__init__.py`) differed from validation enums (in `tools/enums.py`). Constants like `VALID_AXES`, `DOMAINS`, `STRATEGIES` are defined in multiple locations. These should be consolidated.

**Acceptance Criteria**:
- [ ] Single canonical location for all domain/strategy/axis constants
- [ ] `tools/__init__.py` JSON schemas reference the canonical constants
- [ ] `values/store.py` imports from canonical location instead of defining own `VALID_AXES`
- [ ] All imports trace back to single source

**Implementation Notes**:
Canonical location: `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/enums.py`

Currently defines:
- `DOMAINS` (list)
- `STRATEGIES` (list)
- `ROOT_CAUSE_CATEGORIES` (list)
- `VALID_AXES` (list)
- `OUTCOME_STATUS_VALUES` (list)

Duplicates to remove:
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/store.py` line 18: `VALID_AXES = {"full", "strategy", "surprise", "root_cause"}`

Verify `tools/__init__.py` already uses imports from `enums.py` (it does, per current code).

**Testing Requirements**:
- `pytest tests/server/tools/` passes
- `mypy --strict` passes
- Add test verifying `values/store.VALID_AXES == tools/enums.VALID_AXES` (if both exist, they must match)

---

## R2: Schema Generation from Code

**Summary**: Generate JSON schemas from Python enums/constants rather than maintaining them manually. This ensures schemas and validation logic can never drift.

**Bug References**: BUG-026

---

### R2-A: Create Schema Generation Utility

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R1-D (enum consolidation must happen first)

**Problem Statement**:
BUG-026 showed JSON schema enums in `tools/__init__.py` didn't match validation enums in `tools/enums.py`. Manual maintenance of schemas is error-prone. We should generate schema enum values programmatically from the Python constants.

**Acceptance Criteria**:
- [ ] `tools/schema.py` utility module exists
- [ ] Functions to generate enum lists for all domain constants
- [ ] Tool definitions in `__init__.py` use generated values
- [ ] No hardcoded enum values in tool definitions

**Implementation Notes**:
Create `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/schema.py`:
```python
"""Schema generation utilities - single source of truth for JSON schema enums."""

from .enums import (
    DOMAINS,
    STRATEGIES,
    ROOT_CAUSE_CATEGORIES,
    VALID_AXES,
    OUTCOME_STATUS_VALUES,
)


def get_domain_enum() -> list[str]:
    """Get domain enum values for JSON schema."""
    return list(DOMAINS)


def get_strategy_enum() -> list[str]:
    """Get strategy enum values for JSON schema."""
    return list(STRATEGIES)


def get_axis_enum() -> list[str]:
    """Get axis enum values for JSON schema."""
    return list(VALID_AXES)


def get_outcome_enum() -> list[str]:
    """Get outcome status enum values for JSON schema."""
    return list(OUTCOME_STATUS_VALUES)


def get_root_cause_category_enum() -> list[str]:
    """Get root cause category enum values for JSON schema."""
    return list(ROOT_CAUSE_CATEGORIES)
```

Then update `__init__.py` to use these functions (or import constants directly as it currently does).

**Testing Requirements**:
- Unit test verifying schema functions return same values as enums
- `pytest tests/server/tools/test_schema.py` passes
- Integration test that parses tool definitions and verifies enum values match

---

### R2-B: Add Schema Conformance Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R2-A

**Problem Statement**:
Even with generated schemas, we need regression tests to catch if someone accidentally hardcodes values. Tests should verify schema enums match validation enums.

**Acceptance Criteria**:
- [ ] Test file `tests/server/tools/test_schema_conformance.py` exists
- [ ] Tests compare JSON schema enum values to Python enum values
- [ ] Tests fail if any enum drifts
- [ ] CI runs these tests

**Implementation Notes**:
Create `/Users/elliotmilco/Documents/GitHub/clams/tests/server/tools/test_schema_conformance.py`:
```python
"""Verify JSON schemas match Python enums (prevent BUG-026 regression)."""

import pytest
from clams.server.tools import _get_all_tool_definitions
from clams.server.tools.enums import (
    DOMAINS,
    STRATEGIES,
    VALID_AXES,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
)


def get_schema_enum(tool_name: str, param_name: str) -> list[str] | None:
    """Extract enum values from tool schema."""
    tools = _get_all_tool_definitions()
    for tool in tools:
        if tool.name == tool_name:
            props = tool.inputSchema.get("properties", {})
            if param_name in props:
                return props[param_name].get("enum")
    return None


def test_start_ghap_domain_enum():
    """Verify start_ghap domain enum matches DOMAINS."""
    schema_enum = get_schema_enum("start_ghap", "domain")
    assert schema_enum is not None
    assert set(schema_enum) == set(DOMAINS)


def test_start_ghap_strategy_enum():
    """Verify start_ghap strategy enum matches STRATEGIES."""
    schema_enum = get_schema_enum("start_ghap", "strategy")
    assert schema_enum is not None
    assert set(schema_enum) == set(STRATEGIES)


def test_search_experiences_axis_enum():
    """Verify search_experiences axis enum matches VALID_AXES."""
    schema_enum = get_schema_enum("search_experiences", "axis")
    assert schema_enum is not None
    assert set(schema_enum) == set(VALID_AXES)


def test_resolve_ghap_status_enum():
    """Verify resolve_ghap status enum matches OUTCOME_STATUS_VALUES."""
    schema_enum = get_schema_enum("resolve_ghap", "status")
    assert schema_enum is not None
    assert set(schema_enum) == set(OUTCOME_STATUS_VALUES)
```

**Testing Requirements**:
- All new tests pass
- Tests catch intentional enum drift (verified by temporarily breaking an enum)

---

## R3: Mandatory Initialization Pattern

**Summary**: Establish a standard `_ensure_collection()` pattern for all vector store consumers. Every module that upserts to a collection must ensure it exists first.

**Bug References**: BUG-043, BUG-016

---

### R3-A: Audit Current Initialization Patterns

**Type**: chore
**Priority**: P0
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-043 found `memories`, `commits`, and `values` collections weren't being created on first use, causing 404 errors. Some modules already have `_ensure_collection()` patterns (GitAnalyzer, CodeIndexer, ValueStore), but others don't (memory tools). We need a complete audit.

**Acceptance Criteria**:
- [ ] Document all collection-using modules in `planning_docs/collection-audit.md`
- [ ] For each module, note: collection name, has ensure pattern (yes/no), initialization location
- [ ] Identify modules missing the pattern
- [ ] Prioritize fixes by frequency of use

**Implementation Notes**:
Current implementations with ensure patterns (search result from grep):
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/git/analyzer.py`: `_ensure_commits_collection()`
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/store.py`: `_ensure_values_collection()`
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/indexers/indexer.py`: `_ensure_collection()`
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/observation/persister.py`: `ensure_collections()`
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/memory.py`: `_ensure_memories_collection()` (module-level)

Check if any are missing or inconsistent:
- Search for `vector_store.upsert` calls
- Verify each has a preceding ensure call

**Testing Requirements**:
- Audit document is complete
- All identified modules are verified against actual code

---

### R3-B: Create Collection Mixin Pattern

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R3-A

**Problem Statement**:
The current ensure patterns vary in implementation: some are instance methods, some are module-level functions, some cache at instance level, some at module level. We should standardize on a single pattern.

**Acceptance Criteria**:
- [ ] `CollectionMixin` class or utility exists
- [ ] Provides `ensure_collection()` method with consistent caching
- [ ] Documents the expected usage pattern
- [ ] Can be adopted incrementally by existing modules

**Implementation Notes**:
Create `/Users/elliotmilco/Documents/GitHub/clams/src/clams/storage/collection_utils.py`:
```python
"""Collection initialization utilities."""

from typing import Protocol
from clams.storage.base import VectorStore


class CollectionEnsurer:
    """Mixin for classes that need to ensure collections exist.

    Usage:
        class MyIndexer(CollectionEnsurer):
            def __init__(self, vector_store: VectorStore, embedding_service: ...):
                super().__init__(vector_store, "my_collection", embedding_service.dimension)
                ...

            async def index(self, ...):
                await self.ensure_collection()
                ...
    """

    def __init__(
        self,
        vector_store: VectorStore,
        collection_name: str,
        dimension: int,
        distance: str = "cosine",
    ) -> None:
        self._vector_store = vector_store
        self._collection_name = collection_name
        self._collection_dimension = dimension
        self._collection_distance = distance
        self._collection_ensured = False

    async def ensure_collection(self) -> None:
        """Ensure collection exists (idempotent, cached)."""
        if self._collection_ensured:
            return

        try:
            await self._vector_store.create_collection(
                name=self._collection_name,
                dimension=self._collection_dimension,
                distance=self._collection_distance,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "409" in str(e):
                pass  # Collection exists
            else:
                raise

        self._collection_ensured = True
```

**Testing Requirements**:
- Unit tests for `CollectionEnsurer`
- Tests verify caching behavior (only one create attempt per instance)
- Tests verify error handling for "already exists"

---

### R3-C: Apply Ensure Pattern to All Modules

**Type**: bug
**Priority**: P0
**Estimated Complexity**: Medium
**Dependencies**: R3-A, R3-B

**Problem Statement**:
Any module that calls `vector_store.upsert()` without first ensuring the collection exists will fail on cold start. Based on BUG-043, this affects at least the memories collection.

**Acceptance Criteria**:
- [ ] All modules from R3-A audit have ensure patterns
- [ ] Each ensure is called before any upsert operation
- [ ] Ensure calls are cached (not repeated on every operation)
- [ ] Cold-start test passes (see R3-D)

**Implementation Notes**:
Based on current code analysis:

1. **Memory tools** (`/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/memory.py`):
   - Already has `_ensure_memories_collection()` at module level
   - Called before store/retrieve/list operations
   - Uses global `_memories_collection_ensured` for caching

2. **Git analyzer** (`/Users/elliotmilco/Documents/GitHub/clams/src/clams/git/analyzer.py`):
   - Already has `_ensure_commits_collection()` instance method
   - Called in `index_commits()` and `search_commits()`
   - Uses `self._collection_ensured` for caching

3. **Values store** (`/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/store.py`):
   - Already has `_ensure_values_collection()` instance method
   - Called in `store_value()` and `list_values()`
   - Uses `self._collection_ensured` for caching

4. **Code indexer** (`/Users/elliotmilco/Documents/GitHub/clams/src/clams/indexers/indexer.py`):
   - Already has `_ensure_collection()` instance method
   - Called in `index_directory()` and `search()`

5. **Observation persister** (`/Users/elliotmilco/Documents/GitHub/clams/src/clams/observation/persister.py`):
   - Has `ensure_collections()` for GHAP collections
   - Called explicitly in `tools/__init__.py` at startup

Verify all paths are covered and add any missing ensure calls.

**Testing Requirements**:
- Integration test with fresh Qdrant (no pre-existing collections)
- All operations succeed without 404 errors
- Verify ensure is called exactly once per collection per instance

---

### R3-D: Add Cold-Start Integration Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R3-C

**Problem Statement**:
BUG-043 and BUG-016 were not caught by tests because tests used pre-populated databases. We need tests that start with completely empty storage.

**Acceptance Criteria**:
- [ ] Test fixture creates fresh Qdrant with no collections
- [ ] Tests exercise all CRUD operations on each collection type
- [ ] No 404 "collection not found" errors
- [ ] CI includes cold-start test job

**Implementation Notes**:
Create `/Users/elliotmilco/Documents/GitHub/clams/tests/integration/test_cold_start.py`:
```python
"""Cold-start tests - verify operations work with empty database.

These tests use a fresh in-memory VectorStore with no pre-existing collections
to verify all modules properly initialize their collections on first use.
"""

import pytest
from clams.storage.memory import InMemoryVectorStore


@pytest.fixture
def cold_start_store():
    """Create empty vector store - simulates first run."""
    return InMemoryVectorStore()


@pytest.mark.asyncio
async def test_memory_cold_start(cold_start_store):
    """Memory operations should work on fresh database."""
    # Setup (minimal dependencies)
    from clams.server.tools.memory import (
        store_memory_impl,
        retrieve_memories_impl,
    )
    # ... test implementation


@pytest.mark.asyncio
async def test_code_index_cold_start(cold_start_store):
    """Code indexing should work on fresh database."""
    # ... test implementation


@pytest.mark.asyncio
async def test_ghap_cold_start(cold_start_store):
    """GHAP operations should work on fresh database."""
    # ... test implementation


@pytest.mark.asyncio
async def test_values_cold_start(cold_start_store):
    """Value operations should work on fresh database."""
    # ... test implementation


@pytest.mark.asyncio
async def test_commits_cold_start(cold_start_store):
    """Commit indexing should work on fresh database."""
    # ... test implementation
```

**Testing Requirements**:
- All cold-start tests pass
- Tests actually use empty database (verified by adding debug logging)
- CI runs these tests in isolation

---

## R4: Defensive Input Validation

**Summary**: Validate all inputs at public function boundaries with descriptive error messages that list valid options.

**Bug References**: BUG-036, BUG-029

---

### R4-A: Audit Public Function Input Validation

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-036 showed `distribute_budget()` raised cryptic `KeyError` on invalid input instead of helpful error. BUG-029 showed `start_ghap` with active entry returned generic "internal_error". We need to identify all public functions that accept user input and verify they have proper validation.

**Acceptance Criteria**:
- [ ] Document all MCP tool handler functions in `planning_docs/validation-audit.md`
- [ ] For each, note: parameters, current validation (if any), suggested improvements
- [ ] Identify highest-priority functions (most user-facing)
- [ ] List specific error messages that should be improved

**Implementation Notes**:
MCP tools are in `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/`:
- `memory.py` - store_memory, retrieve_memories, list_memories, delete_memory
- `code.py` - index_codebase, search_code, find_similar_code
- `git.py` - index_commits, search_commits, get_file_history, get_churn_hotspots, get_code_authors
- `ghap.py` - start_ghap, update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
- `learning.py` - get_clusters, get_cluster_members, validate_value, store_value, list_values
- `search.py` - search_experiences
- `session.py` - start_session, get_orphaned_ghap, should_check_in, increment_tool_count, reset_tool_count
- `context.py` - assemble_context

Internal functions also used:
- `/Users/elliotmilco/Documents/GitHub/clams/src/clams/context/tokens.py`: `distribute_budget()` (BUG-036)

**Testing Requirements**:
- Audit document is complete
- All public functions are listed with validation status

---

### R4-B: Add Validation to Context Assembler

**Type**: bug
**Priority**: P0
**Estimated Complexity**: Low
**Dependencies**: R4-A

**Problem Statement**:
BUG-036 showed `distribute_budget(context_types=["invalid_type"])` raised `KeyError: 'invalid_type'` because no validation against `SOURCE_WEIGHTS.keys()`. The error should list valid options.

**Acceptance Criteria**:
- [ ] `distribute_budget()` validates context_types against SOURCE_WEIGHTS.keys()
- [ ] Invalid types raise `ValueError` with message listing valid options
- [ ] `assemble_context()` also validates (defense in depth)
- [ ] Error messages are user-friendly

**Implementation Notes**:
File: `/Users/elliotmilco/Documents/GitHub/clams/src/clams/context/tokens.py`

Current code likely has:
```python
def distribute_budget(context_types: list[str], max_tokens: int) -> dict[str, int]:
    ...
    for ct in context_types:
        budget[ct] = SOURCE_WEIGHTS[ct]  # KeyError if invalid
```

Fix:
```python
def distribute_budget(context_types: list[str], max_tokens: int) -> dict[str, int]:
    """Distribute token budget across context types.

    Args:
        context_types: List of context type names
        max_tokens: Total token budget

    Returns:
        Dict mapping context type to token allocation

    Raises:
        ValueError: If any context_type is invalid
    """
    invalid = set(context_types) - SOURCE_WEIGHTS.keys()
    if invalid:
        valid_options = ", ".join(sorted(SOURCE_WEIGHTS.keys()))
        raise ValueError(
            f"Invalid context types: {sorted(invalid)}. "
            f"Valid options: {valid_options}"
        )
    ...
```

Note: The `assembler.py` already has validation using `InvalidContextTypeError` (line 66-71).

**Testing Requirements**:
- Test invalid context type raises ValueError with helpful message
- Test error message contains all valid options
- Existing tests continue to pass

---

### R4-C: Improve GHAP Tool Error Messages

**Type**: bug
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R4-A

**Problem Statement**:
BUG-029 showed `start_ghap` with an active GHAP entry returned generic `"internal_error"` instead of explaining that an entry already exists and must be resolved first.

**Acceptance Criteria**:
- [ ] `start_ghap` returns clear error if active entry exists
- [ ] Error message explains how to resolve (resolve_ghap or get_active_ghap)
- [ ] All GHAP tools return specific, actionable error messages
- [ ] No generic "internal_error" for recoverable conditions

**Implementation Notes**:
File: `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/ghap.py`

Current code likely catches exceptions and returns generic error. Should be:
```python
async def start_ghap_impl(...):
    # Check for active entry first
    active = await collector.get_active()
    if active is not None:
        return {
            "error": "active_ghap_exists",
            "message": (
                "An active GHAP entry already exists. "
                "Use resolve_ghap to complete it, or get_active_ghap to view it."
            ),
            "active_ghap_id": active.id,
        }

    # Normal flow...
```

Also check other GHAP tools:
- `update_ghap` - should error if no active entry
- `resolve_ghap` - should error if no active entry
- All should have specific error types, not generic "internal_error"

**Testing Requirements**:
- Test start_ghap with active entry returns specific error
- Test update_ghap without active entry returns specific error
- Test resolve_ghap without active entry returns specific error
- Error messages include actionable guidance

---

### R4-D: Add Validation Test Suite

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R4-B, R4-C

**Problem Statement**:
We need regression tests to ensure validation stays in place. Tests should pass invalid inputs and verify error messages contain valid options.

**Acceptance Criteria**:
- [ ] Test file `tests/server/tools/test_input_validation.py` exists
- [ ] Tests cover all MCP tools with invalid inputs
- [ ] Tests verify error messages list valid options
- [ ] Tests verify no generic "internal_error" for known error conditions

**Implementation Notes**:
Create `/Users/elliotmilco/Documents/GitHub/clams/tests/server/tools/test_input_validation.py`:
```python
"""Input validation tests - verify helpful error messages.

These tests verify that invalid inputs produce clear, actionable error
messages rather than cryptic KeyErrors or generic "internal_error".
"""

import pytest


@pytest.mark.asyncio
async def test_distribute_budget_invalid_type():
    """Invalid context type should list valid options."""
    from clams.context.tokens import distribute_budget

    with pytest.raises(ValueError) as exc_info:
        distribute_budget(["invalid_type"], 1000)

    error_msg = str(exc_info.value)
    assert "invalid_type" in error_msg.lower()
    assert "memories" in error_msg  # Should list valid option
    assert "code" in error_msg  # Should list valid option


@pytest.mark.asyncio
async def test_start_ghap_with_active_entry():
    """Starting GHAP with active entry should explain resolution."""
    # ... implementation using mocked collector with active entry

    # Verify error includes guidance
    assert "resolve_ghap" in error_msg or "get_active_ghap" in error_msg


@pytest.mark.asyncio
async def test_search_experiences_invalid_axis():
    """Invalid axis should list valid options."""
    from clams.search.searcher import Searcher
    from clams.search.collections import InvalidAxisError

    # ... setup

    with pytest.raises(InvalidAxisError) as exc_info:
        await searcher.search_experiences("query", axis="invalid")

    error_msg = str(exc_info.value)
    assert "full" in error_msg  # Valid axis
    assert "strategy" in error_msg  # Valid axis


@pytest.mark.asyncio
async def test_store_memory_invalid_category():
    """Invalid category should list valid options."""
    # ... implementation
```

**Testing Requirements**:
- All validation tests pass
- Tests catch regressions when validation is removed (verified manually)
- CI runs these tests

---

### R4-E: Add Validation to Remaining Tools

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: R4-A, R4-D

**Problem Statement**:
After addressing BUG-036 and BUG-029 specifically, apply the validation pattern to all remaining MCP tools identified in the audit.

**Acceptance Criteria**:
- [ ] All MCP tools validate enum parameters
- [ ] All tools validate required parameters are present
- [ ] All tools validate parameter constraints (e.g., limit > 0)
- [ ] All error messages are consistent in format and helpfulness

**Implementation Notes**:
Standard validation pattern:
```python
async def tool_impl(
    param1: str,
    param2: int,
    optional_enum: str | None = None,
) -> dict:
    # Validate enum parameter
    if optional_enum is not None and optional_enum not in VALID_VALUES:
        return {
            "error": "invalid_parameter",
            "message": f"Invalid {optional_enum!r}. Valid options: {', '.join(VALID_VALUES)}",
        }

    # Validate numeric constraints
    if param2 < 1 or param2 > 100:
        return {
            "error": "invalid_parameter",
            "message": f"param2 must be between 1 and 100, got {param2}",
        }

    # Normal flow...
```

Apply to all tools identified in R4-A audit.

**Testing Requirements**:
- Each tool has at least one invalid input test
- Tests from R4-D cover all tools
- No uncaught exceptions from invalid user input

---

## Implementation Order

Based on dependencies and impact:

### Phase 1: Audits and Foundation (can be parallelized)
1. **R1-A**: Audit type duplications
2. **R3-A**: Audit collection initialization
3. **R4-A**: Audit input validation

### Phase 2: High Priority Fixes
4. **R1-B**: Consolidate result types (depends on R1-A)
5. **R1-C**: Enforce Searcher ABC (depends on R1-B)
6. **R3-C**: Apply ensure pattern (depends on R3-A)
7. **R4-B**: Add context assembler validation (depends on R4-A)
8. **R4-C**: Improve GHAP errors (depends on R4-A)

### Phase 3: Prevention Infrastructure
9. **R2-A**: Create schema generation utility (depends on R1-D)
10. **R2-B**: Add schema conformance tests (depends on R2-A)
11. **R3-B**: Create collection mixin (depends on R3-A)
12. **R3-D**: Add cold-start tests (depends on R3-C)
13. **R4-D**: Add validation test suite (depends on R4-B, R4-C)

### Phase 4: Cleanup and Completeness
14. **R1-D**: Consolidate enum definitions (depends on R1-A)
15. **R4-E**: Validate remaining tools (depends on R4-A, R4-D)
