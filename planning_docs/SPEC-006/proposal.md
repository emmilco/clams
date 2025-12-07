# SPEC-006 Technical Proposal: Dual Embedding Model Support

## Revision Summary

**Revision 3 - Addresses Human Feedback**

This revision addresses feedback from human review:

1. **Removed backward compatibility:** Eliminated `embedding_service` property from `ServiceContainer`. No users exist, so no need for compatibility shims. Tools use `code_embedder` or `semantic_embedder` directly.

2. **Abstracted model-specific constants:** Removed all hardcoded model names and dimensions. Model names come from `ServerSettings` (configurable via env vars). Dimensions queried from loaded model at runtime via `embedding_service.dimension`.

## Overview

This proposal outlines the implementation of dual embedding model support to accelerate code indexing while maintaining quality for memory/GHAP operations. The system uses separate models for code (optimized for speed) and semantic operations (optimized for quality), with lazy loading to minimize memory overhead. Default models are MiniLM for code and Nomic for semantic operations, both configurable via environment variables.

## Architecture

### 1. Embedding Service Registry

We'll introduce an `EmbeddingRegistry` class that manages two embedding services and provides lazy loading:

```python
# src/learning_memory_server/embedding/registry.py

class EmbeddingRegistry:
    """Singleton registry for dual embedding models.

    Provides lazy-loaded embedders by purpose:
    - Code embedder: Fast model (configurable) for code indexing/search
    - Semantic embedder: Quality model (configurable) for memories/GHAP/clustering

    Models are loaded on first use and cached for the server's lifetime.
    Thread safety is not required since the MCP server is single-threaded asyncio.
    Model names and dimensions determined by ServerSettings.
    """

    def __init__(self, settings: ServerSettings) -> None:
        self._code_embedder: EmbeddingService | None = None
        self._semantic_embedder: EmbeddingService | None = None
        self._settings = settings

    def get_code_embedder(self) -> EmbeddingService:
        """Get or create the code embedder (configured via settings)."""
        if self._code_embedder is None:
            embedding_settings = EmbeddingSettings(model_name=self._settings.code_model)
            self._code_embedder = MiniLMEmbedding(settings=embedding_settings)
            logger.info("code_embedder.loaded",
                       model=self._settings.code_model,
                       dimension=self._code_embedder.dimension)
        return self._code_embedder

    def get_semantic_embedder(self) -> EmbeddingService:
        """Get or create the semantic embedder (configured via settings)."""
        if self._semantic_embedder is None:
            embedding_settings = EmbeddingSettings(model_name=self._settings.semantic_model)
            self._semantic_embedder = NomicEmbedding(settings=embedding_settings)
            logger.info("semantic_embedder.loaded",
                       model=self._settings.semantic_model,
                       dimension=self._semantic_embedder.dimension)
        return self._semantic_embedder

# Module-level singleton (initialized in main.py with settings)
_registry: EmbeddingRegistry | None = None

def initialize_registry(settings: ServerSettings) -> None:
    """Initialize the global registry with settings.

    Must be called from main.py before any tool uses embedders.
    """
    global _registry
    _registry = EmbeddingRegistry(settings)

def get_code_embedder() -> EmbeddingService:
    """Get the code embedder from the global registry."""
    if _registry is None:
        raise RuntimeError("Registry not initialized. Call initialize_registry() first.")
    return _registry.get_code_embedder()

def get_semantic_embedder() -> EmbeddingService:
    """Get the semantic embedder from the global registry."""
    if _registry is None:
        raise RuntimeError("Registry not initialized. Call initialize_registry() first.")
    return _registry.get_semantic_embedder()
```

**Design rationale:**
- Module-level singleton pattern matches MCP server lifecycle (single process, no fork/spawn)
- Lazy loading prevents both models loading at startup (saves ~2-3 seconds + memory)
- No thread safety needed (MCP server is single-threaded asyncio)
- Settings-based configuration for discoverability, environment variables for override
- Function exports (`get_code_embedder()`, `get_semantic_embedder()`) provide clean API
- Explicit initialization prevents accidental use before settings available

### 2. MiniLM Embedding Implementation

Create `src/learning_memory_server/embedding/minilm.py`:

```python
class MiniLMEmbedding(EmbeddingService):
    """MiniLM embedding service using sentence-transformers.

    Model and dimension determined by settings. Optimized for speed while
    maintaining acceptable quality for code search.

    Attributes:
        model: The loaded SentenceTransformer model
        settings: Configuration settings for the embedding service
    """

    def __init__(self, settings: EmbeddingSettings) -> None:
        """Initialize the MiniLM embedding service.

        Args:
            settings: Configuration settings (model_name required)

        Raises:
            EmbeddingModelError: If model loading fails
        """
        self.settings = settings
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

    @property
    def dimension(self) -> int:
        """Get embedding dimension from the loaded model."""
        return self.model.get_sentence_embedding_dimension()

    # embed() and embed_batch() implementations identical to NomicEmbedding
```

