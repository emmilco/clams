# SPEC-003: Optimize MCP Protocol Test Performance

## Problem Statement

The MCP protocol integration tests (`tests/integration/test_mcp_protocol.py`) take ~2 minutes to run 10 tests. Each test takes ~12-13 seconds in setup because:

1. The `mcp_session` fixture has function scope, starting a fresh server for every test
2. Server startup loads the embedding model **twice** (once in validation, once in initialization)

### Current Performance

```
13.22s setup    test_retrieve_memories_callable
13.21s setup    test_server_initializes
13.17s setup    test_tool_count_matches_expected
...
0.28s call     test_store_memory_callable  (actual test)
```

- **Setup**: 12-13s per test (server startup)
- **Test execution**: <1s per test
- **Total**: ~130s for 10 tests

### Root Causes

#### 1. Function-scoped fixture (test issue)
The `mcp_session` fixture uses default `scope="function"`, creating a new server process for each test.

#### 2. Duplicate model loading (server issue)
The server loads the Nomic embedding model twice on startup:

```python
# main.py:54-57 - validate_configuration()
_ = SentenceTransformer(settings.embedding_model, trust_remote_code=True)

# main.py:109-110 - initialize_collections()
embedding_service = NomicEmbedding(settings=embedding_settings)  # Loads again!
```

Each model load takes ~5-6 seconds, so startup is ~12s instead of ~6s.

## Proposed Solution

### Part 1: Module-scoped test fixture

Change the fixture to `scope="module"` so all tests share one server instance.

**Expected improvement**: 10 startups → 1 startup = ~120s saved

### Part 2: Single model load on server startup

Refactor `main.py` to load the embedding model once and reuse it:

```python
def validate_and_create_embedding_service(settings: ServerSettings) -> NomicEmbedding:
    """Load embedding model once, use for both validation and initialization."""
    embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
    embedding_service = NomicEmbedding(settings=embedding_settings)
    logger.info("embedding_model.loaded", model=settings.embedding_model)
    return embedding_service
```

**Expected improvement**: ~6s faster per startup

### Combined Expected Performance

- **Before**: 10 tests × 12s = ~120s
- **After**: 1 startup × 6s + 10 tests × <1s = ~15s

**Total improvement: ~8x faster**

## Technical Approach

### Part 1: Test fixture changes

pytest-asyncio requires special handling for module-scoped async fixtures:

1. Use `@pytest_asyncio.fixture(scope="module", loop_scope="module")` decorator
2. Ensure all tests in the module run on the same event loop
3. Handle cleanup properly to avoid resource leaks

### Part 2: Server startup refactor

1. Create embedding service once at startup
2. Pass it to `validate_configuration()` for dimension/model checks
3. Pass it to `initialize_collections()` for collection creation
4. Pass it to `register_all_tools()` for tool registration

Files to modify:
- `src/learning_memory_server/server/main.py`
- `tests/integration/test_mcp_protocol.py`

## Acceptance Criteria

1. All 10 MCP protocol tests pass
2. Total test time reduced to <30 seconds (from ~130s)
3. Server process is reused across tests (only 1 startup per test run)
4. Embedding model loaded only once per server startup
5. No flaky behavior introduced
6. Proper cleanup on test completion
7. Full test suite (518 tests) still passes

## Out of Scope

- Lazy loading of embedding model (load on first use)
- Parallelizing tests across multiple server instances
- Caching embedding model across server restarts
