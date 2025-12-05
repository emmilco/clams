# SPEC-002-16: Full Integration and Performance Tuning - Technical Proposal

## Problem Statement

The Learning Memory Server consists of 16 completed modules that work independently but are not fully integrated. The system cannot run end-to-end because:

1. **Critical Integration Bugs**:
   - Stub ObservationPersister in `observation/__init__.py` shadows the real implementation from `persister.py`
   - GHAP tools call wrong API: `persister.persist(resolved.to_dict())` but persister expects `GHAPEntry` object
   - `search_experiences()` passes empty embedding array instead of generating real embeddings
   - Four MCP tools return stub results: `list_ghap_entries()`, `get_cluster_members()`, `list_values()`, `search_experiences()`

2. **Initialization Gaps**:
   - Code and Git services commented out, causing "service not initialized" errors
   - Collections not created on startup - fresh installs fail
   - No configuration validation - errors surface too late

3. **Missing Verification**:
   - No end-to-end integration tests proving the system works
   - Performance targets (p95 < 200ms search, p95 < 500ms context) unverified
   - Installation process never tested in clean environment

This task is the critical path to a working product. All prior work (SPEC-002-01 through SPEC-002-15) is validated only when the integrated system runs.

## Solution Overview

**Integration-First Approach**: Wire existing modules together with minimal new code. Focus on:
1. Fixing integration bugs (wrong imports, wrong API calls)
2. Enabling commented-out services with graceful degradation
3. Adding lifecycle management (collection creation, validation)
4. Implementing stub tools to query real data
5. Verifying correctness with integration tests
6. Verifying performance with benchmarks

**Key Principle**: This is plumbing work, not feature development. Every change connects existing pieces or validates they work correctly.

## Detailed Design

### 1. Fix ObservationPersister Integration Bugs

#### Issue Analysis

The stub class in `observation/__init__.py` (lines 25-50) defines a minimal `ObservationPersister` that shadows the real implementation from `persister.py`. The real implementation exists in the main repo but wasn't merged to the worktree, so the stub remained.

Additionally, `ghap.py:374` calls `persister.persist(resolved.to_dict())` but the real persister signature is:
```python
async def persist(self, entry: GHAPEntry) -> None:
```

#### Solution

**Step 1**: Remove stub class from `observation/__init__.py` (lines 25-50)

**Step 2**: Import real `ObservationPersister` from `persister.py`:
```python
from .persister import ObservationPersister
```

**Step 3**: Fix `ghap.py:374`:
```python
# Before (broken):
await persister.persist(resolved.to_dict())

# After (fixed):
await persister.persist(resolved)  # Pass GHAPEntry directly
```

**Step 4**: Verify multi-axis embedding in integration test:
- Call `resolve_ghap()` with falsified outcome (triggers all 4 axes)
- Query each collection (`ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`)
- Assert entry exists with correct payload fields

#### Collection Name Alignment

**Discovery**: The spec mentions both `ghap_*` and `experiences_*` collection names inconsistently.

**Resolution**: Use `ghap_*` as the canonical names per SPEC-002-14:
- `ghap_full` - Full narrative axis
- `ghap_strategy` - Strategy performance axis
- `ghap_surprise` - Unexpected outcomes axis (falsified only)
- `ghap_root_cause` - Failure analysis axis (falsified only)

The `experiences_*` naming appears in older code but is NOT used by the ObservationPersister implementation. The searcher and clusterer modules reference `experiences_*` but these are **different collections** used for generic experience storage (not GHAP-specific). No changes needed to those modules.

**Acceptance Criteria**:
- `from learning_memory_server.observation import ObservationPersister` imports real class
- `resolve_ghap()` successfully persists to all 4 axis collections
- Payload includes all required fields per SPEC-002-14 (domain, strategy, confidence_tier, etc.)
- Integration test: `start_ghap() → resolve_ghap() → search_experiences()` returns the entry

### 2. Enable Code and Git Services

#### Current State

`server/tools/__init__.py` lines 66-103 have code/git initialization commented out with "TODO: Enable when SPEC-002-06/07 complete" comments. These SPECs are complete, but services were never enabled.

#### Solution

**Graceful Degradation Strategy** (Code and Git ONLY):
- Attempt to initialize code/git services
- If initialization fails (missing dependencies, no git repo, etc.), log warning and continue
- MCP tools check if service is available before use
- Return clear error message if tool called without service

**Fail-Fast Strategy** (Qdrant):
- Qdrant connectivity errors fail immediately during startup
- No tolerance for vector store unavailability (per spec requirement 8)
- Clear error message directs user to start Qdrant

**Step 1**: Uncomment code service initialization (lines 66-83):
```python
code_indexer = None
try:
    from learning_memory_server.indexers.code import (
        CodeIndexer,
        TreeSitterParser,
    )
    code_parser = TreeSitterParser()
    code_indexer = CodeIndexer(
        parser=code_parser,
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
    )
    logger.info("code.initialized")
except ImportError as e:
    logger.warning("code.init_skipped", reason="module_not_found", error=str(e))
except Exception as e:
    logger.warning("code.init_failed", error=str(e))
```

**Step 2**: Uncomment git service initialization (lines 85-103):
```python
git_analyzer = None
if settings.repo_path:
    try:
        from learning_memory_server.indexers.git import (
            GitAnalyzer,
            GitPythonReader,
        )
        git_reader = GitPythonReader(repo_path=settings.repo_path)
        git_analyzer = GitAnalyzer(
            git_reader=git_reader,
            embedding_service=embedding_service,
            vector_store=vector_store,
            metadata_store=metadata_store,
        )
        logger.info("git.initialized", repo_path=settings.repo_path)
    except ImportError as e:
        logger.warning("git.init_skipped", reason="module_not_found", error=str(e))
    except Exception as e:
        logger.warning("git.init_failed", repo_path=settings.repo_path, error=str(e))
else:
    logger.info("git.init_skipped", reason="no_repo_path")
```

