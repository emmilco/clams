# Technical Proposal: Searcher Unified Query Interface

## Problem Statement

The Learning Memory Server stores data across multiple vector collections (memories, code, experiences, values, commits), each with different schemas and filtering requirements. Direct use of the VectorStore API requires:

1. **Manual embedding generation** - Caller must embed query text before search
2. **Collection name management** - Caller must know exact collection names
3. **Filter format knowledge** - Caller must construct VectorStore filter dicts
4. **Raw result parsing** - Caller must map generic SearchResult to domain types
5. **No type safety** - Easy to query wrong collection or use wrong filters

This creates significant friction for higher-level components (ContextAssembler, MCP tools) and violates the DRY principle across the codebase.

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Tools / Context Assembler            │
│                                                                  │
│  • Simple typed API calls                                       │
│  • No embedding logic                                           │
│  • No collection name knowledge                                 │
│  • Strongly-typed results                                       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                           Searcher                               │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │ Query Embed    │  │ Filter Build   │  │ Result Map     │    │
│  │ Generation     │  │ Translation    │  │ Conversion     │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EmbeddingService + VectorStore                │
└─────────────────────────────────────────────────────────────────┘
```

The Searcher acts as a **facade** that:
1. Accepts high-level typed queries
2. Generates embeddings from query text
3. Translates filters to VectorStore format
4. Selects correct collection
5. Maps raw results to typed dataclasses

### Module Structure

```
search/
├── __init__.py          # Public exports
├── searcher.py          # Searcher class implementation
├── results.py           # Result dataclasses
├── collections.py       # Collection name constants
└── filters.py           # Filter translation helpers
```

**`__init__.py` exports:**
```python
"""Unified query interface for semantic search."""

from .searcher import Searcher, SearchError, InvalidAxisError, CollectionNotFoundError, EmbeddingError
from .results import (
    MemoryResult,
    CodeResult,
    ExperienceResult,
    ValueResult,
    CommitResult,
    RootCause,
    Lesson,
)
from .collections import CollectionName

__all__ = [
    "Searcher",
    "SearchError",
    "InvalidAxisError",
    "CollectionNotFoundError",
    "EmbeddingError",
    "MemoryResult",
    "CodeResult",
    "ExperienceResult",
    "ValueResult",
    "CommitResult",
    "RootCause",
    "Lesson",
    "CollectionName",
]
```

### Key Design Decisions

#### 1. Separation of Result Types

Each search method returns a specific result dataclass:

```python
# results.py

@dataclass
class MemoryResult:
    """Typed result for memory searches."""
    id: str
    category: str
    content: str
    score: float
    tags: list[str]
    created_at: datetime
    verified_at: datetime | None
    verification_status: str | None

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "MemoryResult":
        """Convert VectorStore SearchResult to MemoryResult."""
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            category=payload["category"],
            content=payload["content"],
            tags=payload.get("tags", []),
            created_at=datetime.fromisoformat(payload["created_at"]),
            verified_at=datetime.fromisoformat(payload["verified_at"]) if payload.get("verified_at") else None,
            verification_status=payload.get("verification_status"),
        )
```

**Rationale**:
- **Type safety** - Each result type has specific fields relevant to that domain
- **Clear contracts** - Callers know exactly what fields are available
- **Easy serialization** - Simple dataclasses serialize to JSON naturally
- **Documentation** - Type hints serve as inline documentation
- **Evolution** - Can add fields to specific types without affecting others

#### 2. Filter Translation Layer

Filters are translated from method parameters to VectorStore dict format:

```python
# filters.py

def build_filters(**kwargs) -> dict[str, Any] | None:
    """
    Build VectorStore filter dict from keyword arguments.

    Args:
        **kwargs: Filter parameters (None values are ignored)

    Returns:
        Filter dict or None if no filters specified
    """
    filters = {}
    for key, value in kwargs.items():
        if value is not None:
            if isinstance(value, datetime):
                # Date filters use $gte operator
                filters[key] = {"$gte": value.isoformat()}
            else:
                # Simple equality filter
                filters[key] = value

    return filters if filters else None
