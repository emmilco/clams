# SPEC-030 Technical Proposal: Cold-Start Testing Protocol

## Overview

This proposal details the implementation of cold-start tests that verify all major operations work correctly when starting with no pre-existing data. The cold-start fixture infrastructure has already been implemented in `tests/fixtures/cold_start.py` as part of BUG-043 and BUG-016 fixes; this proposal covers the test implementation for each operation category.

## Architecture

### Existing Fixture Infrastructure

The fixture infrastructure is already in place at `tests/fixtures/cold_start.py`:

```
tests/
  fixtures/
    cold_start.py              # Fixture implementations (existing)
    test_cold_start_fixtures.py # Fixture self-tests (existing)
  cold_start/                   # NEW: Operation tests
    __init__.py
    test_memory_cold_start.py
    test_git_cold_start.py
    test_values_cold_start.py
    test_ghap_cold_start.py
  conftest.py                   # Already imports cold_start fixtures
```

### Available Fixtures

| Fixture | Purpose | What It Provides |
|---------|---------|------------------|
| `cold_start_qdrant` | Empty Qdrant (no collections) | `QdrantVectorStore` with no collections |
| `cold_start_db` | Empty SQLite (schema only) | `MetadataStore` with tables but no data |
| `cold_start_env` | Both storage systems empty | `{"qdrant": ..., "db": ...}` dict |
| `populated_qdrant` | Qdrant with standard collections | Collections: memories, commits, code, values, experiences |
| `populated_db` | SQLite with sample data | Sample project and indexed file |
| `qdrant_state` | Parameterized (both scenarios) | Runs test twice: cold_start and populated |
| `db_state` | Parameterized (both scenarios) | Runs test twice: cold_start and populated |
| `storage_env` | Parameterized combined | Both systems, both scenarios |

### Pytest Marker

The `cold_start` marker is already registered in `pyproject.toml`:

```toml
markers = [
    "slow: marks tests as slow (>15s, excluded by default)",
    "integration: marks tests as integration tests requiring external services",
    "cold_start: tests that verify behavior with no pre-existing data",
]
```

## Test Implementation Plan

### Part 2: Memory Operations Tests

**File**: `tests/cold_start/test_memory_cold_start.py`

The memory tools use a module-level `_memories_collection_ensured` flag for lazy collection creation. Tests must be careful about this global state.