**Step 3**: Verify TreeSitter grammars are available:
- CodeIndexer initialization will fail if grammars missing
- Error message should guide user to install grammars
- Consider bundling grammars in package (future improvement)

**Step 4**: Update tool implementations to check service availability:
```python
# Example: code.py
async def index_codebase(directory: str, project_name: str | None = None):
    if services.code_indexer is None:
        return {"error": {
            "type": "service_unavailable",
            "message": "Code indexing service not initialized. Check server logs."
        }}

    # Proceed with indexing...
```

**Acceptance Criteria**:
- `index_codebase()` works without "service not initialized" error
- `search_code()` returns real results from indexed code
- `search_commits()` works in a git repository
- Server starts successfully even if code/git services fail to initialize
- Logs clearly indicate which services are available

### 3. Collection Lifecycle Management

#### Problem

Fresh Qdrant installations have no collections. Current code creates collections lazily on first `upsert()`, but this approach has issues:
- Silent failures if collection creation fails
- Dimension mismatches not caught until runtime
- No way to verify system health on startup

#### Solution

**Startup Collection Initialization**:

Add collection setup to `server/main.py` in `run_server()` before starting MCP loop:

```python
async def run_server(settings: ServerSettings) -> None:
    """Run the MCP server."""
    logger.info("server.starting")

    # Create the server
    server = create_server(settings)

    # Initialize collections before accepting requests
    try:
        await initialize_collections(server, settings)
        logger.info("collections.initialized")
    except Exception as e:
        logger.error("collections.init_failed", error=str(e), exc_info=True)
        raise  # Fail fast - cannot proceed without storage

    # Run using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("server.ready", transport="stdio")
        await server.run(...)
```

**Collection Creation Logic**:

```python
async def initialize_collections(settings: ServerSettings) -> tuple[EmbeddingService, VectorStore]:
    """Ensure all required collections exist.

    Creates collections if they don't exist. Idempotent - safe to call
    multiple times.

    Note: Services are initialized HERE (not extracted from server), because
    we need them BEFORE the server is created. The server tools will receive
    these same service instances via ServiceContainer.

    Args:
        settings: Server configuration

    Returns:
        Tuple of (embedding_service, vector_store) for use in ServiceContainer

    Raises:
        Exception: If collection creation fails
    """
    # Initialize services (same pattern as initialize_services() in tools/__init__.py)
    embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
    embedding_service = NomicEmbedding(settings=embedding_settings)
    vector_store = QdrantVectorStore(url=settings.qdrant_url)

    # Determine embedding dimension
    dimension = embedding_service.dimension

    # Define all required collections
    collections = [
        "memories",
        "code",
        "commits",
        "ghap_full",
        "ghap_strategy",
        "ghap_surprise",
        "ghap_root_cause",
        "values",
    ]

    # Create each collection (idempotent)
    for collection_name in collections:
        try:
            await vector_store.create_collection(
                name=collection_name,
                dimension=dimension,
                distance="cosine"
            )
            logger.info("collection.created", name=collection_name)
        except CollectionExistsError:
            # Normal case - collection already exists
            logger.debug("collection.exists", name=collection_name)
        except Exception as e:
            logger.error(
                "collection.create_failed",
                name=collection_name,
                error=str(e),
                exc_info=True
            )
            raise

    return embedding_service, vector_store
```

**Alternative: Pass Pre-Initialized Services to `register_all_tools()`**

The current `register_all_tools()` calls `initialize_services()` internally. To use pre-initialized services from `initialize_collections()`, modify the signature:

```python
# In server/tools/__init__.py
def register_all_tools(
    server: Server,
    settings: ServerSettings,
    embedding_service: EmbeddingService | None = None,
    vector_store: VectorStore | None = None,
) -> None:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
        embedding_service: Pre-initialized embedding service (optional)
        vector_store: Pre-initialized vector store (optional)
    """
    if embedding_service and vector_store:
        # Use pre-initialized services
        services = ServiceContainer(
            embedding_service=embedding_service,
            vector_store=vector_store,
            metadata_store=MetadataStore(db_path=settings.sqlite_path),
            # ... rest of services
        )
    else:
        # Initialize services as usual
        services = initialize_services(settings)

    # ... rest of tool registration
```

**Error Handling**:
- If Qdrant unreachable: **fail fast** with clear error (no tolerance per spec requirement 8)
- If collection already exists: log and continue (normal case)
- If dimension mismatch: fail fast (indicates configuration problem)

**Acceptance Criteria**:
- Server startup creates all collections if they don't exist
- Server startup succeeds if collections already exist
- Integration test: fresh Qdrant instance → start server → all collections exist
- Collection dimension matches `embedding_service.dimension`

### 4. Implement Stub MCP Tools

Four tools currently return empty results. Each needs real implementation querying VectorStore.

#### 4.1 `list_ghap_entries()` (ghap.py:519)

**Current**: Returns `{"results": [], "count": 0}`

**Fix**:
```python
async def list_ghap_entries(
    domain: str | None = None,
    outcome: str | None = None,
    since: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    # Validation already exists (lines 502-517)

    # Build filters
    filters: dict[str, Any] = {}
    if domain is not None:
        filters["domain"] = domain
    if outcome is not None:
        filters["outcome_status"] = outcome
    if since is not None:
        since_dt = datetime.fromisoformat(since)
        filters["captured_at"] = {"$gte": since_dt.timestamp()}

    # Query ghap_full collection
    results = await vector_store.scroll(
        collection="ghap_full",
        limit=limit,
        filters=filters if filters else None,
        with_vectors=False,  # Don't need embeddings for listing
    )

    # Format results
    entries = [
        {
            "id": r.id,
            "domain": r.payload.get("domain"),
            "strategy": r.payload.get("strategy"),
            "outcome_status": r.payload.get("outcome_status"),
            "confidence_tier": r.payload.get("confidence_tier"),
            "iteration_count": r.payload.get("iteration_count"),
            "created_at": datetime.fromtimestamp(r.payload["created_at"]).isoformat(),
            "captured_at": datetime.fromtimestamp(r.payload["captured_at"]).isoformat(),
        }
        for r in results
    ]

    return {
        "results": entries,
        "count": len(entries),
    }
```