```

**Usage in Searcher**:

```python
async def search_code(
    self,
    query: str,
    project: str | None = None,
    language: str | None = None,
    unit_type: str | None = None,
    limit: int = 10,
) -> list[CodeResult]:
    """Search code with filters."""
    # Generate embedding
    query_vector = await self.embedding_service.embed(query)

    # Build filters
    filters = build_filters(
        project=project,
        language=language,
        unit_type=unit_type,
    )

    # Search
    results = await self.vector_store.search(
        collection=CollectionName.CODE,
        query=query_vector,
        limit=limit,
        filters=filters,
    )

    # Map results
    return [CodeResult.from_search_result(r) for r in results]
```

**Rationale**:
- **DRY** - Single filter building logic used by all search methods
- **Consistent** - All filters follow same translation rules
- **Extensible** - Easy to add new filter operators (e.g., $in, $range)
- **Testable** - Filter building is independently testable

#### 3. Collection Name Constants

```python
# collections.py

class CollectionName:
    """Collection name constants for all vector stores.

    Using a class with string constants (not Enum) for:
    - Simple string usage without .value
    - Easy typing in function signatures
    - Clear namespace grouping
    """

    MEMORIES = "memories"
    CODE = "code"
    EXPERIENCES_FULL = "experiences_full"
    EXPERIENCES_DOMAIN = "experiences_domain"
    EXPERIENCES_STRATEGY = "experiences_strategy"
    EXPERIENCES_SURPRISE = "experiences_surprise"
    EXPERIENCES_ROOT_CAUSE = "experiences_root_cause"
    VALUES = "values"
    COMMITS = "commits"

    # Experience axis mapping
    EXPERIENCE_AXES = {
        "full": EXPERIENCES_FULL,
        "domain": EXPERIENCES_DOMAIN,
        "strategy": EXPERIENCES_STRATEGY,
        "surprise": EXPERIENCES_SURPRISE,
        "root_cause": EXPERIENCES_ROOT_CAUSE,
    }

    @classmethod
    def get_experience_collection(cls, axis: str) -> str:
        """
        Get collection name for experience axis.

        Args:
            axis: Experience clustering axis

        Returns:
            Collection name

        Raises:
            InvalidAxisError: If axis is not valid
        """
        if axis not in cls.EXPERIENCE_AXES:
            valid = ", ".join(cls.EXPERIENCE_AXES.keys())
            raise InvalidAxisError(
                f"Invalid axis '{axis}'. Valid axes: {valid}"
            )
        return cls.EXPERIENCE_AXES[axis]
```

**Rationale**:
- **Single source of truth** - Collection names defined in one place
- **Refactoring safety** - Renaming collections requires changes in one file only
- **Type hints** - Can use `CollectionName.CODE` in type annotations
- **Validation** - Experience axis validation centralized
- **Not an Enum** - Simple strings are easier to use than enum values

#### 4. Async-First Design

All search methods are `async def`:

```python
class Searcher:
    async def search_memories(self, query: str, ...) -> list[MemoryResult]:
        """Search memories asynchronously."""
        # Embed query (async)
        query_vector = await self.embedding_service.embed(query)

        # Search (async)
        results = await self.vector_store.search(...)

        # Map results (sync, fast)
        return [MemoryResult.from_search_result(r) for r in results]
```

**Rationale**:
- **Consistency** - Matches codebase async guidelines (see parent spec)
- **Composability** - Can be used in async contexts without bridging
- **Concurrency** - Caller can run multiple searches concurrently with `asyncio.gather`
- **Non-blocking** - Embedding and vector search are I/O operations

#### 5. Stateless Design

The Searcher maintains no state between calls:

```python
class Searcher:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ):
        """Initialize with dependencies only."""
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        # No state fields, no caching, no session tracking
```

**Rationale**:
- **Thread-safe** - No shared mutable state
- **Simple testing** - No state to reset between tests
- **Predictable** - Same query always produces same results
- **Composable** - Multiple components can share one Searcher instance

**Trade-off**: No query caching. If caching is needed in v2, it would be added as a separate layer (decorator pattern) rather than in Searcher itself.

### Implementation Details

#### Error Handling Strategy

```python
# searcher.py

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


