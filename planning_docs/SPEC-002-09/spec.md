# SPEC-002-09: Searcher Unified Query Interface

## Overview

Implement the Searcher module, which provides a unified query interface across all vector collections in the Learning Memory Server. The Searcher abstracts the complexity of collection-specific queries and filtering, presenting a clean, type-safe API for semantic search across memories, code, experiences, values, and commits.

## Dependencies

- SPEC-002-02: EmbeddingService (completed)
- SPEC-002-03: VectorStore (completed)
- SPEC-002-04: SQLite metadata store (completed)

## Purpose

The Searcher serves as the single entry point for all semantic search operations. It:

1. **Unifies query interfaces** - One consistent API for all collection types
2. **Handles embedding generation** - Automatically embeds query text using EmbeddingService
3. **Applies collection-specific filters** - Translates high-level filters to VectorStore format
4. **Maps results to typed dataclasses** - Converts raw SearchResult to domain-specific types
5. **Provides collection naming** - Encapsulates collection name conventions

## Interface Definitions

### Searcher Class

```python
class Searcher:
    """Unified query interface across all vector collections."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ):
        """
        Initialize searcher with dependencies.

        Args:
            embedding_service: Service for embedding query text
            vector_store: Vector storage backend
        """
        ...

    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryResult]:
        """
        Search verified memory entries.

        Args:
            query: Search query text
            category: Optional filter by memory category
            limit: Maximum results to return

        Returns:
            List of memory search results ordered by relevance
        """
        ...

    async def search_code(
        self,
        query: str,
        project: str | None = None,
        language: str | None = None,
        unit_type: str | None = None,
        limit: int = 10,
    ) -> list[CodeResult]:
        """
        Search indexed code units.

        Args:
            query: Search query text
            project: Optional filter by project name
            language: Optional filter by programming language
            unit_type: Optional filter by unit type (function, class, method)
            limit: Maximum results to return

        Returns:
            List of code search results ordered by relevance
        """
        ...

    async def search_experiences(
        self,
        query: str,
        axis: str = "full",
        domain: str | None = None,
        outcome: str | None = None,
        limit: int = 10,
    ) -> list[ExperienceResult]:
        """
        Search GHAP experiences across clustering axes.

        Args:
            query: Search query text
            axis: Clustering axis (full, domain, strategy, surprise, root_cause)
            domain: Optional filter by domain
            outcome: Optional filter by outcome status (confirmed, falsified, abandoned)
            limit: Maximum results to return

        Returns:
            List of experience search results ordered by relevance
        """
        ...

    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
    ) -> list[ValueResult]:
        """
        Search emergent values.

        Args:
            query: Search query text
            axis: Optional filter by axis (domain, strategy, surprise, root_cause)
            limit: Maximum results to return (default 5, values are sparse)

        Returns:
            List of value search results ordered by relevance
        """
        ...

    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[CommitResult]:
        """
        Search git commit messages and diffs.

        Args:
            query: Search query text
            author: Optional filter by commit author
            since: Optional filter by minimum commit date
            limit: Maximum results to return

        Returns:
            List of commit search results ordered by relevance
        """
        ...
```

## Result Dataclasses

### MemoryResult

```python
@dataclass
class MemoryResult:
    """Result from memory search."""

    id: str
    category: str
    content: str
    score: float
    tags: list[str]
    created_at: datetime
    verified_at: datetime | None
    verification_status: str | None  # "passed", "failed", "pending", None
```

### CodeResult

```python
@dataclass
class CodeResult:
    """Result from code search."""

    id: str
    project: str
    file_path: str
    language: str
    unit_type: str  # "function", "class", "method"
    qualified_name: str
    code: str
    docstring: str | None
    score: float
    line_start: int
    line_end: int
```

### ExperienceResult