#### 4.2 `get_cluster_members()` (learning.py:163)

**Current**: Returns `{"cluster_id": cluster_id, "axis": axis, "members": [], "count": 0}`

**Fix**:
```python
async def get_cluster_members(
    cluster_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    # Validation and parsing already exists (lines 140-161)
    axis = parts[0]
    label = int(parts[1])

    # Query appropriate axis collection
    collection = f"ghap_{axis}"  # e.g., "ghap_strategy"

    # Cluster label is stored in payload metadata
    results = await vector_store.scroll(
        collection=collection,
        limit=limit,
        filters={"cluster_label": label},
        with_vectors=False,
    )

    # Format members
    members = [
        {
            "id": r.id,
            "domain": r.payload.get("domain"),
            "strategy": r.payload.get("strategy"),
            "outcome_status": r.payload.get("outcome_status"),
            # Include any additional fields from payload
        }
        for r in results
    ]

    return {
        "cluster_id": cluster_id,
        "axis": axis,
        "members": members,
        "count": len(members),
    }
```

**Note**: Cluster labels are assigned by `ExperienceClusterer.cluster_axis()` and stored in payload metadata during clustering. The integration test must verify this workflow: `resolve_ghap() → get_clusters() → get_cluster_members()`.

#### 4.3 `list_values()` (learning.py:367)

**Current**: Returns `{"results": [], "count": 0}`

**Fix**:
```python
async def list_values(
    axis: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    # Validation already exists (lines 357-365)

    # Build filters
    filters = None
    if axis is not None:
        filters = {"axis": axis}

    # Query values collection
    results = await vector_store.scroll(
        collection="values",
        limit=limit,
        filters=filters,
        with_vectors=False,
    )

    # Format results
    values = [
        {
            "id": r.id,
            "text": r.payload["text"],
            "cluster_id": r.payload["cluster_id"],
            "axis": r.payload["axis"],
            "validated_at": datetime.fromtimestamp(r.payload["validated_at"]).isoformat(),
            "distance_to_centroid": r.payload.get("distance_to_centroid"),
        }
        for r in results
    ]

    return {
        "results": values,
        "count": len(values),
    }
```

#### 4.4 `search_experiences()` (search.py:88)

**Current**: Passes `query_embedding=[]` to searcher

**Fix**:
```python
async def search_experiences(
    query: str,
    axis: str = "full",
    domain: str | None = None,
    outcome: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    # Validation already exists (lines 71-86)

    # Generate query embedding
    try:
        query_embedding = await embedding_service.embed(query)
    except Exception as e:
        logger.error("search.embed_failed", query=query, error=str(e))
        return {"error": {
            "type": "embedding_error",
            "message": f"Failed to generate query embedding: {e}"
        }}

    # Call searcher with real embedding
    results = await searcher.search_experiences(
        query_embedding=query_embedding,
        axis=axis,
        domain=domain,
        outcome=outcome,
        limit=limit,
    )

    logger.info(
        "search.experiences_searched",
        query=query,
        axis=axis,
        count=len(results),
    )

    return {
        "results": results,
        "count": len(results),
    }
```

**Acceptance Criteria**:
- `list_ghap_entries()` returns actual GHAP entries from VectorStore
- Filters work correctly (domain, outcome, since date)
- `get_cluster_members()` returns experiences in a specific cluster
- `list_values()` returns stored values with optional axis filter
- `search_experiences()` generates real embeddings and returns semantically relevant results

### 5. End-to-End Integration Tests

Create `tests/integration/test_e2e.py` with 5 comprehensive scenarios proving the system works.

#### Test Collection Isolation Strategy

**Problem**: Integration tests need to avoid polluting production collections.

**Solution**: Override `AXIS_COLLECTIONS` module-level mapping temporarily during tests (pattern already used in `tests/clustering/test_integration.py`).

**How It Works**:

1. **Production code** uses module-level constant:
```python
# In clustering/experience.py
AXIS_COLLECTIONS = {
    "full": "experiences_full",
    "strategy": "experiences_strategy",
    "surprise": "experiences_surprise",
    "root_cause": "experiences_root_cause",
}
```

2. **Tests temporarily override** this mapping:
```python
# In test fixture
from learning_memory_server.clustering import experience

original_mapping = experience.AXIS_COLLECTIONS.copy()
experience.AXIS_COLLECTIONS = {
    "full": "test_ghap_full",
    "strategy": "test_ghap_strategy",
    "surprise": "test_ghap_surprise",
    "root_cause": "test_ghap_root_cause",
}

try:
    # Run tests
    yield services
finally:
    # Restore original mapping
    experience.AXIS_COLLECTIONS = original_mapping
```

3. **ObservationPersister** uses same pattern (stores to collections via `AXIS_COLLECTIONS`)

4. **Tests clean up** test collections after completion

This approach:
- Requires NO service configuration changes
- Uses existing patterns from clustering tests
- Ensures complete isolation (no shared state between tests)
- Allows tests to create their own collections with known state

#### Test Infrastructure