async def search_experiences(
    self,
    query: str,
    axis: str = "full",
    domain: str | None = None,
    outcome: str | None = None,
    limit: int = 10,
) -> list[ExperienceResult]:
    """Search experiences with comprehensive error handling."""
    try:
        # Get collection name (validates axis)
        collection = CollectionName.get_experience_collection(axis)
    except InvalidAxisError:
        # Re-raise with no wrapping (already has good message)
        raise

    try:
        # Generate embedding
        query_vector = await self.embedding_service.embed(query)
    except Exception as e:
        raise EmbeddingError(f"Failed to embed query: {e}") from e

    try:
        # Build filters
        filters = build_filters(domain=domain, outcome_status=outcome)

        # Search
        results = await self.vector_store.search(
            collection=collection,
            query=query_vector,
            limit=limit,
            filters=filters,
        )
    except Exception as e:
        # Check if collection doesn't exist
        if "collection not found" in str(e).lower():
            raise CollectionNotFoundError(
                f"Collection '{collection}' not found. "
                "Ensure experiences have been indexed."
            ) from e
        # Other VectorStore errors propagate
        raise

    # Map results
    return [ExperienceResult.from_search_result(r) for r in results]
```

**Error Handling Principles**:
1. **Specific exceptions** - Use custom exceptions for known failure modes
2. **Context preservation** - Use `from e` to maintain exception chain
3. **Helpful messages** - Include collection name, axis, etc. in error text
4. **Early validation** - Check axis before doing expensive operations
5. **Propagate unknowns** - Don't catch exceptions we can't handle

#### Result Mapping Pattern

All result dataclasses follow the same pattern:

```python
@dataclass
class CodeResult:
    """Result from code search."""
    id: str
    project: str
    file_path: str
    language: str
    unit_type: str
    qualified_name: str
    code: str
    docstring: str | None
    score: float
    line_start: int
    line_end: int

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "CodeResult":
        """
        Convert VectorStore SearchResult to CodeResult.

        Args:
            result: Raw search result from VectorStore

        Returns:
            Typed CodeResult instance

        Raises:
            KeyError: If required payload fields are missing
            ValueError: If field values are invalid
        """
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            project=payload["project"],
            file_path=payload["file_path"],
            language=payload["language"],
            unit_type=payload["unit_type"],
            qualified_name=payload["qualified_name"],
            code=payload["code"],
            docstring=payload.get("docstring"),  # Optional field
            line_start=payload["line_start"],
            line_end=payload["line_end"],
        )
```

**Mapping Principles**:
1. **Explicit field mapping** - No `**payload` spreading, clear what comes from where
2. **Optional field handling** - Use `.get()` for fields that may be absent
3. **Type conversion** - Handle datetime parsing, list conversion, etc.
4. **Validation** - Let KeyError/ValueError propagate if data is malformed
5. **Classmethod pattern** - Keeps instantiation logic with the class

#### Datetime Handling

All datetime fields use timezone-aware UTC datetimes:

```python
@dataclass
class MemoryResult:
    created_at: datetime
    verified_at: datetime | None

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "MemoryResult":
        payload = result.payload
        return cls(
            # ... other fields ...
            created_at=datetime.fromisoformat(payload["created_at"]),
            verified_at=(
                datetime.fromisoformat(payload["verified_at"])
                if payload.get("verified_at")
                else None
            ),
        )
