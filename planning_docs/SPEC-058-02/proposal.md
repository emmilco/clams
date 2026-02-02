# SPEC-058-02: CALM Memory/GHAP - Technical Proposal

## Overview

This proposal outlines the implementation approach for porting memory and GHAP (Goal-Hypothesis-Action-Prediction) functionality from the existing clams MCP server to the new calm package. The port follows a copy-and-adapt strategy, reusing proven code while adapting it to calm's new architecture.

**Key architectural decision**: calm uses `~/.calm/` as its home directory with a unified `metadata.db` SQLite database, distinct from clams' `~/.clams/` directory. Both packages share the same Qdrant instance for vector storage.

## Module Structure

The ported modules will be organized under `src/calm/` following calm's package conventions:

```
src/calm/
├── __init__.py                 # Package root (exists from SPEC-058-01)
├── config.py                   # Settings (exists from SPEC-058-01)
├── db/
│   ├── __init__.py
│   └── schema.py              # Schema (exists from SPEC-058-01)
├── server/
│   ├── __init__.py
│   ├── app.py                 # MCP server (exists from SPEC-058-01)
│   └── errors.py              # Error types (NEW)
├── tools/                     # MCP tool implementations (NEW)
│   ├── __init__.py            # Tool registration + ServiceContainer
│   ├── memory.py              # Memory CRUD tools
│   ├── ghap.py                # GHAP lifecycle tools
│   ├── code.py                # Code indexing tools
│   ├── git.py                 # Git tools
│   ├── learning.py            # Clustering and value tools
│   ├── search.py              # Semantic search tools
│   ├── context.py             # Context assembly tool
│   ├── session.py             # Session helper tools
│   ├── validation.py          # Input validation utilities
│   ├── enums.py               # Domain/strategy enums
│   └── schema.py              # Tool JSON schema definitions
├── storage/                   # Storage abstractions (NEW)
│   ├── __init__.py
│   ├── base.py                # VectorStore interface
│   ├── qdrant.py              # Qdrant implementation
│   ├── metadata.py            # SQLite metadata store
│   └── memory.py              # Memory storage helpers
├── embedding/                 # Embedding models (NEW)
│   ├── __init__.py
│   ├── base.py                # EmbeddingService interface
│   ├── nomic.py               # Nomic text embeddings (768-dim)
│   ├── minilm.py              # MiniLM code embeddings (384-dim)
│   ├── mock.py                # Mock embedder for testing
│   └── registry.py            # Model registry
├── ghap/                      # GHAP tracking (NEW)
│   ├── __init__.py
│   ├── models.py              # GHAP data models
│   ├── collector.py           # Local GHAP state machine
│   ├── persister.py           # GHAP persistence to Qdrant
│   ├── exceptions.py          # GHAP-specific exceptions
│   └── utils.py               # ID generation, text truncation
├── indexers/                  # Code indexing (NEW)
│   ├── __init__.py
│   ├── base.py                # Parser interface
│   ├── indexer.py             # CodeIndexer implementation
│   ├── tree_sitter.py         # Tree-sitter parser
│   └── utils.py               # Hash, ID generation
├── git/                       # Git analysis (NEW)
│   ├── __init__.py
│   ├── base.py                # GitReader interface
│   ├── reader.py              # GitPython implementation
│   └── analyzer.py            # Commit indexing, churn analysis
├── clustering/                # Experience clustering (NEW)
│   ├── __init__.py
│   ├── clusterer.py           # HDBSCAN clustering
│   ├── experience.py          # ExperienceClusterer
│   └── types.py               # Cluster data types
├── values/                    # Value store (NEW)
│   ├── __init__.py
│   ├── store.py               # ValueStore implementation
│   └── types.py               # Value data types
├── search/                    # Semantic search (NEW)
│   ├── __init__.py
│   ├── searcher.py            # Searcher implementation
│   ├── collections.py         # Collection constants
│   └── results.py             # Search result types
├── context/                   # Context assembly (NEW)
│   ├── __init__.py
│   ├── assembler.py           # ContextAssembler
│   ├── models.py              # ContextItem, FormattedContext
│   ├── formatting.py          # Markdown formatters
│   ├── tokens.py              # Token estimation, budgeting
│   ├── deduplication.py       # Fuzzy deduplication
│   └── searcher_types.py      # Searcher protocol
└── utils/                     # Shared utilities (NEW)
    ├── __init__.py
    ├── datetime.py            # DateTime utilities
    ├── numeric.py             # Numeric utilities
    ├── validation.py          # Common validators
    ├── tokens.py              # Token counting
    └── platform.py            # Platform detection
```