**Setup** (`tests/integration/conftest.py`):
```python
import pytest
from learning_memory_server.embedding import NomicEmbedding, EmbeddingSettings
from learning_memory_server.storage.qdrant import QdrantVectorStore
from learning_memory_server.storage.metadata import MetadataStore

@pytest.fixture
async def integration_services():
    """Create real services for integration testing."""
    # Use real Qdrant (requires docker container running)
    embedding_service = NomicEmbedding(
        settings=EmbeddingSettings(model_name="nomic-ai/nomic-embed-text-v1.5")
    )
    vector_store = QdrantVectorStore(url="http://localhost:6333")
    metadata_store = MetadataStore(db_path=":memory:")  # In-memory for tests

    # Create test collections
    dimension = embedding_service.dimension
    test_collections = [
        "test_memories", "test_code", "test_commits",
        "test_ghap_full", "test_ghap_strategy",
        "test_ghap_surprise", "test_ghap_root_cause",
        "test_values"
    ]

    for collection in test_collections:
        try:
            await vector_store.create_collection(
                name=collection,
                dimension=dimension,
                distance="cosine"
            )
        except:
            pass  # Collection might already exist

    # Override AXIS_COLLECTIONS for test isolation
    from learning_memory_server.clustering import experience
    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {
        "full": "test_ghap_full",
        "strategy": "test_ghap_strategy",
        "surprise": "test_ghap_surprise",
        "root_cause": "test_ghap_root_cause",
    }

    yield {
        "embedding_service": embedding_service,
        "vector_store": vector_store,
        "metadata_store": metadata_store,
    }

    # Restore original mapping
    experience.AXIS_COLLECTIONS = original_mapping

    # Cleanup - delete test collections
    for collection in test_collections:
        try:
            await vector_store.delete_collection(collection)
        except:
            pass
```

#### Scenario 1: Memory Lifecycle

```python
async def test_memory_lifecycle(integration_services):
    """Test store → retrieve → delete memory flow."""
    # Store memory
    memory_id = await memory_tools.store_memory(
        content="Unit tests should be fast and isolated",
        category="preference",
        importance=0.8,
    )

    # Retrieve with semantic search (query different from stored text)
    results = await memory_tools.retrieve_memories(
        query="how should tests be designed",
        limit=5,
    )

    assert len(results) > 0
    assert any(memory_id in r["id"] for r in results)

    # Delete memory
    await memory_tools.delete_memory(memory_id)

    # Verify deleted
    results = await memory_tools.retrieve_memories(query="unit tests", limit=10)
    assert not any(memory_id in r["id"] for r in results)
```

#### Scenario 2: Code Indexing & Search

```python
async def test_code_indexing(integration_services, tmp_path):
    """Test index → search → find_similar code flow."""
    # Create test Python file
    test_file = tmp_path / "example.py"
    test_file.write_text('''
def calculate_average(numbers: list[float]) -> float:
    """Calculate arithmetic mean of numbers."""
    return sum(numbers) / len(numbers)

def find_max(numbers: list[int]) -> int:
    """Find maximum value in list."""
    return max(numbers)
    ''')

    # Index codebase
    await code_tools.index_codebase(
        directory=str(tmp_path),
        project_name="test_project",
    )

    # Search for function
    results = await code_tools.search_code(
        query="compute average of list",
        project="test_project",
        limit=5,
    )

    assert len(results) > 0
    assert "calculate_average" in results[0]["name"]

    # Find similar code
    similar = await code_tools.find_similar_code(
        code_snippet="def avg(xs): return sum(xs) / len(xs)",
        project="test_project",
        limit=5,
    )

    assert len(similar) > 0
    assert "calculate_average" in similar[0]["name"]
```

#### Scenario 3: Git Analysis

```python
async def test_git_analysis(integration_services, tmp_path):
    """Test commit indexing and analysis."""
    # Create test git repo (using GitPython)
    repo = git.Repo.init(tmp_path)
    test_file = tmp_path / "main.py"
    test_file.write_text("print('hello')")
    repo.index.add(["main.py"])
    repo.index.commit("Initial commit")

    # Index commits
    await git_tools.index_commits(
        repo_path=str(tmp_path),
        project_name="test_repo",
    )

    # Search commits
    results = await git_tools.search_commits(
        query="initial commit",
        project="test_repo",
        limit=5,
    )

    assert len(results) > 0
    assert "Initial commit" in results[0]["message"]

    # Get authors
    authors = await git_tools.get_code_authors(
        file_path=str(test_file),
    )

    assert len(authors) > 0
```

#### Scenario 4: GHAP Learning Loop (Comprehensive Single Test)

**Critical**: This must be ONE test with 20+ entries to enable real clustering.

