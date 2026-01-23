# Proposal: Cold-Start Integration Tests for Vector Store Collections

## Summary

This proposal defines the technical design for integration tests that verify vector store collections are properly created on first use (cold-start) against a real Qdrant instance. These tests complement the existing mock-based regression tests in `tests/server/test_bug_043_regression.py` by validating actual Qdrant behavior.

## Test File Structure

### Location

```
tests/integration/test_cold_start_collections.py
```

This file sits alongside existing integration tests (`test_data_flows.py`, `test_mcp_protocol.py`, etc.) and follows the same conventions.

### Class Organization

```python
# Test file structure
class TestMemoriesColdStart:
    """Cold-start tests for memories collection."""

class TestCommitsColdStart:
    """Cold-start tests for commits collection."""

class TestValuesColdStart:
    """Cold-start tests for values collection."""

class TestCodeUnitsColdStart:
    """Cold-start tests for code_units collection."""

class TestGHAPCollectionsColdStart:
    """Cold-start tests for GHAP collections (ghap_full, ghap_strategy, etc.)."""
```

## Fixture Design

### Core Fixtures

#### 1. Qdrant Availability Verification

```python
@pytest.fixture(scope="session", autouse=True)
def verify_qdrant() -> None:
    """Verify Qdrant is available before running tests.

    Tests FAIL if Qdrant unavailable - no skips per spec.
    """
    try:
        response = httpx.get("http://localhost:6333/healthz", timeout=5)
        response.raise_for_status()
    except Exception as e:
        pytest.fail(f"Qdrant not available at localhost:6333: {e}")
```

#### 2. Real Qdrant Vector Store

```python
@pytest.fixture
async def vector_store() -> AsyncIterator[QdrantVectorStore]:
    """Create a Qdrant vector store for tests."""
    store = QdrantVectorStore(url="http://localhost:6333")
    yield store
```

#### 3. Mock Embedding Service

```python
@pytest.fixture
def embedding_service() -> MockEmbedding:
    """Create a mock embedding service for deterministic, fast tests."""
    return MockEmbedding()  # 768-dimensional by default
```

### Collection Name Isolation Strategy

The tests use parameterized collection names with a `test_cold_start_` prefix to avoid conflicts with production data and allow parallel test execution.

#### 4. Collection Name Generator

```python
@pytest.fixture
def test_id() -> str:
    """Generate unique test identifier for collection isolation."""
    return str(uuid.uuid4())[:8]

@pytest.fixture
def collection_names(test_id: str) -> dict[str, str]:
    """Generate isolated collection names for this test run."""
    return {
        "memories": f"test_cold_start_memories_{test_id}",
        "commits": f"test_cold_start_commits_{test_id}",
        "values": f"test_cold_start_values_{test_id}",
        "code_units": f"test_cold_start_code_units_{test_id}",
        "ghap_full": f"test_cold_start_ghap_full_{test_id}",
        "ghap_strategy": f"test_cold_start_ghap_strategy_{test_id}",
        "ghap_surprise": f"test_cold_start_ghap_surprise_{test_id}",
        "ghap_root_cause": f"test_cold_start_ghap_root_cause_{test_id}",
    }
```

### Cold-Start Environment Fixture

#### 5. Clean Slate Fixture

```python
@pytest.fixture
async def cold_start_collection(
    vector_store: QdrantVectorStore,
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[QdrantVectorStore, str]]:
    """Ensure collection doesn't exist before test (cold start).

    Args:
        vector_store: Qdrant store instance
        request: Pytest request for accessing parameterized collection name

    Yields:
        Tuple of (vector_store, collection_name)
    """
    collection_name = request.param  # Parameterized collection name

    # Delete if exists (ensure cold start)
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass  # Collection may not exist

    # Verify collection doesn't exist
    info = await vector_store.get_collection_info(collection_name)
    assert info is None, f"Collection {collection_name} should not exist before test"

    yield vector_store, collection_name

    # Cleanup after test
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass
```

## Test Implementation Strategy

### Approach: Direct Module Testing with Collection Name Injection

The modules under test (`memory.py`, `analyzer.py`, `store.py`, `indexer.py`, `persister.py`) have hardcoded collection names. To test cold-start behavior with isolated collection names, we use one of these strategies:

#### Strategy A: Monkey-Patch Collection Constants (Recommended)