## Key Implementation Details

### 1. Memory Tools

**Source**: `src/clams/server/tools/memory.py`, `src/clams/storage/memory.py`

**Approach**:
- Copy `get_memory_tools()` pattern with inner async functions
- Update imports from `clams.*` to `calm.*`
- Use `calm.config.settings` for configuration
- Memories stored in Qdrant `memories` collection with embeddings
- No SQLite storage for memories (Qdrant only)

**Tools**:
- `store_memory(content, category, importance, tags)` - Store with embedding
- `retrieve_memories(query, limit, category, min_importance)` - Semantic search
- `list_memories(category, tags, limit, offset)` - Non-semantic filtering
- `delete_memory(memory_id)` - Delete by UUID

**Validation**:
- Categories: `preference`, `fact`, `event`, `workflow`, `context`, `error`, `decision`
- Importance: 0.0-1.0 (no silent clamping, explicit error)
- Content max length: 10,000 characters (explicit error, no truncation)
- Tags: max 20 tags, max 50 chars each

### 2. GHAP Tools

**Source**: `src/clams/server/tools/ghap.py`, `src/clams/observation/`

**Components to port**:
- `ObservationCollector` - Local state machine with file-based persistence
- `ObservationPersister` - Embeds resolved GHAP entries to Qdrant
- GHAP models (GHAPEntry, Outcome, RootCause, Lesson, ConfidenceTier)

**Architecture**:
```
                    ┌─────────────────┐
                    │  MCP Tool Call  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ghap.py tools  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
│ ObservationCol- │ │ ObservationPer- │ │    Qdrant       │
│ lector (local)  │ │ sister (embed)  │ │  (ghap_* cols)  │
└────────┬────────┘ └────────┬────────┘ └─────────────────┘
         │                   │
┌────────▼────────┐ ┌────────▼────────┐
│ ~/.calm/journal │ │ Nomic Embedder  │
│ current_ghap.json│ └─────────────────┘
│ session_entries │
└─────────────────┘
```

**Tools**:
- `start_ghap(domain, strategy, goal, hypothesis, action, prediction)` - Begin tracking
- `update_ghap(hypothesis, action, prediction, strategy, note)` - Update active GHAP
- `resolve_ghap(status, result, surprise, root_cause, lesson)` - Mark complete
- `get_active_ghap()` - Get current active entry
- `list_ghap_entries(limit, domain, outcome, since)` - List from Qdrant

**Key behavior**:
- Only one active GHAP at a time (enforced by collector)
- State persisted to `~/.calm/journal/current_ghap.json`
- Resolved entries embedded to Qdrant `ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause` collections
- Confidence tier computed from iteration count and outcome

### 3. Code Indexing Tools

**Source**: `src/clams/indexers/`, `src/clams/server/tools/code.py`

**Components**:
- `TreeSitterParser` - Parse code into semantic units (functions, classes)
- `CodeIndexer` - Index files/directories, manage embeddings
- Metadata tracking in SQLite for change detection

**Tools**:
- `index_codebase(directory, project, recursive)` - Index source files
- `search_code(query, project, language, limit)` - Semantic search
- `find_similar_code(snippet, project, limit)` - Find similar code

**Embedding model**: MiniLM (384-dim, optimized for code)

**Index workflow**:
1. Parse files with tree-sitter
2. Extract semantic units (functions, classes, methods)
3. Check file hash against SQLite metadata (skip unchanged)
4. Embed units in batches
5. Store in Qdrant `code_units` collection
6. Update SQLite metadata

### 4. Git Tools

**Source**: `src/clams/git/`, `src/clams/server/tools/git.py`

**Components**:
- `GitPythonReader` - Read commits, blame info
- `GitAnalyzer` - Index commits, compute churn

**Tools**:
- `index_commits(since, limit, force)` - Index commits for search
- `search_commits(query, author, since, limit)` - Semantic search
- `get_file_history(path, limit)` - File commit history
- `get_churn_hotspots(days, limit)` - High-change files
- `get_code_authors(path)` - File author statistics

**Embedding model**: Nomic (768-dim, semantic content)

### 5. Learning Tools (Clustering, Values)

**Source**: `src/clams/clustering/`, `src/clams/values/`, `src/clams/server/tools/learning.py`

**Components**:
- `Clusterer` - HDBSCAN clustering algorithm
- `ExperienceClusterer` - Cluster GHAP experiences by axis
- `ValueStore` - Store/validate value statements