```python
async def test_ghap_learning_loop(integration_services):
    """Test complete GHAP lifecycle with clustering.

    Creates 20+ entries (required for HDBSCAN clustering) and verifies:
    - Entry persistence to all 4 axes
    - Clustering functionality
    - Value validation and storage
    """
    ghap_ids = []

    # Create 20+ diverse GHAP entries
    domains = ["debugging", "refactoring", "optimization", "testing"]
    strategies = ["systematic-elimination", "binary-search", "hypothesis-testing", "divide-conquer"]

    for i in range(25):  # 25 entries across 4 domains, varying strategies
        # Start GHAP
        entry = await ghap_tools.start_ghap(
            domain=domains[i % 4],
            strategy=strategies[i % 4],
            goal=f"Test goal {i}",
            hypothesis=f"Hypothesis {i}",
            action=f"Action {i}",
            prediction=f"Prediction {i}",
        )
        ghap_id = entry["id"]

        # Resolve with varied outcomes (mix of confirmed/falsified)
        if i % 3 == 0:  # Falsified - triggers all 4 axes
            resolved = await ghap_tools.resolve_ghap(
                status="falsified",
                result=f"Failed: unexpected behavior {i}",
                surprise=f"Did not expect {i}",
                root_cause={
                    "category": "wrong-assumption",
                    "description": f"Root cause {i}"
                },
                lesson={
                    "what_worked": f"Lesson {i}",
                    "takeaway": f"Takeaway {i}",
                },
            )
        else:  # Confirmed - only full and strategy axes
            resolved = await ghap_tools.resolve_ghap(
                status="confirmed",
                result=f"Success {i}",
                lesson={
                    "what_worked": f"Strategy worked for {i}",
                },
            )

        ghap_ids.append(ghap_id)

    # Verify entries persisted to correct axes
    # 1. All 25 should be in ghap_full
    full_entries = await ghap_tools.list_ghap_entries(limit=50)
    assert full_entries["count"] >= 25

    # 2. All 25 should be in ghap_strategy
    strategy_entries = await vector_store.scroll(
        collection="test_ghap_strategy",
        limit=50,
        with_vectors=False,
    )
    assert len(strategy_entries) >= 25

    # 3. ~8-9 falsified entries should be in ghap_surprise
    surprise_entries = await vector_store.scroll(
        collection="test_ghap_surprise",
        limit=50,
        with_vectors=False,
    )
    assert len(surprise_entries) >= 8

    # 4. Same for ghap_root_cause
    root_cause_entries = await vector_store.scroll(
        collection="test_ghap_root_cause",
        limit=50,
        with_vectors=False,
    )
    assert len(root_cause_entries) >= 8

    # Get clusters (requires 20+ entries)
    clusters = await learning_tools.get_clusters(axis="full")
    assert len(clusters) > 0  # Should find at least 1 cluster

    # Get cluster members
    cluster_id = clusters[0]["cluster_id"]
    members = await learning_tools.get_cluster_members(
        cluster_id=cluster_id,
        limit=50,
    )
    assert members["count"] > 0

    # Validate a value against cluster centroid
    validation = await learning_tools.validate_value(
        text="Always check assumptions before debugging",
        cluster_id=cluster_id,
    )
    assert "is_valid" in validation
    assert "distance" in validation

    # Store validated value
    if validation["is_valid"]:
        value_id = await learning_tools.store_value(
            text="Always check assumptions before debugging",
            cluster_id=cluster_id,
        )
        assert value_id is not None

        # List values
        values = await learning_tools.list_values(axis="full", limit=10)
        assert values["count"] > 0
```

#### Scenario 5: Context Assembly

```python
async def test_context_assembly(integration_services):
    """Test context assembly with all data types."""
    # Populate various collections
    await memory_tools.store_memory(
        content="Performance matters for user experience",
        category="preference",
    )

    # (Assume code and experiences already populated from other tests)

    # Assemble light context
    light_context = await context_tools.assemble(
        query="How to optimize performance",
        mode="light",
    )

    assert "# Context" in light_context
    assert len(light_context) < 5000  # Light should be brief

    # Assemble rich context
    rich_context = await context_tools.assemble(
        query="How to optimize performance",
        mode="rich",
    )

    assert "# Context" in rich_context
    assert len(rich_context) > len(light_context)  # Rich should be more detailed

    # Premortem warnings
    warnings = await context_tools.premortem(
        domain="optimization",
        strategy="systematic-elimination",
    )

    # Should warn about past failures in this domain/strategy
    assert "warnings" in warnings
```

**Test Execution**:
- Run with: `pytest tests/integration/test_e2e.py -vvsx`
- Requires Qdrant running: `docker run -p 6333:6333 qdrant/qdrant`
- Total execution time target: < 60 seconds

**Acceptance Criteria**:
- All 5 scenarios pass with real Qdrant instance
- Tests run in < 60 seconds total
- Tests clean up after themselves (delete test collections)
- No flaky failures (tests are deterministic)

### 6. Installation & Deployment Verification

Verify the package can be installed and run in a clean environment.

#### Test Protocol

**Step 1**: Fresh virtual environment
```bash
python -m venv test_venv
source test_venv/bin/activate
```

**Step 2**: Install package
```bash
pip install -e ".[dev]"
```

**Step 3**: Verify dependencies resolve
```bash
pip list | grep -E "qdrant|sentence-transformers|torch"
```

**Step 4**: Test CLI entry point
```bash
learning-memory-server --help
# OR if no --help flag, start server and send ping
```

**Step 5**: Test configuration override
```bash
export LMS_QDRANT_URL=http://localhost:6333
export LMS_EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
learning-memory-server
# Verify server starts with custom config
```

**Automated Test** (`tests/integration/test_installation.py`):
```python
import subprocess
import sys

def test_package_installable(tmp_path):
    """Verify package installs in clean venv."""
    # Create venv
    subprocess.run([sys.executable, "-m", "venv", str(tmp_path / "venv")])

    # Install package
    pip = tmp_path / "venv" / "bin" / "pip"
    result = subprocess.run(
        [str(pip), "install", "-e", "."],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify entry point exists
    entry_point = tmp_path / "venv" / "bin" / "learning-memory-server"
    assert entry_point.exists()

def test_imports_work():
    """Verify all modules can be imported."""
    import learning_memory_server
    from learning_memory_server.embedding import NomicEmbedding
    from learning_memory_server.storage.qdrant import QdrantVectorStore
    from learning_memory_server.observation import ObservationCollector, ObservationPersister
    # etc. for all major modules
```

**Acceptance Criteria**:
- Fresh venv installation succeeds
- `learning-memory-server --help` works (or server starts and responds to ping)
- LMS_QDRANT_URL, LMS_EMBEDDING_MODEL env vars are respected
- No import errors on startup
- No version conflicts in dependencies

### 7. Performance Benchmarking

Create `tests/performance/test_benchmarks.py` to verify latency targets.

**CRITICAL**: These are HARD requirements. Failure blocks integration.

#### Benchmark Infrastructure