```

**Datetime Conventions**:
- Stored as ISO 8601 strings in VectorStore payload
- Parsed to timezone-aware datetime objects
- Always UTC (consistent with codebase standards)
- Optional fields use `| None` type hint
- Use `fromisoformat()` for parsing (handles both 'Z' and '+00:00')

### Testing Strategy

#### Unit Tests

**Test Categories**:

1. **Embedding Generation**
   ```python
   async def test_search_memories_calls_embed(searcher, mock_embedding_service):
       """Verify embedding service is called with query text."""
       await searcher.search_memories("test query")
       mock_embedding_service.embed.assert_called_once_with("test query")
   ```

2. **Filter Translation**
   ```python
   async def test_search_code_with_filters(searcher, mock_vector_store):
       """Verify filters are correctly translated."""
       await searcher.search_code(
           query="auth",
           project="clams",
           language="python",
       )
       mock_vector_store.search.assert_called_once()
       call_filters = mock_vector_store.search.call_args[1]["filters"]
       assert call_filters == {"project": "clams", "language": "python"}
   ```

3. **Collection Selection**
   ```python
   async def test_search_experiences_selects_correct_collection(
       searcher, mock_vector_store
   ):
       """Verify axis maps to correct collection."""
       await searcher.search_experiences(query="test", axis="domain")
       mock_vector_store.search.assert_called_once()
       assert mock_vector_store.search.call_args[1]["collection"] == "experiences_domain"
   ```

4. **Result Mapping**
   ```python
   async def test_memory_result_from_search_result():
       """Verify SearchResult maps to MemoryResult correctly."""
       search_result = SearchResult(
           id="mem_123",
           score=0.95,
           payload={
               "category": "preference",
               "content": "Use async/await",
               "tags": ["python", "async"],
               "created_at": "2024-01-01T12:00:00Z",
               "verified_at": None,
               "verification_status": None,
           },
       )
       result = MemoryResult.from_search_result(search_result)
       assert result.id == "mem_123"
       assert result.score == 0.95
       assert result.category == "preference"
       assert result.content == "Use async/await"
       assert result.tags == ["python", "async"]
       assert result.verified_at is None
   ```

5. **Error Handling**
   ```python
   async def test_invalid_axis_raises_error(searcher):
       """Verify invalid axis raises InvalidAxisError."""
       with pytest.raises(InvalidAxisError) as exc_info:
           await searcher.search_experiences(query="test", axis="invalid")
       assert "invalid" in str(exc_info.value).lower()
       assert "full" in str(exc_info.value)  # Shows valid axes
   ```

#### Integration Tests

**Test Scenarios**:

1. **End-to-end search**
   ```python
   async def test_search_code_integration(
       searcher, vector_store, embedding_service
   ):
       """Test full search flow with real dependencies."""
       # Setup: Index some code
       await index_test_code(vector_store, embedding_service)

       # Search
       results = await searcher.search_code(
           query="authentication function",
           language="python",
           limit=5,
       )

       # Verify
       assert len(results) <= 5
       assert all(isinstance(r, CodeResult) for r in results)
       assert all(r.language == "python" for r in results)
       assert results[0].score >= results[-1].score  # Ordered by score
   ```

2. **Multiple axes**
   ```python
   async def test_search_experiences_across_axes(searcher, vector_store):
       """Test searching same query across different axes."""
       # Setup: Index experiences
       await index_test_experiences(vector_store)

       # Search all axes
       full_results = await searcher.search_experiences(query="bug", axis="full")
       domain_results = await searcher.search_experiences(query="bug", axis="domain")
       strategy_results = await searcher.search_experiences(query="bug", axis="strategy")

       # Verify each axis returns results (may differ)
       assert len(full_results) > 0
       assert len(domain_results) > 0
       assert len(strategy_results) > 0

       # Each result has correct axis
       assert all(r.axis == "full" for r in full_results)
       assert all(r.axis == "domain" for r in domain_results)
       assert all(r.axis == "strategy" for r in strategy_results)
   ```

3. **Empty results**
   ```python
   async def test_search_nonexistent_returns_empty(searcher):
       """Test searching for nonexistent data returns empty list."""
       results = await searcher.search_memories(
           query="nonexistent query that matches nothing",
       )
       assert results == []
   ```

#### Test Fixtures

```python
# conftest.py

