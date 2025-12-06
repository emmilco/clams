# Proposal: SPEC-003 - Optimize MCP Protocol Test Performance

## Problem Statement

The MCP protocol integration tests (`tests/integration/test_mcp_protocol.py`) take approximately 2 minutes to run 10 tests. Analysis shows:

- **Setup time**: 12-13 seconds per test (server startup)
- **Test execution**: <1 second per test
- **Total**: ~130 seconds for 10 tests

### Root Causes Identified

1. **Function-scoped fixture**: The `mcp_session` fixture (line 56) creates a fresh server process for every test. With 10 tests, that's 10 server startups.

2. **Triplicate model loading**: The server loads the Nomic embedding model **three times** on every startup:

   | Location | Function | File |
   |----------|----------|------|
   | Line 57 | `validate_configuration()` | `main.py` |
   | Line 110 | `initialize_collections()` | `main.py` |
   | Line 64 | `initialize_services()` | `tools/__init__.py` |

   Each load takes 4-5 seconds, so startup is ~15s instead of ~5s.

## Proposed Solution

### Part 1: Module-Scoped Test Fixture

Change the `mcp_session` fixture from function scope to module scope so all tests share a single server instance.

**Before:**
```python
@pytest.fixture
async def mcp_session() -> AsyncIterator[ClientSession]:
    # Creates new server for EACH test
```

**After:**
```python
@pytest_asyncio.fixture(scope="module")
async def mcp_session(event_loop: asyncio.AbstractEventLoop) -> AsyncIterator[ClientSession]:
    # Creates ONE server for ALL tests in module
```

**Key considerations for pytest-asyncio with module scope:**

1. **Event loop compatibility**: pytest-asyncio's default event loop scope is "function". For module-scoped async fixtures, we need to configure the event loop scope at the module level using `pytest.ini_options` or a conftest.py marker.

2. **Cleanup behavior**: The fixture will only clean up after all tests in the module complete, not after each test.

3. **Test isolation**: Tests must not leave state that affects other tests. This is acceptable because:
   - Tests are read-heavy (list_tools, ping, retrieve)
   - Write operations (store_memory) create unique records that don't conflict
   - The server uses a fresh Qdrant database on each startup anyway

**Implementation:**

Create a new `conftest.py` in `tests/integration/` to configure the event loop scope:

```python
"""Integration test configuration."""

import pytest

# Configure event loop scope for module-scoped async fixtures
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for integration tests."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
```

Update `test_mcp_protocol.py`:

```python
import pytest_asyncio

# Mark the module to use module-scoped event loop
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Create an MCP client session shared across all tests in this module."""
    # ... implementation unchanged, just the decorator changes
```

### Part 2: Single Model Load During Server Startup

Refactor the server startup to load the embedding model once and pass it to all consumers.

**Current flow (3 model loads):**
```
main()
  -> validate_configuration()     # Load #1: SentenceTransformer()
  -> run_server()
      -> initialize_collections() # Load #2: NomicEmbedding()
      -> create_server()
          -> register_all_tools()
              -> initialize_services() # Load #3: NomicEmbedding()
```

**Proposed flow (1 model load):**
```
main()
  -> create_embedding_service()   # Load: NomicEmbedding()
  -> validate_embedding()         # Just verify the loaded model
  -> run_server(embedding_service)
      -> initialize_collections(embedding_service)  # Reuse
      -> create_server(embedding_service)
          -> register_all_tools(embedding_service)  # Reuse
```

## Code Changes

### File: `src/learning_memory_server/server/main.py`

#### 1. Add new function to create and validate embedding service

```python
def create_embedding_service(settings: ServerSettings) -> NomicEmbedding:
    """Create the embedding service (loads model once).

    Args:
        settings: Server configuration

    Returns:
        Initialized NomicEmbedding service

    Raises:
        ValueError: If model loading fails
    """
    try:
        embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
        embedding_service = NomicEmbedding(settings=embedding_settings)
        logger.info("embedding_model.loaded", model=settings.embedding_model)
        return embedding_service
    except Exception as e:
        raise ValueError(
            f"Invalid embedding model '{settings.embedding_model}': {e}"
        ) from e
```