```python
import time
import numpy as np
from typing import Callable, Any

async def measure_latency(
    func: Callable,
    iterations: int = 100,
    **kwargs: Any,
) -> dict[str, float]:
    """Measure p50, p95, p99 latency for async function.

    Args:
        func: Async function to benchmark
        iterations: Number of iterations
        **kwargs: Arguments to pass to func

    Returns:
        Dict with p50, p95, p99 latency in milliseconds
    """
    latencies = []

    for _ in range(iterations):
        start = time.perf_counter()
        await func(**kwargs)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # Convert to ms

    latencies_array = np.array(latencies)

    return {
        "p50": float(np.percentile(latencies_array, 50)),
        "p95": float(np.percentile(latencies_array, 95)),
        "p99": float(np.percentile(latencies_array, 99)),
        "mean": float(np.mean(latencies_array)),
        "std": float(np.std(latencies_array)),
    }
```

#### Benchmark 1: Code Search

```python
async def test_code_search_performance(integration_services):
    """Verify code search meets p95 < 200ms target."""
    # Prepopulate: Index 100 Python functions
    # (Use fixture to create test codebase)

    # Benchmark
    results = await measure_latency(
        code_tools.search_code,
        iterations=100,
        query="calculate average",
        limit=10,
    )

    # Log results
    print(f"Code search latency: {results}")

    # Assert hard requirement
    assert results["p95"] < 200, f"Code search p95 too slow: {results['p95']:.1f}ms"
```

#### Benchmark 2: Memory Retrieval

```python
async def test_memory_retrieval_performance(integration_services):
    """Verify memory retrieval meets p95 < 200ms target."""
    # Prepopulate: Store 1000 memories
    for i in range(1000):
        await memory_tools.store_memory(
            content=f"Memory {i}: Some content about topic {i % 10}",
            category="fact",
        )

    # Benchmark
    results = await measure_latency(
        memory_tools.retrieve_memories,
        iterations=100,
        query="topic 5",
        limit=10,
    )

    print(f"Memory retrieval latency: {results}")
    assert results["p95"] < 200, f"Memory retrieval p95 too slow: {results['p95']:.1f}ms"
```

#### Benchmark 3: Context Assembly

```python
async def test_context_assembly_performance(integration_services):
    """Verify context assembly meets p95 < 500ms target."""
    # Prepopulate all collections
    # (Memories, code, experiences, values)

    # Benchmark
    results = await measure_latency(
        context_tools.assemble,
        iterations=10,  # Fewer iterations (context is expensive)
        query="How to debug performance issues",
        mode="rich",
    )

    print(f"Context assembly latency: {results}")
    assert results["p95"] < 500, f"Context assembly p95 too slow: {results['p95']:.1f}ms"
```

#### Benchmark 4: Clustering

```python
async def test_clustering_performance(integration_services):
    """Verify clustering completes in < 5s for 100 entries."""
    # Prepopulate: Store 100 GHAP entries across all 4 domains
    # (Similar to integration test but focused on performance)

    # Benchmark clustering on all 4 axes
    start = time.perf_counter()

    for axis in ["full", "strategy", "surprise", "root_cause"]:
        clusters = await learning_tools.get_clusters(axis=axis)

    end = time.perf_counter()
    total_time = end - start

    print(f"Clustering (4 axes, 100 entries): {total_time:.2f}s")
    assert total_time < 5.0, f"Clustering too slow: {total_time:.2f}s"
```

**Note on Cold-Start Performance**: The first clustering call may be slower due to:
- HDBSCAN model initialization
- NumPy/SciPy lazy loading
- Memory allocation for large embedding arrays

Subsequent calls will be faster. Benchmarks should measure steady-state performance (run warmup iteration first or take median of multiple runs).

**Results Logging**:

Save benchmark results to JSON for tracking over time:
```python
import json
from datetime import datetime

benchmark_results = {
    "timestamp": datetime.now().isoformat(),
    "code_search": code_search_results,
    "memory_retrieval": memory_retrieval_results,
    "context_assembly": context_assembly_results,
    "clustering": {"total_time": total_time},
}

with open("benchmark_results.json", "w") as f:
    json.dump(benchmark_results, f, indent=2)
```

**Acceptance Criteria** (HARD REQUIREMENTS):
- Code search: p95 < 200ms
- Memory retrieval: p95 < 200ms
- Context assembly: p95 < 500ms
- Clustering: completes in < 5s for 100 entries (4 axes)
- Benchmark results logged to JSON for tracking
- **If any benchmark fails, escalate to human before proceeding**

### 8. Configuration Validation

Add startup validation to fail fast on configuration errors.

#### Validation Logic

Add to `server/main.py` before `run_server()`:

```python
def validate_configuration(settings: ServerSettings) -> None:
    """Validate configuration before server start.

    Fails fast with clear error messages.

    Args:
        settings: Server configuration

    Raises:
        ValueError: If configuration invalid
    """
    # 1. Validate Qdrant connectivity (no tolerance per spec)
    try:
        # Attempt connection
        import requests
        response = requests.get(f"{settings.qdrant_url}/collections", timeout=5)
        if response.status_code != 200:
            raise ValueError(
                f"Qdrant unreachable at {settings.qdrant_url}. "
                f"Status: {response.status_code}. "
                "Ensure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
            )
    except requests.exceptions.ConnectionError:
        raise ValueError(
            f"Cannot connect to Qdrant at {settings.qdrant_url}. "
            "Ensure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
        )
    except requests.exceptions.Timeout:
        raise ValueError(
            f"Qdrant connection timeout at {settings.qdrant_url}. "
            "Check network connectivity."
        )

    # 2. Validate embedding model (will fail on first embed if invalid)
    try:
        from sentence_transformers import SentenceTransformer
        # Try to load model (downloads if needed)
        _ = SentenceTransformer(settings.embedding_model)
    except Exception as e:
        raise ValueError(
            f"Invalid embedding model '{settings.embedding_model}': {e}"
        )

    # 3. Validate paths are writable
    import os
    for path_name, path_value in [
        ("storage_path", settings.storage_path),
        ("sqlite_path", settings.sqlite_path),
        ("journal_path", settings.journal_path),
    ]:
        parent = os.path.dirname(path_value)
        if not os.access(parent, os.W_OK):
            raise ValueError(
                f"{path_name} parent directory not writable: {parent}"
            )

    # 4. Validate git repo if provided
    if settings.repo_path:
        import git
        try:
            repo = git.Repo(settings.repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(
                f"Invalid git repository at {settings.repo_path}"
            )
```