@pytest.fixture
async def mock_embedding_service():
    """Mock embedding service with fixed vectors."""
    service = AsyncMock(spec=EmbeddingService)
    service.embed.return_value = np.random.rand(768).astype(np.float32)
    service.dimension = 768
    return service

@pytest.fixture
async def mock_vector_store():
    """Mock vector store with test data."""
    store = AsyncMock(spec=VectorStore)
    store.search.return_value = [
        SearchResult(
            id="test_1",
            score=0.95,
            payload={"category": "test", "content": "Test content"},
        )
    ]
    return store

@pytest.fixture
async def searcher(mock_embedding_service, mock_vector_store):
    """Create searcher with mocked dependencies."""
    return Searcher(mock_embedding_service, mock_vector_store)

@pytest.fixture
async def real_searcher(embedding_service, vector_store):
    """Create searcher with real dependencies for integration tests."""
    return Searcher(embedding_service, vector_store)
```

### Performance Considerations

#### Query Flow Timing

```
Total Query Time = Embedding Time + Vector Search Time + Result Mapping Time

Typical:
- Embedding: 20-50ms (model-dependent)
- Vector search: 30-100ms (size-dependent)
- Result mapping: <1ms (simple dict-to-dataclass)

Total: ~50-150ms (target: <100ms p95)
```

#### Optimization Strategies

1. **Batch queries where possible**
   ```python
   # Instead of:
   results1 = await searcher.search_code(query1)
   results2 = await searcher.search_code(query2)

   # Use concurrent execution:
   results1, results2 = await asyncio.gather(
       searcher.search_code(query1),
       searcher.search_code(query2),
   )
   ```

2. **Limit result counts** - Use appropriate limits (default 10, not 100)

3. **Filter early** - Apply filters in VectorStore, not in Python

4. **No premature optimization** - Start simple, measure, then optimize

#### Memory Efficiency

- **Stream results** - Don't load entire collection into memory
- **Limit enforcement** - VectorStore applies limit, we don't fetch-then-slice
- **No result caching** - Saves memory, keeps implementation simple
- **Dataclass efficiency** - Plain dataclasses are memory-efficient

### Alternatives Considered

#### 1. Generic Search Method

**Alternative**: Single `search(collection, query, filters)` method instead of specialized methods.

**Pros**:
- Simpler implementation
- Fewer methods to maintain
- More flexible

**Cons**:
- No type safety
- Caller must know collection names
- Unclear what filters are valid
- Result type is ambiguous
- Harder to discover API

**Decision**: Rejected. Specialized methods provide better DX and type safety.

#### 2. Result Mapping in VectorStore

**Alternative**: VectorStore returns typed results directly.

**Pros**:
- One less conversion step
- Centralized result handling

**Cons**:
- VectorStore becomes domain-aware
- Violates separation of concerns
- Harder to add new result types
- VectorStore is infrastructure, shouldn't know about memories/code/etc.

**Decision**: Rejected. Keep VectorStore generic, do mapping in Searcher.

#### 3. Enum for Collection Names

**Alternative**: Use `Enum` instead of class constants.

```python
class CollectionName(Enum):
    MEMORIES = "memories"
    CODE = "code"
```

**Pros**:
- More "Pythonic"
- Better IDE autocomplete
- Can iterate over values

**Cons**:
- Must use `.value` everywhere: `collection=CollectionName.CODE.value`
- Awkward in type hints: `collection: str` vs `collection: CollectionName`
- Overkill for simple string constants

**Decision**: Rejected. Simple class constants are cleaner for string usage.

#### 4. Query Builder Pattern

**Alternative**: Fluent API for building queries:

```python
results = await searcher.query("auth") \
    .collection(CollectionName.CODE) \
    .filter(language="python") \
    .limit(10) \
    .execute()