```python
@dataclass
class ExperienceResult:
    """Result from experience search."""

    id: str
    ghap_id: str
    axis: str
    domain: str
    strategy: str
    goal: str
    hypothesis: str
    action: str
    prediction: str
    outcome_status: str  # "confirmed", "falsified", "abandoned"
    outcome_result: str
    surprise: str | None
    root_cause: RootCause | None
    lesson: Lesson | None
    confidence_tier: str
    iteration_count: int
    score: float
    created_at: datetime

@dataclass
class RootCause:
    category: str
    description: str

@dataclass
class Lesson:
    what_worked: str
    takeaway: str | None
```

### ValueResult

```python
@dataclass
class ValueResult:
    """Result from value search."""

    id: str
    axis: str
    cluster_id: str
    text: str
    score: float
    member_count: int
    avg_confidence: float
    created_at: datetime
```

### CommitResult

```python
@dataclass
class CommitResult:
    """Result from commit search."""

    id: str
    sha: str
    message: str
    author: str
    author_email: str
    committed_at: datetime
    files_changed: list[str]
    score: float
```

## Collection Naming Conventions

The Searcher encapsulates collection naming:

```python
class CollectionName:
    """Collection name constants."""

    MEMORIES = "memories"
    CODE = "code"
    EXPERIENCES_FULL = "experiences_full"
    EXPERIENCES_DOMAIN = "experiences_domain"
    EXPERIENCES_STRATEGY = "experiences_strategy"
    EXPERIENCES_SURPRISE = "experiences_surprise"
    EXPERIENCES_ROOT_CAUSE = "experiences_root_cause"
    VALUES = "values"
    COMMITS = "commits"
```

Experience axis values map to collections:
- `"full"` → `"experiences_full"`
- `"domain"` → `"experiences_domain"`
- `"strategy"` → `"experiences_strategy"`
- `"surprise"` → `"experiences_surprise"`
- `"root_cause"` → `"experiences_root_cause"`

## Filter Specifications

### VectorStore Filter Format

The VectorStore expects filters as nested dictionaries:

```python
# Simple equality filter
filters = {"category": "preference"}

# Multiple filters (AND)
filters = {
    "project": "my-project",
    "language": "python"
}

# Range filter (for dates)
filters = {
    "committed_at": {"$gte": "2024-01-01T00:00:00Z"}
}
```

### Filter Translation

The Searcher translates method parameters to VectorStore filters:

```python
# search_memories(query="...", category="preference")
# → filters = {"category": "preference"}

# search_code(query="...", project="clams", language="python")
# → filters = {"project": "clams", "language": "python"}

# search_experiences(query="...", domain="debugging", outcome="confirmed")
# → filters = {"domain": "debugging", "outcome_status": "confirmed"}

# search_commits(query="...", author="alice", since=datetime(2024, 1, 1))
# → filters = {"author": "alice", "committed_at": {"$gte": "2024-01-01T00:00:00Z"}}
```

## Performance Requirements

### Query Latency

- **Target**: <100ms for typical queries (p95)
- **Maximum**: <500ms for complex filtered queries (p99)
- **Embedding time**: ~20-50ms per query (model dependent)
- **Vector search time**: ~30-100ms (collection size dependent)

### Throughput

- **Concurrent queries**: Support 10+ concurrent searches
- **Batch efficiency**: Not required (queries are independent)
- **Cache strategy**: No caching in v1 (embedding service may cache internally)

### Scalability

- **Collection sizes**:
  - Memories: 1k-10k entries
  - Code: 10k-100k units
  - Experiences: 100-10k entries
  - Values: 10-100 entries
  - Commits: 1k-100k commits

- **Result limits**: Respect caller-provided limits (default: 5-10)
- **Memory usage**: Stream results from VectorStore, don't load all into memory

## Error Handling

```python
class SearchError(Exception):
    """Base exception for search operations."""
    pass

class InvalidAxisError(SearchError):
    """Raised when an invalid experience axis is specified."""
    pass

class CollectionNotFoundError(SearchError):
    """Raised when a collection doesn't exist."""
    pass

class EmbeddingError(SearchError):
    """Raised when query embedding fails."""
    pass
```