#### 2. Update `validate_configuration` to skip model loading

Remove the model loading from `validate_configuration()`:

```python
def validate_configuration(settings: ServerSettings) -> None:
    """Validate configuration before server start.

    Note: Embedding model validation happens separately in create_embedding_service().
    """
    # 1. Validate Qdrant connectivity (no tolerance per spec)
    # ... unchanged ...

    # 2. Validate paths are writable
    # ... unchanged (move this up since we removed model validation) ...

    # 3. Validate git repo if provided
    # ... unchanged ...
```

#### 3. Update `initialize_collections` signature

```python
async def initialize_collections(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> None:
    """Ensure all required collections exist.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service
    """
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    dimension = embedding_service.dimension

    # ... rest unchanged ...
```

#### 4. Update `create_server` signature

```python
def create_server(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> Server:
    """Create and configure the MCP server.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Returns:
        Configured MCP Server instance
    """
    server = Server("learning-memory-server")
    register_all_tools(server, settings, embedding_service)
    logger.info("server.created", server_name=server.name)
    return server
```

#### 5. Update `run_server` signature

```python
async def run_server(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> None:
    """Run the MCP server.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service
    """
    logger.info("server.starting")

    try:
        await initialize_collections(settings, embedding_service)
        logger.info("collections.initialized")
    except Exception as e:
        logger.error("collections.init_failed", error=str(e), exc_info=True)
        raise

    server = create_server(settings, embedding_service)
    # ... rest unchanged ...
```

#### 6. Update `main` function

```python
def main() -> None:
    """Entry point for the MCP server."""
    settings = ServerSettings()
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("learning_memory_server.starting", version="0.1.0")

    # Validate configuration (Qdrant, paths, git repo)
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Create embedding service (loads model ONCE)
    try:
        embedding_service = create_embedding_service(settings)
    except ValueError as e:
        logger.error("embedding.invalid", error=str(e))
        sys.exit(1)

    try:
        asyncio.run(run_server(settings, embedding_service))
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise
```

### File: `src/learning_memory_server/server/tools/__init__.py`

#### Update `initialize_services` to accept pre-initialized embedding service

```python
def initialize_services(
    settings: ServerSettings,
    embedding_service: EmbeddingService,
) -> ServiceContainer:
    """Initialize all services for MCP tools.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Returns:
        ServiceContainer with initialized services
    """
    logger.info("services.initializing")

    # Use provided embedding service (no more NomicEmbedding() call here)
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    metadata_store = MetadataStore(db_path=settings.sqlite_path)

    # ... rest unchanged, just use the passed embedding_service ...
```

#### Update `register_all_tools` signature

```python
def register_all_tools(
    server: Server,
    settings: ServerSettings,
    embedding_service: EmbeddingService,
) -> None:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
        embedding_service: Pre-initialized embedding service
    """
    services = initialize_services(settings, embedding_service)
    # ... rest unchanged ...
```

### File: `tests/integration/test_mcp_protocol.py`

#### Update fixture to module scope

```python
import pytest_asyncio

# Configure module-scoped event loop for async fixtures
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Create an MCP client session connected to the server.

    This fixture starts the actual server ONCE and all tests share it.
    Module scope dramatically improves test performance by avoiding
    repeated server startup (each takes ~5s for model loading).
    """
    # ... implementation mostly unchanged ...
```

## Alternative Approaches Considered

### 1. Lazy Loading of Embedding Model

**Approach**: Only load the embedding model on first actual use (first `embed()` call).

**Why rejected**:
- Delays the error to runtime instead of startup - spec prefers fail-fast
- Adds complexity (need to handle "not yet loaded" state)
- First user request would be slow (unexpected latency)

### 2. Parallelizing Tests Across Multiple Server Instances

**Approach**: Run tests in parallel with multiple server processes.

**Why rejected**:
- Significantly more complex (need port management, Qdrant isolation)
- Would still have slow startup times per process
- Overkill for 10 tests

### 3. Session-Scoped Test Fixture

