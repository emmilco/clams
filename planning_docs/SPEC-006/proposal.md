# SPEC-006 Technical Proposal: Dual Embedding Model Support

## Overview

This proposal outlines the implementation of dual embedding model support to accelerate code indexing while maintaining quality for memory/GHAP operations. The system will use MiniLM (384-dim) for code and Nomic (768-dim) for semantic operations, with lazy loading to minimize memory overhead.

## Architecture

### 1. Embedding Service Registry

We'll introduce an `EmbeddingRegistry` class that manages two embedding services and provides lazy loading:

```python
# src/learning_memory_server/embedding/registry.py

class EmbeddingRegistry:
    """Singleton registry for dual embedding models.

    Provides lazy-loaded embedders by purpose:
    - Code embedder: Fast MiniLM (384-dim) for code indexing/search
    - Semantic embedder: Quality Nomic (768-dim) for memories/GHAP/clustering

    Models are loaded on first use and cached for the server's lifetime.
    Thread safety is not required since the MCP server is single-threaded asyncio.
    """

    def __init__(self) -> None:
        self._code_embedder: EmbeddingService | None = None
        self._semantic_embedder: EmbeddingService | None = None
        self._code_model_name: str = os.getenv(
            "LMS_CODE_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._semantic_model_name: str = os.getenv(
            "LMS_SEMANTIC_MODEL",
            "nomic-ai/nomic-embed-text-v1.5"
        )

    def get_code_embedder(self) -> EmbeddingService:
        """Get or create the code embedder (MiniLM, 384-dim)."""
        if self._code_embedder is None:
            settings = EmbeddingSettings(model_name=self._code_model_name)
            self._code_embedder = MiniLMEmbedding(settings=settings)
            logger.info("code_embedder.loaded", model=self._code_model_name)
        return self._code_embedder

    def get_semantic_embedder(self) -> EmbeddingService:
        """Get or create the semantic embedder (Nomic, 768-dim)."""
        if self._semantic_embedder is None:
            settings = EmbeddingSettings(model_name=self._semantic_model_name)
            self._semantic_embedder = NomicEmbedding(settings=settings)
            logger.info("semantic_embedder.loaded", model=self._semantic_model_name)
        return self._semantic_embedder

# Module-level singleton
_registry = EmbeddingRegistry()

def get_code_embedder() -> EmbeddingService:
    """Get the code embedder from the global registry."""
    return _registry.get_code_embedder()

def get_semantic_embedder() -> EmbeddingService:
    """Get the semantic embedder from the global registry."""
    return _registry.get_semantic_embedder()
```

**Design rationale:**
- Module-level singleton pattern matches MCP server lifecycle (single process, no fork/spawn)
- Lazy loading prevents both models loading at startup (saves ~2-3 seconds + memory)
- No thread safety needed (MCP server is single-threaded asyncio)
- Environment variables allow override for testing/experimentation
- Function exports (`get_code_embedder()`, `get_semantic_embedder()`) provide clean API

### 2. MiniLM Embedding Implementation

Create `src/learning_memory_server/embedding/minilm.py`:

```python
class MiniLMEmbedding(EmbeddingService):
    """MiniLM embedding service using sentence-transformers.

    Uses sentence-transformers/all-MiniLM-L6-v2 by default, producing
    384-dimensional embeddings. Optimized for speed while maintaining
    acceptable quality for code search.

    Attributes:
        model: The loaded SentenceTransformer model
        settings: Configuration settings for the embedding service
    """

    _DIMENSION = 384

    def __init__(self, settings: EmbeddingSettings | None = None) -> None:
        """Initialize the MiniLM embedding service.

        Args:
            settings: Configuration settings (uses defaults if not provided)

        Raises:
            EmbeddingModelError: If model loading fails
        """
        self.settings = settings or EmbeddingSettings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        try:
            self.model = SentenceTransformer(
                self.settings.model_name,
                cache_folder=self.settings.cache_dir,
                trust_remote_code=True,
            )
            # Force CPU to avoid MPS memory leak (same as Nomic)
            if torch.backends.mps.is_available():
                self.model = self.model.to(torch.device("cpu"))
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to load model {self.settings.model_name}: {e}"
            ) from e

    # embed() and embed_batch() implementations identical to NomicEmbedding
    # except _DIMENSION = 384
```

**Design rationale:**
- Identical structure to `NomicEmbedding` for consistency
- Reuses MPS workaround (BUG-014 fix applies to all sentence-transformers models)
- 384-dim matches benchmark results and model spec
- Default model name in constructor allows override via `EmbeddingSettings`