For modules that use module-level constants (like `VALUES_COLLECTION` in `values/store.py`):

```python
async def test_store_value_creates_collection_on_cold_start(
    vector_store: QdrantVectorStore,
    embedding_service: MockEmbedding,
    collection_names: dict[str, str],
) -> None:
    """Verify store_value creates collection if it doesn't exist."""
    from unittest.mock import patch
    from clams.values import store as values_store_module

    collection_name = collection_names["values"]

    # Ensure cold start
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass

    # Verify collection doesn't exist
    info = await vector_store.get_collection_info(collection_name)
    assert info is None

    # Patch the collection name constant
    with patch.object(values_store_module, "VALUES_COLLECTION", collection_name):
        # Create ValueStore instance (needs mock clusterer for validation bypass)
        mock_clusterer = create_mock_clusterer()
        value_store = ValueStore(
            embedding_service=embedding_service,
            vector_store=vector_store,
            clusterer=mock_clusterer,
        )

        # Reset collection ensured flag
        value_store._collection_ensured = False

        # Action: list_values triggers lazy creation
        await value_store.list_values()

        # Verify collection was created
        info = await vector_store.get_collection_info(collection_name)
        assert info is not None
        assert info.dimension == 768
```

#### Strategy B: Constructor Parameters (For Classes That Support It)

For `ObservationPersister`, which accepts a `collection_prefix` parameter:

```python
async def test_ensure_collections_creates_all_ghap_collections(
    vector_store: QdrantVectorStore,
    embedding_service: MockEmbedding,
    test_id: str,
) -> None:
    """Verify ensure_collections creates all four GHAP collections."""
    collection_prefix = f"test_cold_start_ghap_{test_id}"
    expected_collections = [
        f"{collection_prefix}_full",
        f"{collection_prefix}_strategy",
        f"{collection_prefix}_surprise",
        f"{collection_prefix}_root_cause",
    ]

    # Ensure cold start
    for name in expected_collections:
        try:
            await vector_store.delete_collection(name)
        except Exception:
            pass

    # Create persister with custom prefix
    persister = ObservationPersister(
        embedding_service=embedding_service,
        vector_store=vector_store,
        collection_prefix=collection_prefix,
    )

    # Action: ensure_collections triggers creation
    await persister.ensure_collections()

    # Verify all collections were created
    for name in expected_collections:
        info = await vector_store.get_collection_info(name)
        assert info is not None, f"Collection {name} should exist"
        assert info.dimension == 768
```

### Module-Level State Reset

The memory module uses a module-level `_memories_collection_ensured` flag. Tests must reset this:

```python
@pytest.fixture(autouse=True)
def reset_memory_module_state(self) -> None:
    """Reset module-level state between tests."""
    import clams.server.tools.memory as memory_module
    memory_module._memories_collection_ensured = False
    yield
    memory_module._memories_collection_ensured = False
```

For class-instance caching (GitAnalyzer, ValueStore, CodeIndexer), create fresh instances per test.

## Test Cases by Collection

### Memories Collection Tests

| Test | Method Under Test | Verifies |
|------|-------------------|----------|
| `test_store_memory_creates_collection_on_cold_start` | `store_memory` | Collection created before upsert |
| `test_retrieve_memories_creates_collection_on_cold_start` | `retrieve_memories` | Collection created before search |
| `test_list_memories_creates_collection_on_cold_start` | `list_memories` | Collection created before scroll/count |
| `test_memory_collection_has_correct_dimension` | Any | Dimension = 768 |
| `test_stored_memory_retrievable_after_cold_start` | `store_memory` + `retrieve_memories` | Full round-trip works |

### Commits Collection Tests

| Test | Method Under Test | Verifies |
|------|-------------------|----------|
| `test_index_commits_creates_collection_on_cold_start` | `index_commits` | Collection created before indexing |
| `test_search_commits_creates_collection_on_cold_start` | `search_commits` | Collection created before search |
| `test_commits_collection_has_correct_dimension` | Any | Dimension = 768 |
| `test_indexed_commit_searchable_after_cold_start` | `index_commits` + `search_commits` | Full round-trip works |

### Values Collection Tests

| Test | Method Under Test | Verifies |
|------|-------------------|----------|
| `test_store_value_creates_collection_on_cold_start` | `store_value` | Collection created before upsert |
| `test_list_values_creates_collection_on_cold_start` | `list_values` | Collection created before scroll |
| `test_values_collection_has_correct_dimension` | Any | Dimension = 768 |
| `test_stored_value_retrievable_after_cold_start` | `store_value` + `list_values` | Full round-trip works |