Call validation in `main()`:
```python
def main() -> None:
    """Entry point for the MCP server."""
    settings = ServerSettings()
    configure_logging(...)

    logger.info("learning_memory_server.starting", version="0.1.0")

    # Validate configuration before starting
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except ValueError as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Run server...
```

**Acceptance Criteria**:
- Invalid/unreachable Qdrant URL fails fast with clear error (no tolerance)
- Invalid embedding model fails fast with clear error
- Invalid paths fail fast with clear error
- Valid configuration starts successfully
- Error messages guide user to fix the issue

### 9. Error Handling & Observability

Improve logging and error context for production debugging.

#### Structured Logging

Already using `structlog`. Ensure all tool calls log:
```python
logger.info(
    "tool.started",
    tool="search_code",
    query=query,
    project=project,
)

try:
    # Tool implementation
    results = ...

    logger.info(
        "tool.completed",
        tool="search_code",
        query=query,
        result_count=len(results),
        duration_ms=duration,
    )
except Exception as e:
    logger.error(
        "tool.failed",
        tool="search_code",
        query=query,
        error=str(e),
        exc_info=True,  # Include stack trace
    )
    raise
```

#### Error Context Enhancement

Wrap exceptions with context:
```python
class MCPToolError(Exception):
    """Base exception for MCP tool errors."""

    def __init__(self, tool: str, message: str, details: dict | None = None):
        self.tool = tool
        self.message = message
        self.details = details or {}
        super().__init__(f"[{tool}] {message}")

# Usage:
try:
    await vector_store.search(...)
except Exception as e:
    raise MCPToolError(
        tool="search_code",
        message="VectorStore search failed",
        details={
            "query": query,
            "collection": collection,
            "original_error": str(e),
        }
    ) from e
```

#### Health Check

The `ping` tool already exists. Verify it works:
```python
@server.call_tool()
async def ping() -> str:
    """Health check endpoint."""
    return "pong"
```

#### Metrics Endpoint (Optional)

Add optional metrics for observability:
```python
@server.call_tool()
async def metrics() -> dict[str, Any]:
    """Get system metrics."""
    # Collection counts
    collection_counts = {}
    for collection in ["memories", "code", "commits", "ghap_full", "values"]:
        try:
            count = await vector_store.count(collection)
            collection_counts[collection] = count
        except:
            collection_counts[collection] = None

    return {
        "collections": collection_counts,
        "timestamp": datetime.now().isoformat(),
    }
```

**Acceptance Criteria**:
- Every MCP tool logs start and completion
- Errors include full context (tool name, parameters, stack trace)
- ping tool returns "pong" successfully
- Logs are valid JSON (for log aggregation)

### 10. Minimal README Update

Update README.md with essential information only. Avoid brittle details.

#### README Structure

```markdown
# Learning Memory Server

A Model Context Protocol (MCP) server for semantic memory, code indexing, and experience-based learning.

## Features

- **Memory Management**: Store and retrieve semantic memories with categories
- **Code Indexing**: Index and search Python/TypeScript code with TreeSitter
- **Git Analysis**: Analyze commit history, find churn hotspots, identify code authors
- **GHAP Learning**: Goal-Hypothesis-Action-Prediction cycle with experience clustering
- **Context Assembly**: Generate rich context from memories, code, and experiences

## System Requirements

- Python 3.11+
- Qdrant vector database (Docker: `docker run -p 6333:6333 qdrant/qdrant`)
- 4GB RAM minimum (8GB recommended for embedding model)

## Installation

```bash
# Clone repository
git clone <repo-url>
cd learning-memory-server

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .
```

## Usage

### Start Server

```bash
# Start Qdrant first
docker run -p 6333:6333 qdrant/qdrant

# Start Learning Memory Server
learning-memory-server
```

### Configuration

Environment variables:
- `LMS_QDRANT_URL` - Qdrant URL (default: http://localhost:6333)
- `LMS_EMBEDDING_MODEL` - Embedding model (default: nomic-ai/nomic-embed-text-v1.5)
- `LMS_LOG_LEVEL` - Logging level (default: INFO)

### Available Tools

See `src/learning_memory_server/server/tools/` for all MCP tools:
- `memory.py` - store_memory, retrieve_memories, list_memories, delete_memory
- `code.py` - index_codebase, search_code, find_similar_code
- `git.py` - index_commits, search_commits, get_churn_hotspots, get_code_authors
- `ghap.py` - start_ghap, update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
- `learning.py` - get_clusters, get_cluster_members, validate_value, store_value, list_values
- `search.py` - search_experiences, search_all

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest -vvsx

# Run linter
ruff check src tests

# Run type checker
mypy src
```

## Architecture

Core components:
- **Embedding**: sentence-transformers with Nomic Embed
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: SQLite for structured data
- **Parsing**: TreeSitter for code analysis
- **Clustering**: HDBSCAN for experience grouping