### 3. Service Container Updates

Modify `src/learning_memory_server/server/tools/__init__.py`:

**Current state:**
```python
async def initialize_services(
    settings: ServerSettings,
    embedding_service: EmbeddingService,  # Single service passed in
) -> ServiceContainer:
    # Uses provided embedding_service for all tools
```

**Proposed change:**
```python
async def initialize_services(
    settings: ServerSettings,
    code_embedder: EmbeddingService,
    semantic_embedder: EmbeddingService,
) -> ServiceContainer:
    """Initialize all services for MCP tools.

    Args:
        settings: Server configuration
        code_embedder: Embedding service for code indexing/search (MiniLM)
        semantic_embedder: Embedding service for memories/GHAP (Nomic)

    Returns:
        ServiceContainer with initialized services
    """
    logger.info("services.initializing")

    # Core infrastructure
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    metadata_store = MetadataStore(db_path=settings.sqlite_path)
    await metadata_store.initialize()

    # Code indexing - uses code_embedder (MiniLM)
    code_indexer = None
    try:
        from learning_memory_server.indexers import CodeIndexer, TreeSitterParser
        code_parser = TreeSitterParser()
        code_indexer = CodeIndexer(
            parser=code_parser,
            embedding_service=code_embedder,  # MiniLM for speed
            vector_store=vector_store,
            metadata_store=metadata_store,
        )
        logger.info("code.initialized", model="MiniLM")
    except ImportError as e:
        logger.warning("code.init_skipped", reason="module_not_found", error=str(e))

    # Git analysis - uses semantic_embedder (Nomic)
    git_analyzer = None
    if repo_path_to_use:
        try:
            from learning_memory_server.git import GitAnalyzer, GitPythonReader
            git_reader = GitPythonReader(repo_path=repo_path_to_use)
            git_analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=semantic_embedder,  # Nomic for quality
                vector_store=vector_store,
                metadata_store=metadata_store,
            )
            logger.info("git.initialized", model="Nomic")
        except Exception as e:
            logger.warning("git.init_failed", error=str(e))

    # ServiceContainer stores both embedders
    return ServiceContainer(
        code_embedder=code_embedder,
        semantic_embedder=semantic_embedder,
        vector_store=vector_store,
        metadata_store=metadata_store,
        code_indexer=code_indexer,
        git_analyzer=git_analyzer,
    )
```

**ServiceContainer changes:**
```python
@dataclass
class ServiceContainer:
    """Container for shared services used by MCP tools."""

    code_embedder: EmbeddingService        # NEW: MiniLM for code
    semantic_embedder: EmbeddingService    # NEW: Nomic for memories/GHAP
    vector_store: VectorStore
    metadata_store: MetadataStore
    code_indexer: object | None = None
    git_analyzer: object | None = None
    searcher: object | None = None
```

**Tool registration updates:**
```python
async def register_all_tools(
    server: Server,
    settings: ServerSettings,
    code_embedder: EmbeddingService,
    semantic_embedder: EmbeddingService,
) -> ServiceContainer:
    """Register all MCP tools with the server."""

    services = await initialize_services(settings, code_embedder, semantic_embedder)

    # GHAP tools - use semantic_embedder
    observation_persister = ObservationPersister(
        embedding_service=services.semantic_embedder,  # Nomic
        vector_store=services.vector_store,
    )

    # Learning tools - use semantic_embedder
    value_store = ValueStore(
        embedding_service=services.semantic_embedder,  # Nomic
        vector_store=services.vector_store,
        clusterer=experience_clusterer,
    )

    # Search tools - use semantic_embedder
    searcher = Searcher(
        embedding_service=services.semantic_embedder,  # Nomic
        vector_store=services.vector_store,
    )

    # Memory tools already use services.semantic_embedder

    return services
```

### 4. Server Main Updates

Modify `src/learning_memory_server/server/main.py`:

**Current state:**
```python
def create_embedding_service(settings: ServerSettings) -> NomicEmbedding:
    """Create the embedding service (loads model once)."""
    embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
    embedding_service = NomicEmbedding(settings=embedding_settings)
    return embedding_service

def main() -> None:
    settings = ServerSettings()
    embedding_service = create_embedding_service(settings)
    asyncio.run(run_server(settings, embedding_service))
```