```

**Pros**:
- Flexible query construction
- Discoverable via autocomplete
- Chainable

**Cons**:
- More complex implementation
- Stateful builder object
- Less clear what's required vs optional
- Overkill for simple use cases

**Decision**: Rejected. Simple method calls are sufficient for current needs. Could add in v2 if needed.

## Implementation Plan

### Phase 1: Foundation (Est: 2 hours)

- [ ] Create module structure (`search/` package)
- [ ] Implement `CollectionName` constants
- [ ] Implement custom exceptions
- [ ] Add basic tests for constants and exceptions

### Phase 2: Result Dataclasses (Est: 2 hours)

- [ ] Define all result dataclasses in `results.py`
- [ ] Implement `from_search_result()` classmethods
- [ ] Add datetime parsing and optional field handling
- [ ] Unit tests for all result types

### Phase 3: Filter Translation (Est: 1 hour)

- [ ] Implement `build_filters()` helper in `filters.py`
- [ ] Handle datetime range filters
- [ ] Handle multiple filters (AND logic)
- [ ] Unit tests for filter building

### Phase 4: Searcher Implementation (Est: 3 hours)

- [ ] Implement `Searcher` class with all search methods
- [ ] Embed query text
- [ ] Apply filters
- [ ] Map results
- [ ] Error handling

### Phase 5: Testing (Est: 3 hours)

- [ ] Unit tests with mocks
- [ ] Integration tests with real dependencies
- [ ] Error case tests
- [ ] Performance validation tests

### Phase 6: Documentation & Polish (Est: 1 hour)

- [ ] Docstrings for all public APIs
- [ ] Update `__init__.py` exports
- [ ] Add usage examples in docstrings
- [ ] Type hint verification

**Total Estimate**: ~12 hours

## Open Questions

1. **Date filter operator**: Should we support only `$gte` (since) or also `$lte` (until) and `$between`?
   - **Recommendation**: Start with `$gte` only. Add others if needed in v2 based on actual usage.

2. **Result score interpretation**: Should we normalize scores to 0-1 range or keep raw scores?
   - **Recommendation**: Keep raw scores from VectorStore. Normalization can be added later if needed.

3. **Empty query handling**: Return empty list or raise error?
   - **Recommendation**: Return empty list. Matches VectorStore behavior and is more forgiving.

4. **Filter validation**: Should we validate filter values (e.g., valid language names)?
   - **Recommendation**: No validation in v1. Let VectorStore handle it. Add validation in v2 if needed.

## Success Criteria

Implementation is complete when:

1. ✅ All search methods implemented and tested
2. ✅ Test coverage ≥ 90% for search module
3. ✅ All tests pass in isolation and in suite
4. ✅ Code passes `ruff` linting
5. ✅ Code passes `mypy` strict type checking
6. ✅ Docstrings present for all public APIs
7. ✅ Integration tests with real dependencies pass
8. ✅ Query latency <100ms (p95) in integration tests
9. ✅ All acceptance criteria from spec met

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| VectorStore schema mismatch | Runtime errors | Medium | Comprehensive tests with real data |
| Slow query performance | Poor UX | Low | Measure in tests, optimize if needed |
| Missing result fields | KeyError at runtime | Medium | Validate with integration tests |
| Invalid filter syntax | VectorStore errors | Low | Test all filter combinations |
| Datetime parsing failures | ValueError | Low | Handle both 'Z' and '+00:00' formats |

## Conclusion

This proposal implements a clean, type-safe query interface that:
- **Simplifies caller code** - No embedding or collection name management
- **Provides type safety** - Strongly-typed results and parameters
- **Follows best practices** - Async-first, stateless, well-tested
- **Enables evolution** - Easy to add new search methods or result fields
- **Maintains performance** - Target <100ms query latency

The design prioritizes **developer experience** and **type safety** while keeping the implementation simple and maintainable. The Searcher acts as a clean facade over the VectorStore, encapsulating all collection-specific knowledge and providing a consistent API for the rest of the system.