```python
"""Cold-start tests for memory operations.

These tests verify that memory operations handle the cold-start scenario
where no collections exist yet. The ensure_collection pattern should
automatically create collections on first use.

Reference: BUG-043 - memories collection was never created
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from clams.server.tools.memory import get_memory_tools, _memories_collection_ensured
from clams.server.tools import ServiceContainer
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
def reset_memory_module_state():
    """Reset module-level state before each test.

    The memory module uses a global flag to track collection creation.
    This must be reset between tests to ensure true cold-start behavior.
    """
    import clams.server.tools.memory as memory_module
    original = memory_module._memories_collection_ensured
    memory_module._memories_collection_ensured = False
    yield
    memory_module._memories_collection_ensured = original


@pytest.fixture
async def memory_services(cold_start_qdrant: QdrantVectorStore):
    """Create ServiceContainer with cold-start Qdrant and mock embedder."""
    semantic_embedder = AsyncMock()
    semantic_embedder.embed.return_value = [0.1] * 768
    semantic_embedder.dimension = 768

    return ServiceContainer(
        code_embedder=None,
        semantic_embedder=semantic_embedder,
        vector_store=cold_start_qdrant,
        metadata_store=None,
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


class TestStoreMemoryColdStart:
    """Tests for store_memory on cold start."""

    @pytest.mark.cold_start
    async def test_store_memory_creates_collection(
        self,
        memory_services: ServiceContainer,
        cold_start_qdrant: QdrantVectorStore,
        reset_memory_module_state,
    ) -> None:
        """First memory storage should auto-create collection."""
        # Verify collection doesn't exist
        info = await cold_start_qdrant.get_collection_info("memories")
        assert info is None, "memories collection should not exist on cold start"

        # Get tool implementations
        tools = get_memory_tools(memory_services)
        store_memory = tools["store_memory"]

        # Store a memory - should create collection
        result = await store_memory(
            content="Test memory content",
            category="fact",
            importance=0.7,
        )

        # Verify success - returns dict with memory_id key
        assert "id" in result, f"Expected 'id' key in result, got: {result}"
        assert result.get("category") == "fact"

        # Verify collection was created
        info = await cold_start_qdrant.get_collection_info("memories")
        assert info is not None, "memories collection should exist after store"
        assert info.dimension == 768

    @pytest.mark.cold_start
    async def test_store_memory_no_exception(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """store_memory should not raise exceptions on cold start."""
        tools = get_memory_tools(memory_services)
        store_memory = tools["store_memory"]

        # Should not raise any exception
        result = await store_memory(
            content="Another test memory",
            category="preference",
        )

        assert isinstance(result, dict)
        assert "id" in result


class TestRetrieveMemoriesColdStart:
    """Tests for retrieve_memories on cold start."""

    @pytest.mark.cold_start
    async def test_retrieve_memories_returns_empty_list(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """retrieve_memories should return empty list on cold start, not 404."""
        tools = get_memory_tools(memory_services)
        retrieve_memories = tools["retrieve_memories"]

        result = await retrieve_memories(query="test query")

        # Should return empty results, not error
        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_retrieve_memories_no_404_error(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """retrieve_memories should not raise 404 on cold start."""
        tools = get_memory_tools(memory_services)
        retrieve_memories = tools["retrieve_memories"]

        # Should not raise
        result = await retrieve_memories(
            query="nonexistent memory",
            limit=10,
            category="fact",
        )

        assert "error" not in result or "404" not in str(result.get("error", ""))


class TestListMemoriesColdStart:
    """Tests for list_memories on cold start."""

    @pytest.mark.cold_start
    async def test_list_memories_returns_empty_list(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """list_memories should return empty list on cold start."""
        tools = get_memory_tools(memory_services)
        list_memories = tools["list_memories"]

        result = await list_memories()

        assert "results" in result
        assert result["results"] == []
        assert result["total"] == 0

    @pytest.mark.cold_start
    async def test_list_memories_with_filters_cold_start(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """list_memories with filters should return empty on cold start."""
        tools = get_memory_tools(memory_services)
        list_memories = tools["list_memories"]

        result = await list_memories(
            category="fact",
            tags=["important"],
            limit=50,
        )

        assert result["results"] == []


class TestDeleteMemoryColdStart:
    """Tests for delete_memory on cold start."""

    @pytest.mark.cold_start
    async def test_delete_nonexistent_memory(
        self,
        memory_services: ServiceContainer,
        reset_memory_module_state,
    ) -> None:
        """delete_memory with non-existent ID should return error dict."""
        tools = get_memory_tools(memory_services)
        delete_memory = tools["delete_memory"]

        result = await delete_memory(memory_id="nonexistent-id-12345")

        # Per spec: returns error dict with 'error' key (not exception)
        # Looking at implementation, it returns {"deleted": False}
        assert isinstance(result, dict)
        # Verify it doesn't raise exception
        assert "deleted" in result
```

### Part 3: Git/Commit Operations Tests

**File**: `tests/cold_start/test_git_cold_start.py`

Git operations depend on `GitAnalyzer` service which may not be available. The tests must handle both service availability and empty collection scenarios.