**Tools**:
- `get_clusters(axis)` - Get cluster info for axis
- `get_cluster_members(cluster_id, limit)` - Experiences in cluster
- `validate_value(text, cluster_id)` - Check value against centroid
- `store_value(text, cluster_id, axis)` - Store validated value
- `list_values(axis, limit)` - List stored values

**Important**: Values are stored in Qdrant `values` collection, NOT SQLite. Clustering is computed at query time from GHAP embeddings.

### 6. Context Assembly Tool

**Source**: `src/clams/context/`, `src/clams/server/tools/context.py`

**Components**:
- `ContextAssembler` - Query multiple sources, deduplicate, format
- Token budgeting and distribution
- Markdown formatting

**Tool**:
- `assemble_context(query, context_types, limit, max_tokens)` - Build context

**Features**:
- Parallel queries to multiple sources
- Fuzzy deduplication across sources
- Token budget distribution by source weight
- Item truncation when over budget

### 7. Session Helpers

**Source**: `src/clams/server/tools/session.py`

**Tools**:
- `ping()` - Health check
- `start_session()` - Initialize session, generate session ID
- `get_orphaned_ghap()` - Check for GHAP from previous session
- `should_check_in(frequency)` - Check if reminder due
- `increment_tool_count()` - Track tool calls
- `reset_tool_count()` - Reset after reminder shown

**Session state**:
- Session ID in `~/.calm/journal/.session_id`
- Tool count in `~/.calm/journal/.tool_count`
- Current GHAP in `~/.calm/journal/current_ghap.json`

## Database Integration

### SQLite (`~/.calm/metadata.db`)

The schema from SPEC-058-01 provides these tables for memory/GHAP:

```sql
-- Code indexing metadata
CREATE TABLE code_files (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    project TEXT NOT NULL,
    language TEXT,
    file_hash TEXT NOT NULL,
    unit_count INTEGER DEFAULT 0,
    last_modified TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_path, project)
);

-- Git commit indexing
CREATE TABLE commits (
    id INTEGER PRIMARY KEY,
    sha TEXT UNIQUE NOT NULL,
    message TEXT NOT NULL,
    author TEXT,
    author_email TEXT,
    timestamp TIMESTAMP NOT NULL,
    files_changed INTEGER DEFAULT 0,
    insertions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    embedding_id TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings storage
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**MetadataStore interface**:
```python
class MetadataStore:
    async def initialize() -> None
    async def close() -> None
    async def add_indexed_file(file_path, project, language, file_hash, unit_count, last_modified) -> None
    async def get_indexed_file(file_path, project) -> IndexedFile | None
    async def delete_indexed_file(file_path, project) -> None
    async def list_indexed_files(project=None) -> list[IndexedFile]
    async def delete_project(project) -> None
    async def add_commit(sha, message, author, timestamp, ...) -> None
    async def get_commit(sha) -> Commit | None
    async def get_indexed_commits() -> set[str]
```

### Qdrant Collections

All collections use the shared Qdrant instance (default: `http://localhost:6333`):

| Collection | Content | Dimension | Metric | Notes |
|------------|---------|-----------|--------|-------|
| `memories` | Memory embeddings | 768 | Cosine | Nomic embedder |
| `code_units` | Code snippet embeddings | 384 | Cosine | MiniLM embedder |
| `commits` | Commit message embeddings | 768 | Cosine | Nomic embedder |
| `ghap_full` | Full GHAP entry text | 768 | Cosine | For general search |
| `ghap_strategy` | Strategy-focused text | 768 | Cosine | For strategy patterns |
| `ghap_surprise` | Surprise descriptions | 768 | Cosine | For unexpected outcomes |
| `ghap_root_cause` | Root cause descriptions | 768 | Cosine | For failure patterns |
| `values` | Value statement embeddings | 768 | Cosine | Learnings from clusters |

**QdrantVectorStore interface**:
```python
class VectorStore(Protocol):
    async def create_collection(name, dimension, distance="cosine") -> None
    async def delete_collection(name) -> None
    async def upsert(collection, id, vector, payload) -> None
    async def search(collection, query, limit=10, filters=None) -> list[SearchResult]
    async def scroll(collection, limit=100, filters=None, with_vectors=False) -> list[SearchResult]
    async def delete(collection, id) -> None
    async def count(collection, filters=None) -> int
    async def get(collection, id, with_vector=False) -> SearchResult | None
    async def get_collection_info(name) -> CollectionInfo | None
```

## Configuration

### CalmSettings (extends SPEC-058-01)