**Design rationale:**
- Identical structure to `NomicEmbedding` for consistency
- Reuses MPS workaround (BUG-014 fix applies to all sentence-transformers models)
- Dimension queried from model at runtime (no hardcoded constants)
- Model name comes from settings (configured via `ServerSettings` and env vars)

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
            embedding_service=code_embedder,  # Fast model for speed
            vector_store=vector_store,
            metadata_store=metadata_store,
        )
        logger.info("code.initialized")
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
            logger.info("git.initialized")
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

    code_embedder: EmbeddingService        # For code indexing/search
    semantic_embedder: EmbeddingService    # For memories/GHAP/commits
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

    # Initialize embedding registry (does NOT load models)
    from learning_memory_server.embedding.registry import initialize_registry
    initialize_registry(settings)
    logger.info("embedding_registry.initialized")

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

    # Create server with embedder accessor functions
    # Models load lazily when first tool calls these functions
    server, services = await create_server(settings, get_code_embedder, get_semantic_embedder)

    # ... rest unchanged (run server, etc.)
```

**Design rationale:**
- Registry initialized at startup with settings, but models NOT loaded
- No `initialize_collections()` at startup - collections created lazily by each tool type
- Tools call `_ensure_collection()` on first use, which loads model and creates collection
- `ping` tool does NOT load any models (validates lazy loading)
- Collection dimensions determined by embedder type when collection is created

### 5. Lazy Collection Creation per Tool Type

Each tool type creates its collection lazily via `_ensure_collection()` pattern. We'll enhance `CodeIndexer._ensure_collection()` to handle dimension mismatches:

```python
class CodeIndexer:
    """Indexes code into vector storage for semantic search."""

    COLLECTION_NAME = "code_units"  # Consistent name used everywhere

    async def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist, recreate if dimension mismatches.

        Automatically migrates from 768-dim (Nomic) to 384-dim (MiniLM) by
        recreating the collection. User's next index_codebase call will repopulate.

        This is called on first indexing operation (lazy creation).
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

**Similar pattern for other tools:**
- `MemoryStore._ensure_collection()` → creates "memories" collection (uses semantic_embedder.dimension)
- `GitAnalyzer._ensure_collection()` → creates "commits" collection (uses semantic_embedder.dimension)
- `ObservationPersister._ensure_collection()` → creates GHAP axis collections (uses semantic_embedder.dimension)
- `ValueStore._ensure_collection()` → creates "values" collection (uses semantic_embedder.dimension)