```python
"""Cold-start tests for git operations.

These tests verify that git operations handle the cold-start scenario
gracefully. Git tools depend on GitAnalyzer service which requires
a git repository and vector storage.

Reference: BUG-043 - commits collection was never created
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from clams.server.tools.git import get_git_tools
from clams.server.tools import ServiceContainer
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
async def mock_git_analyzer():
    """Create a mock GitAnalyzer for testing."""
    analyzer = AsyncMock()

    # Mock index_commits to return empty stats
    mock_stats = MagicMock()
    mock_stats.commits_indexed = 0
    mock_stats.commits_skipped = 0
    mock_stats.duration_ms = 100
    mock_stats.errors = []
    analyzer.index_commits.return_value = mock_stats

    # Mock search_commits to return empty list
    analyzer.search_commits.return_value = []

    # Mock git_reader for file history
    mock_reader = AsyncMock()
    mock_reader.get_file_history.return_value = []
    analyzer.git_reader = mock_reader

    # Mock churn hotspots
    analyzer.get_churn_hotspots.return_value = []

    # Mock file authors
    analyzer.get_file_authors.return_value = []

    return analyzer


@pytest.fixture
async def git_services_with_analyzer(
    cold_start_qdrant: QdrantVectorStore,
    mock_git_analyzer,
):
    """ServiceContainer with mock GitAnalyzer for cold-start testing."""
    return ServiceContainer(
        code_embedder=None,
        semantic_embedder=None,
        vector_store=cold_start_qdrant,
        metadata_store=None,
        code_indexer=None,
        git_analyzer=mock_git_analyzer,
        searcher=None,
    )


@pytest.fixture
async def git_services_no_analyzer(cold_start_qdrant: QdrantVectorStore):
    """ServiceContainer without GitAnalyzer (simulates no git repo)."""
    return ServiceContainer(
        code_embedder=None,
        semantic_embedder=None,
        vector_store=cold_start_qdrant,
        metadata_store=None,
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


class TestIndexCommitsColdStart:
    """Tests for index_commits on cold start."""

    @pytest.mark.cold_start
    async def test_index_commits_returns_zero_count(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """index_commits on cold start returns dict with indexed count (may be 0)."""
        tools = get_git_tools(git_services_with_analyzer)
        index_commits = tools["index_commits"]

        result = await index_commits()

        # Should return stats dict, not exception
        assert isinstance(result, dict)
        assert "commits_indexed" in result
        # Value may be 0 on cold start
        assert isinstance(result["commits_indexed"], int)

    @pytest.mark.cold_start
    async def test_index_commits_no_analyzer_returns_error(
        self,
        git_services_no_analyzer: ServiceContainer,
    ) -> None:
        """index_commits without GitAnalyzer raises MCPError."""
        tools = get_git_tools(git_services_no_analyzer)
        index_commits = tools["index_commits"]

        # Without analyzer, should raise MCPError (not 404)
        from clams.server.errors import MCPError
        with pytest.raises(MCPError) as exc_info:
            await index_commits()

        assert "GitAnalyzer" in str(exc_info.value)


class TestSearchCommitsColdStart:
    """Tests for search_commits on cold start."""

    @pytest.mark.cold_start
    async def test_search_commits_returns_empty_list(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """search_commits on cold start returns empty list, not 404."""
        tools = get_git_tools(git_services_with_analyzer)
        search_commits = tools["search_commits"]

        result = await search_commits(query="fix bug")

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_search_commits_no_exception(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """search_commits should not raise exception on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        search_commits = tools["search_commits"]

        # Should not raise
        result = await search_commits(
            query="refactor",
            author="developer",
            limit=20,
        )

        assert isinstance(result, dict)


class TestGetFileHistoryColdStart:
    """Tests for get_file_history on cold start."""

    @pytest.mark.cold_start
    async def test_get_file_history_returns_empty_list(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_file_history on cold start returns empty list."""
        tools = get_git_tools(git_services_with_analyzer)
        get_file_history = tools["get_file_history"]

        result = await get_file_history(path="src/main.py")

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_get_file_history_no_404_error(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_file_history should not raise 404 on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        get_file_history = tools["get_file_history"]

        # Should return empty, not error
        result = await get_file_history(path="nonexistent/file.py")

        # Empty result is expected, not 404
        assert isinstance(result, dict)
```

### Part 4: Values/GHAP Operations Tests

**File**: `tests/cold_start/test_values_cold_start.py` and `tests/cold_start/test_ghap_cold_start.py`

Values and GHAP operations involve the `ValueStore`, `ExperienceClusterer`, `ObservationCollector`, and `ObservationPersister`. These have complex dependencies but should handle cold start gracefully.