```python
# src/calm/config.py
from pydantic_settings import BaseSettings

class CalmSettings(BaseSettings):
    """CALM configuration."""
    # From SPEC-058-01
    home: Path = Path.home() / ".calm"
    db_path: Path = Path.home() / ".calm" / "metadata.db"
    server_host: str = "127.0.0.1"
    server_port: int = 6335
    log_level: str = "info"

    # New for SPEC-058-02
    qdrant_url: str = "http://localhost:6333"
    qdrant_timeout: float = 30.0
    journal_path: Path = Path.home() / ".calm" / "journal"

    # Embedding models
    code_embedding_model: str = "all-MiniLM-L6-v2"  # 384-dim
    semantic_embedding_model: str = "nomic-embed-text-v1.5"  # 768-dim

    # Tool limits
    memory_content_max_length: int = 10_000
    snippet_max_length: int = 5_000
    project_id_max_length: int = 100

    # Indexing
    embedding_batch_size: int = 100

    # Context assembly
    context_max_item_fraction: float = 0.25
    context_similarity_threshold: float = 0.90

    model_config = SettingsConfigDict(env_prefix="CALM_")
```

Environment variable overrides:
- `CALM_QDRANT_URL` - Qdrant server URL
- `CALM_LOG_LEVEL` - Logging level
- `CALM_SEMANTIC_EMBEDDING_MODEL` - Model for semantic content
- `CALM_CODE_EMBEDDING_MODEL` - Model for code content

## Testing Strategy

### Unit Tests

Each module gets comprehensive unit tests:

```
tests/calm/
├── tools/
│   ├── test_memory.py           # Memory tool functions
│   ├── test_ghap.py             # GHAP tool functions
│   ├── test_code.py             # Code indexing tools
│   ├── test_git.py              # Git tools
│   ├── test_learning.py         # Clustering/value tools
│   ├── test_search.py           # Search tools
│   ├── test_context.py          # Context assembly
│   └── test_session.py          # Session helpers
├── storage/
│   ├── test_qdrant.py           # VectorStore tests
│   └── test_metadata.py         # MetadataStore tests
├── ghap/
│   ├── test_collector.py        # ObservationCollector
│   ├── test_persister.py        # ObservationPersister
│   └── test_models.py           # GHAP data models
├── indexers/
│   ├── test_indexer.py          # CodeIndexer
│   └── test_tree_sitter.py      # Parser tests
├── git/
│   ├── test_reader.py           # GitPythonReader
│   └── test_analyzer.py         # GitAnalyzer
├── clustering/
│   ├── test_clusterer.py        # HDBSCAN clustering
│   └── test_experience.py       # ExperienceClusterer
├── values/
│   └── test_store.py            # ValueStore
├── context/
│   ├── test_assembler.py        # ContextAssembler
│   ├── test_tokens.py           # Token estimation
│   └── test_deduplication.py    # Fuzzy dedup
└── embedding/
    └── test_registry.py         # Model loading
```

### Test Fixtures

```python
@pytest.fixture
def mock_vector_store():
    """In-memory QdrantVectorStore for testing."""
    return QdrantVectorStore(url=":memory:")

@pytest.fixture
def mock_embedder():
    """Mock embedder returning fixed-dimension vectors."""
    return MockEmbeddingService(dimension=768)

@pytest.fixture
def tmp_calm_home(tmp_path):
    """Temporary CALM home directory."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()
    (calm_home / "journal").mkdir()
    return calm_home

@pytest.fixture
def services(mock_vector_store, mock_embedder, tmp_calm_home):
    """ServiceContainer with mocked dependencies."""
    return ServiceContainer(
        code_embedder=MockEmbeddingService(dimension=384),
        semantic_embedder=mock_embedder,
        vector_store=mock_vector_store,
        metadata_store=MetadataStore(db_path=tmp_calm_home / "metadata.db"),
    )
```

### Integration Tests