**Proposed change:**
```python
def main() -> None:
    """Entry point for the MCP server."""
    settings = ServerSettings()
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info("learning_memory_server.starting", version="0.1.0")

    # Validate configuration
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # NO MODEL LOADING HERE - models load lazily on first tool use

    try:
        asyncio.run(run_server(settings))
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise

async def run_server(settings: ServerSettings) -> None:
    """Run the MCP server."""
    logger.info("server.starting")

    # Import registry functions
    from learning_memory_server.embedding.registry import (
        get_code_embedder,
        get_semantic_embedder,
    )

    # Get lazy-loaded embedders (don't call yet - will load on first tool use)
    # Pass functions to create_server, which calls them as needed
    code_embedder_fn = get_code_embedder
    semantic_embedder_fn = get_semantic_embedder

    # Initialize collections (needs to handle dynamic dimensions)
    await initialize_collections(settings, code_embedder_fn, semantic_embedder_fn)

    # Create server with embedder functions
    server, services = await create_server(settings, code_embedder_fn(), semantic_embedder_fn())

    # ... rest unchanged

async def initialize_collections(
    settings: ServerSettings,
    code_embedder_fn: Callable[[], EmbeddingService],
    semantic_embedder_fn: Callable[[], EmbeddingService],
) -> None:
    """Ensure all required collections exist.

    Collections are created with appropriate dimensions:
    - code_units: 384-dim (MiniLM)
    - memories, commits, GHAP axes, values: 768-dim (Nomic)
    """
    vector_store = QdrantVectorStore(url=settings.qdrant_url)

    # Code collections use MiniLM dimensions
    code_embedder = code_embedder_fn()  # Triggers lazy load
    await _create_collection_if_needed(vector_store, "code_units", code_embedder.dimension)

    # Semantic collections use Nomic dimensions
    semantic_embedder = semantic_embedder_fn()  # Triggers lazy load
    for collection_name in ["memories", "commits", "ghap_full", "ghap_strategy",
                            "ghap_surprise", "ghap_root_cause", "values"]:
        await _create_collection_if_needed(vector_store, collection_name, semantic_embedder.dimension)

async def _create_collection_if_needed(
    vector_store: VectorStore,
    name: str,
    dimension: int
) -> None:
    """Create collection if it doesn't exist."""
    try:
        await vector_store.create_collection(name=name, dimension=dimension)
        logger.info("collection.created", name=name, dimension=dimension)
    except Exception as e:
        if "already exists" in str(e) or "409" in str(e):
            logger.debug("collection.exists", name=name)
        else:
            logger.error("collection.create_failed", name=name, error=str(e))
            raise
```

**Design rationale:**
- Models load during `initialize_collections()`, not at startup
- First tool call triggers model load via registry
- `ping` tool will NOT load any models (validates lazy loading)
- Collection dimensions determined by embedder type

### 5. Code Units Collection Migration

The `CodeIndexer._ensure_collection()` method already has logic to create collections. We'll enhance it to handle dimension mismatches:

```python
async def _ensure_collection(self) -> None:
    """Create collection if it doesn't exist, recreate if dimension mismatches.

    Automatically migrates from 768-dim (Nomic) to 384-dim (MiniLM) by
    recreating the collection. User's next index_codebase call will repopulate.
    """
    if self._collection_ensured:
        return

    try:
        # Check if collection exists and verify dimension
        try:
            info = await self.vector_store.get_collection_info(self.COLLECTION_NAME)
            if info and info.dimension != self.embedding_service.dimension:
                logger.warning(
                    "dimension_mismatch",
                    collection=self.COLLECTION_NAME,
                    expected=self.embedding_service.dimension,
                    actual=info.dimension,
                    action="recreating_collection"
                )
                await self.vector_store.delete_collection(self.COLLECTION_NAME)
        except Exception:
            # Collection doesn't exist - that's fine
            pass

        # Create with correct dimension
        await self.vector_store.create_collection(
            name=self.COLLECTION_NAME,
            dimension=self.embedding_service.dimension,
        )
        logger.info("collection_created", name=self.COLLECTION_NAME,
                   dimension=self.embedding_service.dimension)
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "409" in str(e):
            logger.debug("collection_exists", name=self.COLLECTION_NAME)
        else:
            raise

    self._collection_ensured = True
```

**Migration flow:**
1. User upgrades to SPEC-006 implementation
2. First `index_codebase` call checks collection
3. Finds 768-dim collection (from old Nomic embeddings)
4. Logs warning and deletes collection
5. Recreates with 384-dim
6. Indexing proceeds normally with MiniLM

**Note:** We need to add `get_collection_info()` to the `VectorStore` protocol if it doesn't exist.

### 6. Vector Store Protocol Extension

Add to `src/learning_memory_server/storage/base.py`:

```python
@dataclass
class CollectionInfo:
    """Information about a vector collection."""
    name: str
    dimension: int
    vector_count: int

class VectorStore(ABC):
    """Abstract base for vector storage operations."""

    # ... existing methods

    @abstractmethod
    async def get_collection_info(self, name: str) -> CollectionInfo | None:
        """Get collection metadata.

        Args:
            name: Collection name

        Returns:
            CollectionInfo if collection exists, None otherwise
        """
        ...
```

Implement in `QdrantVectorStore`:

```python
async def get_collection_info(self, name: str) -> CollectionInfo | None:
    """Get collection metadata from Qdrant."""
    try:
        collection = await self.client.get_collection(name)
        return CollectionInfo(
            name=name,
            dimension=collection.config.params.vectors.size,
            vector_count=collection.points_count,
        )
    except Exception:
        return None
```

## Files Modified

### New Files
1. `src/learning_memory_server/embedding/registry.py` - Embedding registry implementation
2. `src/learning_memory_server/embedding/minilm.py` - MiniLM embedding service

### Modified Files
1. `src/learning_memory_server/embedding/__init__.py` - Export new classes
2. `src/learning_memory_server/embedding/base.py` - Add `CollectionInfo` (optional)
3. `src/learning_memory_server/storage/base.py` - Add `get_collection_info()` to protocol
4. `src/learning_memory_server/storage/qdrant.py` - Implement `get_collection_info()`
5. `src/learning_memory_server/indexers/indexer.py` - Add dimension mismatch handling
6. `src/learning_memory_server/server/tools/__init__.py` - Dual embedder support
7. `src/learning_memory_server/server/main.py` - Lazy loading, remove upfront model creation
8. `src/learning_memory_server/server/config.py` - Add code/semantic model config (optional)

### Test Files to Create/Modify
1. `tests/embedding/test_minilm.py` - MiniLM implementation tests
2. `tests/embedding/test_registry.py` - Registry lazy loading tests
3. `tests/indexers/test_indexer.py` - Add dimension migration test
4. `tests/integration/test_dual_embeddings.py` - End-to-end test with both models

## Dependencies