See source code for detailed implementation.
```

**What NOT to Include**:
- Detailed tool parameter documentation (changes frequently - refer to source)
- Exhaustive configuration reference (see code for all options)
- Version-specific information (will drift)
- Implementation details that change often

**Acceptance Criteria**:
- README is under 100 lines
- No brittle information that will drift from code
- Directs users to source code as the source of truth
- Covers installation, basic usage, and architecture overview

## Implementation Order

Implement in this sequence to minimize dependencies and enable early testing:

### Phase 1: Foundation (Days 1-2)
1. Fix ObservationPersister bugs (Req 1)
   - Remove stub class from `observation/__init__.py`
   - Fix `ghap.py:374` API call
   - Verify multi-axis embedding works
2. Add collection lifecycle management (Req 3)
   - Add `initialize_collections()` to `main.py`
   - Test with fresh Qdrant instance
3. Add configuration validation (Req 8)
   - Implement `validate_configuration()`
   - Test fail-fast behavior

### Phase 2: Service Integration (Day 2)
4. Enable Code and Git services (Req 2)
   - Uncomment initialization code
   - Add graceful degradation
   - Test service availability checks

### Phase 3: Tool Implementation (Day 2-3)
5. Implement stub MCP tools (Req 4)
   - Fix `search_experiences()` embedding
   - Implement `list_ghap_entries()`
   - Implement `get_cluster_members()`
   - Implement `list_values()`

### Phase 4: Verification (Day 3-4)
6. Integration tests (Req 5)
   - Create test infrastructure
   - Implement 5 scenarios
   - Verify all pass
7. Performance benchmarks (Req 7)
   - Implement 4 benchmarks
   - Run and measure
   - **BLOCKER**: Escalate to human if targets missed

### Phase 5: Polish (Day 4)
8. Error handling & observability (Req 9)
   - Add structured logging
   - Enhance error context
   - Verify ping tool works
9. Installation verification (Req 6)
   - Test fresh venv install
   - Verify CLI entry point
   - Test configuration override
10. Documentation (Req 10)
    - Update README with minimal info
    - Avoid brittle details

## Testing Strategy

### Unit Tests
- Existing tests must continue to pass (no regressions)
- Add tests for new utility functions (validation, initialization)

### Integration Tests
- **Primary validation method** for this task
- Test end-to-end flows with real services
- Use real Qdrant (not mocks) to catch integration issues
- Each scenario tests multiple module interactions

### Performance Tests
- Hard requirements - failure blocks integration
- Run on representative data volumes (100 functions, 1000 memories, 100 experiences)
- Log results for tracking over time

### Installation Tests
- Verify package works in clean environment
- Catch missing dependencies or import errors

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Performance targets too aggressive** | High - blocks integration | Medium | Measure first, optimize if needed, escalate if unrealistic |
| **ObservationPersister complex** | High - blocks learning loop | Low | Implementation already exists (SPEC-002-14), just needs wiring |
| **Collection naming mismatch** | Medium - wrong collections queried | Low | Clarified: use `ghap_*` per SPEC-002-14 |
| **GHAP clustering test needs 20+ entries** | Medium - complex test setup | Medium | Create comprehensive single test (not multiple small tests) |
| **TreeSitter grammar loading fails** | Low - code indexing breaks | Medium | Graceful degradation, clear error message |
| **Qdrant version incompatibility** | Low - tests may fail | Low | Pin qdrant-client version, test with Docker image |
| **Fresh install missing dependencies** | Low - poor UX | Low | Add installation test, verify dependency resolution |

## Success Metrics

Integration is successful when:

1. **All MCP tools work end-to-end** - No stubs, no "service not initialized" errors
2. **Fresh installation succeeds** - `uv venv → install → start server → ping returns pong`
3. **All integration tests pass** - 5 scenarios in `test_e2e.py` complete successfully
4. **All performance benchmarks pass** - Targets met in `test_benchmarks.py`
5. **Documentation is complete** - README covers installation, configuration, usage
6. **No regressions** - Existing unit tests still pass

## Open Questions

None. All major decisions resolved:
- Collection naming: `ghap_*` per SPEC-002-14
- Collection lifecycle: Create on startup, fail fast if Qdrant unreachable
- Service initialization: Graceful degradation for code/git, strict for Qdrant
- Performance targets: Hard requirements, escalate if missed
- GHAP test: Single comprehensive test with 20+ entries

## Appendix: Integration Checklist

Every module pair verification (from spec):

### EmbeddingService ↔ VectorStore
- [x] Dimension matches (tested in existing tests)
- [ ] Fresh install creates collections with correct dimension

### EmbeddingService ↔ ObservationPersister
- [ ] Multi-axis embedding generates 4 embeddings per entry
- [ ] Confidence tier weights propagate to payload

### EmbeddingService ↔ Searcher
- [ ] Query embeddings match stored embedding format
- [ ] Search results have correct scores (cosine similarity)

### VectorStore ↔ ObservationPersister
- [ ] All 4 axis collections store entries
- [ ] Payload schema matches Clusterer expectations

### VectorStore ↔ Clusterer
- [ ] Scroll retrieves all entries (no pagination issues)
- [ ] Weights extracted from payload correctly
- [ ] Centroids computed correctly

### VectorStore ↔ ValueStore
- [ ] Values stored with embeddings
- [ ] Validation queries cluster centroids
- [ ] List queries values collection

### VectorStore ↔ Searcher
- [ ] All collections searchable
- [ ] Filters work correctly (category, project, language, domain, outcome, axis)
- [ ] Limit parameter respected

### Searcher ↔ ContextAssembler
- [ ] Multi-collection queries return correct results
- [ ] Deduplication works across collections
- [ ] Token budgeting distributes correctly

### ObservationCollector ↔ ObservationPersister
- [ ] Resolved entries serialize correctly
- [ ] Persister handles all outcome types (confirmed, falsified, abandoned)

### Clusterer ↔ ExperienceClusterer
- [ ] Multi-axis clustering queries correct collections
- [ ] Cluster labels stored correctly
- [ ] Noise filtering works

### ExperienceClusterer ↔ ValueStore
- [ ] Cluster centroids accessible for validation
- [ ] Member distances computed correctly
- [ ] Median distance threshold works

### MCP Server ↔ All Services
- [ ] ServiceContainer initializes all dependencies
- [ ] Tools have access to required services
- [ ] Errors propagate to MCP responses correctly

All items will be verified by integration tests.