**Migration flow:**
1. User upgrades to SPEC-006 implementation
2. First `index_codebase` call triggers `CodeIndexer._ensure_collection()`
3. Finds collection with mismatched dimension (old Nomic embeddings vs new code_embedder)
4. Logs warning and deletes collection
5. Recreates with correct dimension from `code_embedder.dimension`
6. Indexing proceeds normally with configured code embedder
7. Other tool types (memories, GHAP) continue using semantic embedder unchanged

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

        Raises:
            Exception: For network/connection errors (NOT for missing collections)
        """
        ...
```

Implement in `QdrantVectorStore`:

```python
async def get_collection_info(self, name: str) -> CollectionInfo | None:
    """Get collection metadata from Qdrant.

    Args:
        name: Collection name

    Returns:
        CollectionInfo if collection exists, None if not found

    Raises:
        Exception: For Qdrant connection/network errors
    """
    try:
        collection = await self.client.get_collection(name)
        return CollectionInfo(
            name=name,
            dimension=collection.config.params.vectors.size,
            vector_count=collection.points_count,
        )
    except Exception as e:
        # Distinguish between "not found" vs real errors
        if "not found" in str(e).lower() or "404" in str(e):
            return None
        # Re-raise connection/network errors
        raise
```

Implement in `InMemoryVectorStore`:

```python
async def get_collection_info(self, name: str) -> CollectionInfo | None:
    """Get collection metadata from in-memory storage.

    Args:
        name: Collection name

    Returns:
        CollectionInfo if collection exists, None if not found
    """
    if name not in self.collections:
        return None

    collection = self.collections[name]
    return CollectionInfo(
        name=name,
        dimension=collection["dimension"],
        vector_count=len(collection["vectors"]),
    )
```

**Design notes:**
- Protocol defines clear error handling contract: None for missing, exception for errors
- Implementations distinguish "not found" from connection/network failures
- In-memory implementation is simple (no network errors possible)
- Used by `_ensure_collection()` to detect dimension mismatches

## Files Modified

### New Files
1. `src/learning_memory_server/embedding/registry.py` - Embedding registry implementation
2. `src/learning_memory_server/embedding/minilm.py` - MiniLM embedding service

### Modified Files
1. `src/learning_memory_server/embedding/__init__.py` - Export new classes
2. `src/learning_memory_server/storage/base.py` - Add `CollectionInfo` dataclass and `get_collection_info()` to protocol
3. `src/learning_memory_server/storage/qdrant.py` - Implement `get_collection_info()`
4. `src/learning_memory_server/storage/memory.py` - Implement `get_collection_info()` for in-memory store
5. `src/learning_memory_server/indexers/indexer.py` - Update `COLLECTION_NAME`, add dimension mismatch handling
6. `src/learning_memory_server/server/tools/__init__.py` - Dual embedder support, add `embedding_service` property
7. `src/learning_memory_server/server/main.py` - Registry initialization, remove upfront model creation
8. `src/learning_memory_server/server/config.py` - Add `code_model` and `semantic_model` settings

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

### Server Settings

Add to `src/learning_memory_server/server/config.py`:

```python
class ServerSettings(BaseSettings):
    """Server configuration settings."""

    # ... existing settings (qdrant_url, sqlite_path, etc.)

    # Embedding models (overridable via environment variables)
    code_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Model for code indexing (optimized for speed)",
        env="LMS_CODE_MODEL",
    )
    semantic_model: str = Field(
        default="nomic-ai/nomic-embed-text-v1.5",
        description="Model for memories/GHAP (optimized for quality)",
        env="LMS_SEMANTIC_MODEL",
    )
```

### Environment Variables

Users can override models for testing/experimentation:

```bash
# Use different code model (any sentence-transformers compatible model)
export LMS_CODE_MODEL="sentence-transformers/paraphrase-MiniLM-L6-v2"

# Use different semantic model (any sentence-transformers compatible model)
export LMS_SEMANTIC_MODEL="sentence-transformers/all-mpnet-base-v2"
```

**Benefits of ServerSettings approach:**
- Centralized configuration with defaults
- Environment variable override support via `env` parameter
- Type checking and validation via Pydantic
- Discoverability (developers can see all config options)
- Registry receives settings object, cleaner than direct `os.getenv()`

## Test Strategy

### Unit Tests

1. **MiniLM Implementation** (`test_minilm.py`)
   - Test embedding generation (single + batch)
   - Verify dimension matches model spec (query from model)
   - Test MPS CPU fallback
   - Test error handling

2. **Registry** (`test_registry.py`)
   - Test lazy loading (model not loaded until first call)
   - Test caching (same instance returned on repeated calls)
   - Test environment variable override
   - Test error propagation from model loading

3. **Dimension Migration** (`test_indexer.py`)
   - Create collection with one dimension
   - Initialize indexer with embedder of different dimension
   - Verify collection recreated with embedder's dimension
   - Verify re-indexing works

### Integration Tests

1. **Dual Embeddings E2E** (`test_dual_embeddings.py`)
   - Index code with code_embedder (verify vectors match embedder dimension)
   - Store memory with semantic_embedder (verify vectors match embedder dimension)
   - Search code (verify results)
   - Retrieve memories (verify results)
   - Verify both models loaded after use
   - Verify `ping` doesn't load models

2. **Performance Benchmark** (existing `tests/performance/benchmark_indexing.py`)
   - Run code indexing benchmark with configured code model
   - Verify <60s for clams repo (155 files, 986 units)
   - Compare to baseline (currently 3.4 min with Nomic)

### Manual Verification

1. Start server, call `ping`, verify no model load logs
2. Call `index_codebase`, verify code model loads, indexing fast
3. Call `store_memory`, verify semantic model loads
4. Check Qdrant collections have correct dimensions matching their embedders

## Migration Path

### For Existing Deployments

**On upgrade:**
1. First `index_codebase` call detects dimension mismatch in `code_units` collection
2. Logs warning: "dimension_mismatch: recreating collection"
3. Deletes old collection
4. Creates new collection with code_embedder's dimension
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
2. Manually delete `code_units` collection via Qdrant API
3. Revert code to previous version
4. Restart server
5. Re-index code (creates collection with previous embedder's dimension)

## Performance Expectations

Based on benchmark results in spec (using default models):

**Before (Nomic for code):**
- Code indexing: ~230ms per unit
- Clams repo (986 units): ~3.4 minutes

**After (MiniLM for code):**
- Code indexing: ~37ms per unit (6.2x faster)
- Clams repo (986 units): ~33 seconds (6x improvement)

**Target:** <60 seconds for clams repo indexing with default code model

**Memory:**
- Typical usage: One model loaded (~500MB-1GB)
- Worst case: Both models loaded (~1.5GB total)
- Acceptable for server workload

## Risk Mitigation

### Quality Regression
- **Risk:** Default code model (MiniLM) has lower quality than semantic model (Nomic)
- **Mitigation:** Benchmark shows 95% MRR (9/10 vs 10/10 hits@1) - acceptable for code
- **Fallback:** Environment variable allows using semantic model for code if needed

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

## Resolved Design Decisions

Based on proposal review and human feedback, these decisions have been made:

1. **Settings vs Environment Variables:** ✅ RESOLVED
   - Using `ServerSettings` with `code_model` and `semantic_model` fields
   - Environment variables (`LMS_CODE_MODEL`, `LMS_SEMANTIC_MODEL`) for override via Pydantic `env` parameter
   - Registry receives settings object, not direct `os.getenv()` calls

2. **Collection Info Method:** ✅ RESOLVED
   - Added `get_collection_info()` to base `VectorStore` protocol
   - Implemented in both `QdrantVectorStore` and `InMemoryVectorStore`
   - Clear error handling contract: None for missing, exception for errors

3. **Migration Logging Level:** ✅ RESOLVED
   - Using WARNING level for dimension mismatch
   - It's unexpected but handled automatically - user should be aware

4. **Lazy Loading vs Upfront Initialization:** ✅ RESOLVED
   - No `initialize_collections()` at startup
   - Each tool type creates its collection lazily via `_ensure_collection()` on first use
   - Registry initialized at startup, but models load on first tool use
   - `ping` tool will NOT load any models (validates lazy loading)

5. **Backward Compatibility:** ✅ RESOLVED (Revision 3)
   - NO backward compatibility needed - no users exist
   - Removed `embedding_service` property from `ServiceContainer`
   - Tools use `code_embedder` or `semantic_embedder` directly

6. **Collection Name Consistency:** ✅ RESOLVED
   - Using `"code_units"` everywhere (constant `CodeIndexer.COLLECTION_NAME`)
   - No mismatch between initialization and indexer

7. **Model-Specific Constants:** ✅ RESOLVED (Revision 3)
   - NO hardcoded model names outside `ServerSettings` defaults
   - NO hardcoded dimensions - all queried from loaded model via `dimension` property
   - Configuration-driven design enables easy model swapping

## Implementation Order

1. **Phase 1: Configuration**
   - Add `code_model` and `semantic_model` to `ServerSettings`
   - Verify Pydantic environment variable override works

2. **Phase 2: Core Embedding**
   - Add `MiniLMEmbedding` class (with MPS CPU fallback)
   - Add `EmbeddingRegistry` class (takes `ServerSettings`)
   - Update embedding module exports

3. **Phase 3: Vector Store Protocol**
   - Add `CollectionInfo` dataclass to storage base
   - Add `get_collection_info()` to `VectorStore` protocol
   - Implement in `QdrantVectorStore`
   - Implement in `InMemoryVectorStore`

4. **Phase 4: Collection Management**
   - Update `CodeIndexer.COLLECTION_NAME` to `"code_units"`
   - Update `CodeIndexer._ensure_collection()` for dimension migration
   - Verify other tools have `_ensure_collection()` pattern

5. **Phase 5: Service Container**
   - Update `ServiceContainer` to hold both embedders (`code_embedder`, `semantic_embedder`)
   - Update `initialize_services()` to use dual embedders
   - Update `register_all_tools()` to wire correct embedder per tool

6. **Phase 6: Server Initialization**
   - Update `main.py` to initialize registry with settings
   - Remove upfront model loading
   - Pass embedder accessor functions to `create_server()`
   - Verify lazy loading (no models at startup)

7. **Phase 7: Testing**
   - Unit tests for MiniLM
   - Unit tests for registry (lazy loading, caching)
   - Unit tests for `get_collection_info()`
   - Integration test for dual embeddings
   - Integration test for dimension migration
   - Performance benchmark verification

8. **Phase 8: Documentation**
   - Add CHANGELOG entry
   - Document migration behavior
   - Document environment variable override

## Success Criteria

1. Code indexing completes in <60s for clams repo (currently 3.4 min)
2. Existing memory/GHAP search continues to work (no quality regression)
3. `ping` tool does NOT load any models (validates lazy loading)
4. Dimension mismatch triggers automatic collection recreation
5. Both models can load and run simultaneously if needed
6. All tests pass, mypy strict mode, ruff clean
7. Integration test verifies correct embedder per tool type