### Code Units Collection Tests

| Test | Method Under Test | Verifies |
|------|-------------------|----------|
| `test_index_file_creates_collection_on_cold_start` | `index_file` | Collection created before indexing |
| `test_code_units_collection_has_correct_dimension` | Any | Dimension = 768 |
| `test_indexed_code_searchable_after_cold_start` | `index_file` + vector store search | Full round-trip works |

### GHAP Collections Tests

| Test | Method Under Test | Verifies |
|------|-------------------|----------|
| `test_ensure_collections_creates_all_ghap_collections` | `ensure_collections` | All 4 collections created |
| `test_ghap_collections_have_correct_dimension` | Any | Each has dimension = 768 |
| `test_persist_works_after_ensure_collections` | `persist` | Can persist after creation |

## Helper Utilities

### Mock Clusterer for ValueStore Tests

ValueStore's `store_value` requires validation against clusters. Create a mock clusterer:

```python
def create_mock_clusterer() -> AsyncMock:
    """Create mock clusterer that bypasses validation for cold-start tests."""
    from clams.values import ClusterInfo

    mock = AsyncMock()
    mock.count_experiences = AsyncMock(return_value=25)
    mock.cluster_axis = AsyncMock(return_value=[
        ClusterInfo(
            cluster_id="full_0",
            axis="full",
            label=0,
            centroid=np.zeros(768, dtype=np.float32),
            member_ids=["exp_1", "exp_2", "exp_3"],
            size=3,
            avg_weight=0.9,
        ),
    ])
    return mock
```

### Mock Git Reader for GitAnalyzer Tests

```python
def create_mock_git_reader(repo_path: str = "/test/repo") -> MagicMock:
    """Create mock git reader for cold-start tests."""
    reader = MagicMock()
    reader.get_repo_root.return_value = repo_path
    reader.get_commits = AsyncMock(return_value=[])
    reader.get_head_sha = AsyncMock(return_value="abc123")
    return reader
```

### Mock Code Parser for CodeIndexer Tests

```python
def create_mock_parser() -> MagicMock:
    """Create mock code parser for cold-start tests."""
    from clams.indexers.base import SemanticUnit, UnitType

    parser = MagicMock()
    parser.detect_language.return_value = "python"
    parser.parse_file = AsyncMock(return_value=[
        SemanticUnit(
            name="test_function",
            qualified_name="module.test_function",
            unit_type=UnitType.FUNCTION,
            content="def test_function(): pass",
            signature="def test_function()",
            file_path="/test/file.py",
            language="python",
            start_line=1,
            end_line=1,
            docstring=None,
            complexity=1,
        )
    ])
    return parser
```

## Test Markers and Configuration

```python
# Mark all tests in module as integration tests
pytestmark = pytest.mark.integration

pytest_plugins = ("pytest_asyncio",)
```

## Expected Failures Without Fix

If the cold-start lazy creation code (BUG-043 fix) were reverted, these tests would fail with:
- `qdrant_client.http.exceptions.UnexpectedResponse` with status 404
- Error message: `Collection ... doesn't exist`

## Test Execution

```bash
# Run only cold-start integration tests
pytest tests/integration/test_cold_start_collections.py -v

# Run with real Qdrant (required)
# Qdrant must be running at localhost:6333
docker run -p 6333:6333 qdrant/qdrant
```

## Implementation Dependencies

1. **BUG-043 fix must be merged**: Tests verify the lazy creation pattern
2. **Qdrant at localhost:6333**: Tests require real Qdrant instance
3. **MockEmbedding**: For deterministic 768-dimensional embeddings

## Out of Scope

- Testing Qdrant internals (we trust the client)
- Testing with different distance metrics (only cosine used)
- Concurrent cold-start race conditions (covered by unit tests)
- Performance benchmarking

## Verification Criteria

Each cold-start test verifies:

1. **Pre-condition**: Collection does NOT exist (`get_collection_info` returns `None`)
2. **Action**: Call the method that triggers lazy creation
3. **Post-condition**: Collection EXISTS with correct configuration
4. **Functional**: Operation succeeds (no 404 errors)
5. **Round-trip**: Data stored can be retrieved