**Approach**: Share server across ALL test modules, not just within one module.

**Why rejected**:
- Higher risk of test pollution between modules
- Other test modules may have different server requirements
- Module scope provides sufficient improvement

### 4. Caching Embedding Model to Disk

**Approach**: Cache loaded model to disk, reload from cache on startup.

**Why rejected**:
- `sentence-transformers` already caches the model files (~350MB)
- The slow part is model initialization/loading into memory, not download
- Would add significant complexity for marginal benefit

### 5. Keep validate_configuration() Model Load, Remove Others

**Approach**: Keep the validation load, just ensure others reuse it.

**Why rejected**:
- The validation code creates a raw `SentenceTransformer`, while the service uses `NomicEmbedding`
- Would require awkward type conversions or duplicate abstractions
- Cleaner to have one path: `NomicEmbedding` constructor is the single load point

## Testing Strategy

### 1. Verify Tests Still Pass

```bash
# Run MCP protocol tests
pytest tests/integration/test_mcp_protocol.py -v

# Run full test suite to ensure no regressions
pytest -v
```

### 2. Verify Performance Improvement

```bash
# Time the MCP protocol tests before and after
time pytest tests/integration/test_mcp_protocol.py --durations=0
```

**Expected results:**
- Before: ~130 seconds
- After: ~15-20 seconds (1 startup of ~6s + 10 tests of <1s each)

### 3. Verify Single Model Load

Add debug logging or check server logs to confirm model is loaded exactly once:

```bash
# Run server and grep for model load message
LOG_LEVEL=DEBUG learning-memory-server 2>&1 | grep "embedding_model"
# Should see exactly one "embedding_model.loaded" message
```

### 4. Verify Test Isolation

Run tests multiple times in different orders to ensure module-scoped fixture doesn't cause flaky behavior:

```bash
# Run tests in random order
pytest tests/integration/test_mcp_protocol.py --random-order -v

# Run specific test subsets
pytest tests/integration/test_mcp_protocol.py -k "test_store" -v
pytest tests/integration/test_mcp_protocol.py -k "test_retrieve" -v
```

## Edge Cases and Risks

### 1. Test Interdependencies

**Risk**: Tests may now affect each other since they share a server.

**Mitigation**:
- Current tests are mostly read-only (list_tools, ping)
- Write tests (store_memory) create unique records with UUIDs
- Qdrant collections are created fresh on server startup
- Add cleanup in fixture teardown if needed in future

### 2. Event Loop Compatibility

**Risk**: pytest-asyncio event loop scope changes could cause issues.

**Mitigation**:
- Explicitly configure `loop_scope="module"` in pytestmark
- Use `pytest_asyncio.fixture` instead of `pytest.fixture` for async fixtures
- Test with both sync and async tests in the same module

### 3. Server Process Cleanup

**Risk**: Server process may not be cleanly terminated.

**Mitigation**:
- Current fixture already has try/finally cleanup
- Module scope means cleanup runs once at end, which is simpler
- Process termination signals are handled correctly

### 4. Memory Usage

**Risk**: Long-running server process may accumulate memory.

**Mitigation**:
- Server is stateless (Qdrant is external)
- Only 10 tests, <1 minute total runtime
- Acceptable tradeoff for 8x speedup

### 5. Qdrant State

**Risk**: Qdrant collections may have stale data between tests.

**Mitigation**:
- Collections are created fresh on server startup
- Tests that modify data use unique identifiers
- Not a concern since server only starts once per test run

## Summary

| Change | Impact | Effort |
|--------|--------|--------|
| Module-scoped fixture | 10 startups -> 1 startup | Low |
| Single model load | ~15s startup -> ~5s startup | Medium |
| **Combined** | **~130s -> ~15s (~8x faster)** | **Medium** |

The changes are surgical and low-risk:
- Part 1 is a pytest configuration change
- Part 2 is a refactor that threads an existing object through function parameters

Both changes improve code quality beyond just performance:
- Tests are clearer about their scope
- Server startup code is more efficient and easier to understand
- Single responsibility: one place loads the model, others receive it