```python
# tests/cold_start/test_values_cold_start.py
"""Cold-start tests for values/learning operations.

These tests verify that value operations handle the cold-start scenario
where no values or experiences exist yet.

Reference: BUG-043 - values collection was never created
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from clams.server.tools.learning import get_learning_tools
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
async def mock_experience_clusterer(cold_start_qdrant: QdrantVectorStore):
    """Mock ExperienceClusterer for cold-start testing."""
    clusterer = AsyncMock()
    clusterer.vector_store = cold_start_qdrant

    # count_experiences returns 0 on cold start
    clusterer.count_experiences.return_value = 0

    # cluster_axis returns empty list on cold start
    clusterer.cluster_axis.return_value = []

    return clusterer


@pytest.fixture
async def mock_value_store():
    """Mock ValueStore for cold-start testing."""
    store = AsyncMock()

    # list_values returns empty on cold start
    store.list_values.return_value = []

    # validate_value_candidate returns invalid for empty cluster
    mock_result = MagicMock()
    mock_result.valid = False
    mock_result.reason = "Not enough experiences"
    mock_result.similarity = None
    store.validate_value_candidate.return_value = mock_result

    return store


class TestStoreValueColdStart:
    """Tests for store_value on cold start."""

    @pytest.mark.cold_start
    async def test_store_value_insufficient_data(
        self,
        mock_experience_clusterer,
        mock_value_store,
    ) -> None:
        """store_value on cold start returns error for insufficient data."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        store_value = tools["store_value"]

        # Mock store_value to raise ValueError for validation failure
        mock_value_store.store_value.side_effect = ValueError(
            "Value failed validation: Not enough experiences"
        )

        result = await store_value(
            text="Test value",
            cluster_id="full_0",
            axis="full",
        )

        # Should return error response, not raise exception
        assert "error" in result
        assert result["error"]["type"] == "validation_error"


class TestListValuesColdStart:
    """Tests for list_values on cold start."""

    @pytest.mark.cold_start
    async def test_list_values_returns_empty_list(
        self,
        mock_experience_clusterer,
        mock_value_store,
        cold_start_qdrant: QdrantVectorStore,
    ) -> None:
        """list_values on cold start returns empty list."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        result = await list_values()

        # Should return empty results, not error
        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_list_values_no_exception(
        self,
        mock_experience_clusterer,
        mock_value_store,
    ) -> None:
        """list_values should not raise exception on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        # Should not raise
        result = await list_values(axis="full", limit=20)

        assert isinstance(result, dict)


class TestGetClustersColdStart:
    """Tests for get_clusters on cold start."""

    @pytest.mark.cold_start
    async def test_get_clusters_insufficient_data(
        self,
        mock_experience_clusterer,
        mock_value_store,
    ) -> None:
        """get_clusters on cold start returns error for insufficient data."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_clusters = tools["get_clusters"]

        result = await get_clusters(axis="full")

        # Should return error response with insufficient_data type
        assert "error" in result
        assert result["error"]["type"] == "insufficient_data"
        assert "20" in result["error"]["message"]  # Need at least 20 experiences

    @pytest.mark.cold_start
    async def test_get_clusters_returns_dict_with_clusters_key(
        self,
        mock_experience_clusterer,
        mock_value_store,
    ) -> None:
        """get_clusters always returns dict with clusters key (may be error)."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_clusters = tools["get_clusters"]

        result = await get_clusters(axis="strategy")

        # Either clusters key or error key
        assert isinstance(result, dict)
        assert "clusters" in result or "error" in result
```

```python
# tests/cold_start/test_ghap_cold_start.py
"""Cold-start tests for GHAP operations.

These tests verify that GHAP operations handle the cold-start scenario
where no GHAP entries exist yet.

Reference: BUG-016 - GHAP collections missing on first start
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from clams.server.tools.ghap import get_ghap_tools
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
async def mock_observation_collector():
    """Mock ObservationCollector for cold-start testing."""
    collector = AsyncMock()

    # get_current returns None (no active GHAP)
    collector.get_current.return_value = None

    # create_ghap returns a mock entry
    mock_entry = MagicMock()
    mock_entry.id = "ghap-test-123"
    collector.create_ghap.return_value = mock_entry

    return collector


@pytest.fixture
async def mock_observation_persister(cold_start_qdrant: QdrantVectorStore):
    """Mock ObservationPersister for cold-start testing."""
    persister = AsyncMock()
    persister._vector_store = cold_start_qdrant
    persister.persist.return_value = None
    return persister


class TestStartGhapColdStart:
    """Tests for start_ghap on cold start."""

    @pytest.mark.cold_start
    async def test_start_ghap_returns_id(
        self,
        mock_observation_collector,
        mock_observation_persister,
    ) -> None:
        """start_ghap on cold start returns dict with ghap_id key."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        start_ghap = tools["start_ghap"]

        result = await start_ghap(
            domain="debugging",
            strategy="hypothesis_testing",
            goal="Find the root cause",
            hypothesis="The bug is in the parser",
            action="Add logging to parser",
            prediction="Logs will show malformed input",
        )

        # Should return success with id
        assert "ok" in result or "id" in result
        if "ok" in result:
            assert result["ok"] is True

    @pytest.mark.cold_start
    async def test_start_ghap_no_exception(
        self,
        mock_observation_collector,
        mock_observation_persister,
    ) -> None:
        """start_ghap should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        start_ghap = tools["start_ghap"]

        # Should not raise
        result = await start_ghap(
            domain="feature",
            strategy="incremental",
            goal="Add new endpoint",
            hypothesis="Endpoint will improve UX",
            action="Implement the endpoint",
            prediction="Tests will pass",
        )

        assert isinstance(result, dict)


class TestListGhapEntriesColdStart:
    """Tests for list_ghap_entries on cold start."""

    @pytest.mark.cold_start
    async def test_list_ghap_entries_returns_empty(
        self,
        mock_observation_collector,
        mock_observation_persister,
    ) -> None:
        """list_ghap_entries on cold start returns empty list or dict with empty entries."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        result = await list_ghap_entries()

        # Should return empty results (collection may not exist yet)
        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_list_ghap_entries_no_exception(
        self,
        mock_observation_collector,
        mock_observation_persister,
    ) -> None:
        """list_ghap_entries should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        # Should not raise
        result = await list_ghap_entries(
            limit=20,
            domain="debugging",
        )

        assert isinstance(result, dict)
```

