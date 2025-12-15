# SPEC-018: Add Cold-Start Integration Tests for Vector Store Collections

## Problem Statement

BUG-043 revealed that the `memories`, `commits`, and `values` collections were not auto-created on first use, causing 404 errors on fresh installations. The fix implemented lazy collection creation following the `CodeIndexer._ensure_collection()` pattern.

While BUG-043 includes regression tests using mocks (in `tests/server/test_bug_043_regression.py`), there are no integration tests that verify this behavior against a real Qdrant instance. The existing data flow tests in `tests/integration/test_data_flows.py` pre-create all collections in fixtures, bypassing the lazy creation logic.

This spec ensures we have integration tests that verify vector store collections are properly created on cold start (first use) with a real vector store backend.

## Context

### Related Work

- **BUG-043**: Fixed 404 errors by adding lazy collection creation for `memories`, `commits`, and `values` collections
- **BUG-016**: Previously fixed similar issue for GHAP collections by adding `ensure_collections()` at startup
- **`tests/integration/test_data_flows.py`**: Existing integration tests that test data flows but pre-create collections

### Collection Inventory

The following collections use lazy creation (via `_ensure_*_collection()` pattern):

| Collection | Module | Ensure Method |
|------------|--------|---------------|
| `memories` | `src/clams/server/tools/memory.py` | `_ensure_memories_collection()` |
| `commits` | `src/clams/git/analyzer.py` | `_ensure_commits_collection()` |
| `values` | `src/clams/values/store.py` | `_ensure_values_collection()` |
| `code_units` | `src/clams/indexers/indexer.py` | `_ensure_collection()` |

The following collections use startup creation (via `ensure_collections()`):

| Collection Pattern | Module | Ensure Method |
|-------------------|--------|---------------|
| `ghap_*` (full, strategy, surprise, root_cause) | `src/clams/observation/persister.py` | `ensure_collections()` |

## Proposed Solution

Add integration tests that verify cold-start collection creation against a real Qdrant instance. These tests will:

1. Delete any existing test collections before each test (ensure clean state)
2. Call the component that triggers lazy creation WITHOUT pre-creating collections
3. Verify the operation succeeds (no 404 errors)
4. Verify the collection now exists with correct configuration

## Acceptance Criteria

### Test File and Structure

- [ ] Test file exists at `tests/integration/test_cold_start_collections.py`
- [ ] Tests are marked with `@pytest.mark.integration` (requires Qdrant)
- [ ] Tests fail if Qdrant is unavailable (no skips per project conventions)
- [ ] Test collection names are prefixed with `test_cold_start_` to avoid conflicts

### Memories Collection Tests

- [ ] Test `store_memory` creates `memories` collection on cold start
- [ ] Test `retrieve_memories` creates `memories` collection on cold start
- [ ] Test `list_memories` creates `memories` collection on cold start
- [ ] Verify collection has correct dimension (768 for semantic embedder)
- [ ] Verify stored memory is retrievable after cold-start creation

### Commits Collection Tests

- [ ] Test `index_commits` creates `commits` collection on cold start
- [ ] Test `search_commits` creates `commits` collection on cold start
- [ ] Verify collection has correct dimension (768 for embedding service)
- [ ] Verify indexed commit is searchable after cold-start creation

### Values Collection Tests

- [ ] Test `list_values` creates `values` collection on cold start
- [ ] Verify collection has correct dimension (768 for embedding service)

### Code Units Collection Tests

- [ ] Test `index_file` creates `code_units` collection on cold start
- [ ] Verify collection has correct dimension (matches embedding service)
- [ ] Verify indexed code unit is searchable after cold-start creation

### GHAP Collections Tests

- [ ] Test `ensure_collections()` creates all four GHAP collections (`ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`)
- [ ] Verify each collection has correct dimension (768)
- [ ] Test `persist()` works after `ensure_collections()` is called

## Implementation Notes

### Test Setup Pattern

Each test should follow this pattern:

```python
@pytest.fixture
async def clean_collection(vector_store: QdrantVectorStore) -> AsyncIterator[None]:
    """Ensure collection doesn't exist before test (cold start)."""
    collection_name = "test_cold_start_memories"

    # Delete if exists (ensure cold start)
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass  # Collection may not exist

    yield

    # Cleanup after test
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass
```

### Collection Name Strategy

Use test-specific collection names to avoid conflicts with production:

- `test_cold_start_memories` (instead of `memories`)
- `test_cold_start_commits` (instead of `commits`)
- `test_cold_start_values` (instead of `values`)
- `test_cold_start_code_units` (instead of `code_units`)
- `test_cold_start_ghap_*` (instead of `ghap_*`)

This requires parameterizing the modules under test or using dependency injection.

### Mock vs Integration Strategy

The implementation should:
1. Use a real `QdrantVectorStore` instance pointing to `localhost:6333`
2. Use `MockEmbedding` for deterministic, fast embedding generation
3. Configure modules to use test collection names (via constructor parameters or monkey-patching)

### Example Test Structure

```python
class TestMemoriesColdStart:
    """Test cold-start creation of memories collection."""

    async def test_store_memory_creates_collection_on_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
    ) -> None:
        """Verify store_memory creates collection if it doesn't exist."""
        collection_name = "test_cold_start_memories"

        # Verify collection doesn't exist (cold start)
        info = await vector_store.get_collection_info(collection_name)
        assert info is None, "Collection should not exist before test"

        # Create ServiceContainer with our vector store
        services = ServiceContainer(
            semantic_embedder=embedding_service,
            vector_store=vector_store,
            ...
        )

        # Store memory (triggers lazy creation)
        # Note: May need to parameterize collection name in memory module
        tools = get_memory_tools(services)
        result = await tools["store_memory"](
            content="Test cold start",
            category="fact",
        )

        # Verify collection was created
        info = await vector_store.get_collection_info(collection_name)
        assert info is not None, "Collection should exist after store"
        assert info.dimension == 768

        # Verify memory is retrievable
        assert "id" in result
```

### Module Parameterization

The memory module uses a hardcoded collection name `"memories"`. For testing, consider:

1. **Option A**: Modify tests to use production collection names with careful cleanup
2. **Option B**: Add collection name parameter to `get_memory_tools()` (requires code change)
3. **Option C**: Use module-level monkey-patching in tests (fragile but no code changes)

Recommendation: Start with Option A (use production names with cleanup), then consider Option B if isolation becomes a problem.

## Testing Requirements

- Tests MUST run against real Qdrant (localhost:6333)
- Tests MUST clean up after themselves (delete test collections)
- Tests MUST fail fast if Qdrant is unavailable (not skip)
- Tests MUST verify collection configuration (dimension, distance metric)

## Out of Scope

- Testing Qdrant's internal behavior (we trust the Qdrant client)
- Testing collection creation with different distance metrics (only cosine used)
- Testing concurrent cold-start race conditions (covered by existing unit tests)
- Performance testing of cold-start vs warm-start paths

## Dependencies

- BUG-043 fix must be merged (lazy creation pattern in place)
- Qdrant must be available at localhost:6333 for integration tests