```python
# tests/calm/test_integration.py

async def test_memory_roundtrip(services):
    """Store and retrieve a memory."""
    tools = get_memory_tools(services)

    # Store
    result = await tools["store_memory"](
        content="Python uses indentation for blocks",
        category="fact",
        importance=0.8,
    )
    assert result["status"] == "stored"
    memory_id = result["id"]

    # Retrieve
    result = await tools["retrieve_memories"](query="Python syntax")
    assert len(result["results"]) >= 1
    assert any(r["id"] == memory_id for r in result["results"])

async def test_ghap_lifecycle(services, tmp_calm_home):
    """Complete GHAP lifecycle: start -> update -> resolve."""
    collector = ObservationCollector(journal_dir=tmp_calm_home / "journal")
    persister = ObservationPersister(
        embedding_service=services.semantic_embedder,
        vector_store=services.vector_store,
    )
    tools = get_ghap_tools(collector, persister)

    # Start
    result = await tools["start_ghap"](
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix failing test",
        hypothesis="The mock is returning wrong value",
        action="Inspect mock configuration",
        prediction="Will find misconfigured return_value",
    )
    assert result["ok"]

    # Update
    result = await tools["update_ghap"](
        hypothesis="The mock is not being called",
        note="Added logging, mock never invoked",
    )
    assert result["success"]

    # Resolve
    result = await tools["resolve_ghap"](
        status="confirmed",
        result="Found mock was patching wrong module path",
    )
    assert result["ok"]
```

## Migration Notes

### Data Migration

Users with existing clams data have two options:

1. **Keep both**: Run clams and calm in parallel. They use separate directories (`~/.clams/` vs `~/.calm/`) and can share the same Qdrant instance.

2. **Migrate**: Copy Qdrant collections. The collection names are the same, so a user could:
   ```bash
   # No code migration needed - collections are shared
   # SQLite data (file metadata) can be rebuilt by re-indexing
   calm init
   calm index-codebase /path/to/project my-project
   calm index-commits
   ```

### Embedding Model Compatibility

**Critical**: calm must use the same embedding models as clams for shared Qdrant collections:
- Semantic content: `nomic-embed-text-v1.5` (768-dim)
- Code content: `all-MiniLM-L6-v2` (384-dim)

Using different models would corrupt existing indexes due to dimension mismatches.

### Path Changes

| clams path | calm path |
|------------|-----------|
| `~/.clams/` | `~/.calm/` |
| `~/.clams/clams.db` | `~/.calm/metadata.db` |
| `~/.clams/journal/` | `~/.calm/journal/` |
| `~/.clams/journal/current_ghap.json` | `~/.calm/journal/current_ghap.json` |

## Implementation Order

1. **Storage layer** (storage/, embedding/)
   - Port VectorStore interface and QdrantVectorStore
   - Port EmbeddingService interface and implementations
   - Port MetadataStore

2. **GHAP subsystem** (ghap/)
   - Port models, collector, persister
   - Test GHAP lifecycle

3. **Memory tools** (tools/memory.py)
   - Port memory CRUD operations
   - Test with mock embedder

4. **GHAP tools** (tools/ghap.py)
   - Wire up collector and persister
   - Test full lifecycle

5. **Indexing** (indexers/, git/)
   - Port tree-sitter parser
   - Port CodeIndexer
   - Port GitPythonReader and GitAnalyzer

6. **Code/Git tools** (tools/code.py, tools/git.py)
   - Wire up indexers
   - Test indexing and search

7. **Learning** (clustering/, values/)
   - Port Clusterer and ExperienceClusterer
   - Port ValueStore
   - Test clustering on mock data

8. **Learning tools** (tools/learning.py)
   - Wire up clustering and values
   - Test full workflow

9. **Search and Context** (search/, context/)
   - Port Searcher
   - Port ContextAssembler
   - Wire up tools

10. **Session helpers** (tools/session.py)
    - Port session management
    - Test tool counting

11. **Tool registration** (tools/__init__.py, server/app.py)
    - Create ServiceContainer
    - Register all tools with MCP server
    - Integration test full server

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Embedding model mismatch | Index corruption | Validate model names match exactly |
| Path confusion | Wrong data accessed | Clear documentation, distinct dir names |
| Qdrant connection issues | Tools fail | Graceful degradation, clear error messages |
| Tree-sitter language support | Missing languages | Document supported languages |
| Large index operations | Timeout/memory | Batching, progress feedback |

## File Changes Summary

| Category | Files | Notes |
|----------|-------|-------|
| New modules | ~40 files | Ported from clams |
| Modified | `src/calm/config.py` | Add new settings |
| Modified | `src/calm/server/app.py` | Register tools |
| Modified | `pyproject.toml` | No changes needed |
| Tests | ~25 test files | Comprehensive coverage |

## Estimated Complexity

**Medium-High**. While this is primarily a port (proven code), the scope is significant:
- 30+ tools to wire up
- Multiple subsystems (storage, embedding, indexing, clustering)
- Integration testing across components

The complexity is mitigated by:
- Existing working code to reference
- Clear architectural patterns from clams
- Module-by-module testing approach