No new dependencies required:
- `sentence-transformers` already in `pyproject.toml`
- MiniLM model auto-downloads via `sentence-transformers` on first use
- Model size: ~90MB (vs Nomic's ~500MB)

## Configuration

### Environment Variables (Optional)

Users can override models for testing/experimentation:

```bash
# Use different code model (must be 384-dim compatible)
export LMS_CODE_MODEL="sentence-transformers/paraphrase-MiniLM-L6-v2"

# Use different semantic model (must be 768-dim compatible)
export LMS_SEMANTIC_MODEL="nomic-ai/nomic-embed-text-v1.5"
```

### Server Settings (Optional Enhancement)

Could add to `ServerSettings` for discoverability:

```python
class ServerSettings(BaseSettings):
    # ... existing settings

    # Embedding models (overridable via LMS_CODE_MODEL, LMS_SEMANTIC_MODEL)
    code_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model: str = "nomic-ai/nomic-embed-text-v1.5"
```

Then registry reads from settings instead of direct `os.getenv()`.

**Decision point:** Do we want settings-based config or just environment variables?

## Test Strategy

### Unit Tests

1. **MiniLM Implementation** (`test_minilm.py`)
   - Test embedding generation (single + batch)
   - Verify 384-dim output
   - Test MPS CPU fallback
   - Test error handling

2. **Registry** (`test_registry.py`)
   - Test lazy loading (model not loaded until first call)
   - Test caching (same instance returned on repeated calls)
   - Test environment variable override
   - Test error propagation from model loading

3. **Dimension Migration** (`test_indexer.py`)
   - Create 768-dim collection
   - Initialize indexer with 384-dim embedder
   - Verify collection recreated with correct dimension
   - Verify re-indexing works

### Integration Tests

1. **Dual Embeddings E2E** (`test_dual_embeddings.py`)
   - Index code with MiniLM (verify 384-dim vectors)
   - Store memory with Nomic (verify 768-dim vectors)
   - Search code (verify results)
   - Retrieve memories (verify results)
   - Verify both models loaded after use
   - Verify `ping` doesn't load models

2. **Performance Benchmark** (existing `tests/performance/benchmark_indexing.py`)
   - Run code indexing benchmark
   - Verify <60s for clams repo (155 files, 986 units)
   - Compare to baseline (currently 3.4 min)

### Manual Verification

1. Start server, call `ping`, verify no model load logs
2. Call `index_codebase`, verify MiniLM loads, indexing fast
3. Call `store_memory`, verify Nomic loads
4. Check Qdrant collections: `code_units` is 384-dim, `memories` is 768-dim

## Migration Path

### For Existing Deployments

**On upgrade:**
1. First `index_codebase` call detects 768-dim `code_units` collection
2. Logs warning: "dimension_mismatch: recreating collection"
3. Deletes old collection
4. Creates new 384-dim collection
5. Re-indexes all files (user-initiated, part of normal `index_codebase` call)

**Impact:**
- Zero downtime (collection recreate is atomic)
- No manual intervention required
- Existing memory/GHAP data unaffected (remains 768-dim)
- Code search temporarily returns empty results until re-indexed

**User communication:**
- Update CHANGELOG.md to note automatic migration
- Document that code needs re-indexing after upgrade

### Rollback

If issues arise:
1. Stop server
2. Manually delete 384-dim `code_units` collection via Qdrant API
3. Revert code to previous version
4. Restart server
5. Re-index code (creates 768-dim collection)

## Performance Expectations

Based on benchmark results in spec:

**Before (Nomic):**
- Code indexing: ~230ms per unit
- Clams repo (986 units): ~3.4 minutes

**After (MiniLM):**
- Code indexing: ~37ms per unit (6.2x faster)
- Clams repo (986 units): ~33 seconds (6x improvement)

**Target:** <60 seconds for clams repo indexing

**Memory:**
- Typical usage: One model loaded (~500MB-1GB)
- Worst case: Both models loaded (~1.5GB total)
- Acceptable for server workload

## Risk Mitigation

### Quality Regression
- **Risk:** MiniLM code search quality lower than Nomic
- **Mitigation:** Benchmark shows 95% MRR (9/10 vs 10/10 hits@1) - acceptable
- **Fallback:** Environment variable allows reverting to Nomic for code

### Memory Issues
- **Risk:** Both models load, excessive memory usage
- **Mitigation:** Lazy loading prevents both loading unless both tool types used
- **Monitoring:** Log model loads, track memory usage in production

### Dimension Mismatch Bugs
- **Risk:** Wrong embedder used for collection, dimension mismatch errors
- **Mitigation:** Type system enforces correct embedder wiring
- **Testing:** Integration test verifies correct embedder per tool
- **Migration:** Auto-detect and recreate mismatched collections

### Collection Recreation Data Loss
- **Risk:** Dimension mismatch deletes collection, data lost
- **Mitigation:** Code indexing is transient (user re-indexes on demand)
- **Note:** Memories/GHAP unaffected (no dimension change)

## Open Questions

1. **Settings vs Environment Variables:** Should model names be in `ServerSettings` or just environment variables?
   - Recommendation: Settings for discoverability, env vars for override

2. **Collection Info Method:** Should `get_collection_info()` be added to base `VectorStore` protocol or just Qdrant?
   - Recommendation: Add to protocol for consistency, implement in both stores

3. **Migration Logging Level:** Should dimension mismatch be WARNING or INFO?
   - Recommendation: WARNING - it's unexpected but handled, user should know

4. **Embedder Function vs Instance:** Should `initialize_collections()` take embedder functions or instances?
   - Recommendation: Call functions to trigger lazy load explicitly, clearer intent

## Implementation Order

1. **Phase 1: Core Implementation**
   - Add `MiniLMEmbedding` class
   - Add `EmbeddingRegistry` class
   - Update embedding module exports

2. **Phase 2: Infrastructure**
   - Add `get_collection_info()` to VectorStore protocol
   - Implement in QdrantVectorStore
   - Update `CodeIndexer._ensure_collection()` for migration

3. **Phase 3: Service Wiring**
   - Update `ServiceContainer` to hold both embedders
   - Update `initialize_services()` to use dual embedders
   - Update `register_all_tools()` to wire correct embedder per tool

4. **Phase 4: Server Startup**
   - Remove upfront model loading from `main.py`
   - Update `initialize_collections()` for lazy loading
   - Update `create_server()` signature

5. **Phase 5: Testing**
   - Unit tests for MiniLM
   - Unit tests for registry
   - Integration test for dual embeddings
   - Performance benchmark verification

6. **Phase 6: Documentation**
   - Update README if needed
   - Add CHANGELOG entry
   - Document migration behavior

## Success Criteria

1. Code indexing completes in <60s for clams repo (currently 3.4 min)
2. Existing memory/GHAP search continues to work (no quality regression)
3. `ping` tool does NOT load any models (validates lazy loading)
4. Dimension mismatch triggers automatic collection recreation
5. Both models can load and run simultaneously if needed
6. All tests pass, mypy strict mode, ruff clean
7. Integration test verifies correct embedder per tool type