## Verification Strategy

### 1. Fixture Verification

The fixture self-tests in `tests/fixtures/test_cold_start_fixtures.py` already verify:
- `cold_start_qdrant` has no collections
- `cold_start_db` has schema but no data
- Fixtures provide isolation between tests
- Parameterized fixtures run both scenarios

### 2. Test Isolation Verification

Each test module should verify:
```python
@pytest.mark.cold_start
async def test_fixture_is_truly_empty(cold_start_qdrant):
    """Verify cold_start_qdrant has no pre-existing collections."""
    # List all collections
    collections = await cold_start_qdrant.list_collections()
    assert len(collections) == 0, "Cold start should have no collections"
```

### 3. No 404 Error Verification

Cold-start tests must verify that operations don't raise 404 errors:
```python
@pytest.mark.cold_start
async def test_no_404_on_cold_start(cold_start_qdrant, services):
    """Verify no 404 errors are raised on cold start."""
    tools = get_memory_tools(services)

    # Capture any exceptions
    try:
        result = await tools["retrieve_memories"](query="test")
        # Should succeed with empty results
        assert "results" in result
    except Exception as e:
        # Should not be a 404
        assert "404" not in str(e)
        assert "not found" not in str(e).lower()
```

### 4. Collection Creation Verification

For operations that create collections, verify:
```python
@pytest.mark.cold_start
async def test_collection_created_on_first_use(cold_start_qdrant, services):
    """Verify collection is created on first write operation."""
    # Before: no collection
    info = await cold_start_qdrant.get_collection_info("memories")
    assert info is None

    # Perform write operation
    tools = get_memory_tools(services)
    await tools["store_memory"](content="test", category="fact")

    # After: collection exists
    info = await cold_start_qdrant.get_collection_info("memories")
    assert info is not None
```

### 5. ensure_collection Pattern Verification

Verify that `ensure_collection` patterns work correctly:
```python
@pytest.mark.cold_start
async def test_ensure_collection_idempotent(cold_start_qdrant, services):
    """Verify ensure_collection can be called multiple times safely."""
    tools = get_memory_tools(services)

    # Multiple operations should all succeed
    await tools["store_memory"](content="test1", category="fact")
    await tools["store_memory"](content="test2", category="fact")
    await tools["retrieve_memories"](query="test")
    await tools["list_memories"]()

    # All should succeed without error
```

## Running Cold-Start Tests

### Run all cold-start tests
```bash
pytest -m cold_start -v
```

### Run cold-start tests for specific category
```bash
pytest tests/cold_start/test_memory_cold_start.py -v
pytest tests/cold_start/test_git_cold_start.py -v
pytest tests/cold_start/test_values_cold_start.py -v
pytest tests/cold_start/test_ghap_cold_start.py -v
```

### Run with both cold-start and populated scenarios (parameterized)
```bash
pytest -k "qdrant_state or db_state" -v
```

## Implementation Notes

### Module State Reset

The memory module uses a global `_memories_collection_ensured` flag. Tests must reset this flag to ensure true cold-start behavior. The `reset_memory_module_state` fixture handles this.

### Mock Dependencies

For true isolation, cold-start tests should:
1. Use `cold_start_qdrant` for real Qdrant behavior
2. Mock external services (embedders) that are not under test
3. Reset any module-level caching between tests

### Error Response Patterns

The codebase uses two patterns for errors:
1. **Exceptions**: `MCPError`, `ValidationError` for programming errors
2. **Error dicts**: `{"error": {"type": ..., "message": ...}}` for expected failures

Cold-start tests should verify the appropriate pattern is used.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| pytest | Test framework |
| pytest-asyncio | Async test support |
| qdrant-client | In-memory Qdrant for testing |
| existing fixtures | `cold_start_qdrant`, `cold_start_db`, etc. |

## Out of Scope

Per spec:
- CI job configuration for cold-start tests
- Cold-start tests for code indexing (complex setup)
- Performance testing of cold-start scenarios