**Error scenarios**:

1. **Invalid axis**: Raise `InvalidAxisError` with valid options
2. **Missing collection**: Raise `CollectionNotFoundError` with collection name
3. **Embedding failure**: Raise `EmbeddingError` wrapping original exception
4. **Empty query**: Return empty list (not an error)
5. **VectorStore errors**: Propagate with context

## Testing Strategy

### Unit Tests

1. **Query embedding**: Verify embedding service is called with correct text
2. **Filter translation**: Test all parameter combinations map to correct filters
3. **Collection selection**: Verify axis names map to correct collections
4. **Result mapping**: Test payload-to-dataclass conversion for all types
5. **Error handling**: Test invalid axes, missing collections, embedding failures
6. **Limit enforcement**: Verify result count respects limit parameter

### Integration Tests

1. **End-to-end search**: Populate collections, search, verify results
2. **Filter combinations**: Test multiple filters applied correctly
3. **Multi-axis experiences**: Search same query across different axes
4. **Empty results**: Query non-existent data returns empty list
5. **Score ordering**: Verify results are sorted by relevance score

### Test Fixtures

```python
@pytest.fixture
async def mock_embedding_service():
    """Mock embedding service returning fixed vectors."""
    ...

@pytest.fixture
async def mock_vector_store():
    """Mock vector store with test data."""
    ...

@pytest.fixture
async def searcher(mock_embedding_service, mock_vector_store):
    """Create searcher with mocked dependencies."""
    return Searcher(mock_embedding_service, mock_vector_store)
```

## Acceptance Criteria

### Functional

1. Can search memories with category filter
2. Can search code with project, language, and unit_type filters
3. Can search experiences across all 5 axes
4. Can search experiences with domain and outcome filters
5. Can search values with optional axis filter
6. Can search commits with author and date filters
7. Results are ordered by score (descending)
8. Result count respects limit parameter
9. Empty query returns empty list
10. Invalid axis raises InvalidAxisError

### Result Mapping

1. MemoryResult includes all fields from payload
2. CodeResult includes file path, qualified name, code content
3. ExperienceResult includes full GHAP data
4. ValueResult includes cluster metadata
5. CommitResult includes commit metadata and file list
6. All datetime fields are parsed correctly
7. Optional fields (docstring, surprise, etc.) handle None

### Error Handling

1. Invalid axis raises clear error with valid options
2. Missing collection raises CollectionNotFoundError
3. Embedding failure propagates with context
4. VectorStore errors propagate with collection name
5. All errors include helpful messages for debugging

### Performance

1. Typical queries complete in <100ms (p95)
2. Can handle 10+ concurrent searches
3. Memory usage is bounded (no loading entire collections)
4. Results stream from VectorStore efficiently

### Code Quality

1. All public methods have docstrings
2. Type hints on all parameters and returns
3. Passes mypy strict type checking
4. Passes ruff linting
5. Test coverage ≥ 90%

## Out of Scope

- **Caching**: No query result caching in v1
- **Ranking customization**: Use VectorStore's default scoring
- **Hybrid search**: No keyword + vector hybrid in v1
- **Pagination**: Caller can implement by adjusting limit/offset at VectorStore level
- **Aggregations**: No faceting or aggregations in v1
- **Query rewriting**: No automatic query expansion or correction
- **Multi-collection search**: Each method searches one collection/axis

## Notes

- All async operations (consistent with codebase async guidelines)
- All datetime fields are timezone-aware UTC (consistent with metadata.py patterns)
- Result dataclasses use simple types (str, int, float, datetime) for easy serialization
- Collection name constants prevent typos and enable refactoring
- Filter translation keeps collection schema knowledge internal to Searcher
- Searcher is stateless - no session management or cached embeddings
