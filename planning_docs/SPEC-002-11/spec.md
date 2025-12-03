# SPEC-002-11: MCP Tools for Memory, Code, Git

## Overview

Implement MCP tool interfaces that expose the Learning Memory Server's functionality through the Model Context Protocol. These tools wire the underlying services (memory, code indexing, git analysis, searcher) to Claude Code agents via MCP.

## Dependencies

### Completed
- SPEC-002-02: EmbeddingService
- SPEC-002-03: VectorStore
- SPEC-002-04: SQLite metadata store
- SPEC-002-05: MCP server skeleton

### In Progress (will be completed before this task)
- SPEC-002-06: CodeParser + CodeIndexer
- SPEC-002-07: GitReader + GitAnalyzer
- SPEC-002-09: Searcher

## Components

This spec defines three tool modules:

1. **Memory Tools** (`server/tools/memory.py`) - Store, retrieve, list, delete memories
2. **Code Tools** (`server/tools/code.py`) - Index codebases, search code semantically
3. **Git Tools** (`server/tools/git.py`) - Search commits, analyze churn, blame

Each module registers its tools with the MCP server and wires to underlying services.

---

## Memory Tools

### Purpose

Enable Claude Code agents to store and retrieve verified memories with semantic search.

### Tool Definitions

#### store_memory

**Purpose**: Store a new memory with semantic embedding.

**Input Schema**:
```python
{
    "content": str,           # Required: Memory content (max 10,000 chars)
    "category": str,          # Required: One of: preference, fact, event, workflow, context
    "importance": float,      # Optional: 0.0-1.0, default 0.5
    "tags": list[str],        # Optional: Tags for categorization
}
```

**Output Schema**:
```python
{
    "id": str,                # Generated memory ID (UUID)
    "content": str,           # Stored content
    "category": str,
    "importance": float,
    "tags": list[str],
    "created_at": str,        # ISO timestamp (UTC)
}
```

**Behavior**:
1. Validate inputs (content length, category enum, importance range)
2. Generate embedding via EmbeddingService
3. Store in VectorStore collection `memories` with payload
4. Store metadata in SQLite
5. Return memory record

**Error Handling**:
- Content too long (>10k chars): Truncate with warning
- Invalid category: Raise ValueError with valid options
- Importance out of range: Clamp to [0.0, 1.0] with warning
- Embedding failure: Raise MCPError with details
- Storage failure: Raise MCPError with details

#### retrieve_memories

**Purpose**: Search memories semantically.

**Input Schema**:
```python
{
    "query": str,             # Required: Search query
    "limit": int,             # Optional: Max results, default 10, max 100
    "category": str,          # Optional: Filter by category
    "min_importance": float,  # Optional: Minimum importance, default 0.0
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "content": str,
            "category": str,
            "importance": float,
            "tags": list[str],
            "score": float,       # Similarity score (0.0-1.0)
            "created_at": str,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs (limit range, category if provided)
2. Generate query embedding via EmbeddingService
3. Search VectorStore with filters
4. Return results sorted by score (descending)

**Error Handling**:
- Empty query: Return empty results (not an error)
- Invalid category: Raise ValueError with valid options
- Limit out of range: Clamp to [1, 100] with warning
- Embedding failure: Raise MCPError
- Search failure: Raise MCPError

#### list_memories

**Purpose**: List memories with filters (non-semantic).

**Input Schema**:
```python
{
    "category": str,          # Optional: Filter by category
    "tags": list[str],        # Optional: Filter by tags (ANY match)
    "limit": int,             # Optional: Max results, default 50, max 200
    "offset": int,            # Optional: Pagination offset, default 0
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "content": str,
            "category": str,
            "importance": float,
            "tags": list[str],
            "created_at": str,
        }
    ],
    "count": int,
    "total": int,             # Total matching records (for pagination)
}
```

**Behavior**:
1. Query VectorStore with filters (no embedding needed)
2. Apply pagination
3. Return results sorted by created_at (newest first)

**Error Handling**:
- Invalid category: Raise ValueError
- Offset/limit negative: Clamp to 0
- Storage failure: Raise MCPError

#### delete_memory

**Purpose**: Delete a memory by ID.

**Input Schema**:
```python
{
    "id": str,                # Required: Memory ID
}
```

**Output Schema**:
```python
{
    "deleted": bool,
}
```

**Behavior**:
1. Delete from VectorStore
2. Delete from SQLite metadata
3. Return success status

**Error Handling**:
- ID not found: Return `{"deleted": false}` (not an error)
- Storage failure: Raise MCPError

---

## Code Tools

### Purpose

Enable semantic code search and codebase indexing.

### Tool Definitions

#### index_codebase

**Purpose**: Index a directory of source code for semantic search.

**Input Schema**:
```python
{
    "directory": str,         # Required: Absolute path to directory
    "project": str,           # Required: Project identifier
    "recursive": bool,        # Optional: Recurse subdirectories, default True
}
```

**Output Schema**:
```python
{
    "project": str,
    "files_indexed": int,
    "units_indexed": int,
    "files_skipped": int,
    "errors": [
        {
            "file_path": str,
            "error_type": str,    # parse_error, encoding_error, io_error
            "message": str,
        }
    ],
    "duration_ms": int,
}
```

**Behavior**:
1. Validate directory exists and is readable
2. Delegate to CodeIndexer.index_directory()
3. Return IndexingStats

**Error Handling**:
- Directory not found: Raise ValueError
- Permission denied: Raise PermissionError
- Individual file errors: Accumulated in errors list, not thrown
- Indexing failure: Raise MCPError

#### search_code

**Purpose**: Search indexed code semantically.

**Input Schema**:
```python
{
    "query": str,             # Required: Search query
    "project": str,           # Optional: Filter by project
    "language": str,          # Optional: Filter by language (python, typescript, etc.)
    "limit": int,             # Optional: Max results, default 10, max 50
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "project": str,
            "file_path": str,
            "name": str,
            "qualified_name": str,
            "unit_type": str,     # function, class, method
            "signature": str,
            "language": str,
            "start_line": int,
            "end_line": int,
            "line_count": int,
            "complexity": int | None,
            "has_docstring": bool,
            "score": float,       # Similarity score (0.0-1.0)
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs
2. Generate query embedding
3. Search VectorStore collection `code_units` with filters
4. Return results sorted by score

**Error Handling**:
- Empty query: Return empty results
- Invalid language: Raise ValueError with supported languages
- Limit out of range: Clamp to [1, 50]
- Embedding failure: Raise MCPError
- Search failure: Raise MCPError

#### find_similar_code

**Purpose**: Find code similar to a given snippet.

**Input Schema**:
```python
{
    "snippet": str,           # Required: Code snippet (max 5,000 chars)
    "project": str,           # Optional: Filter by project
    "limit": int,             # Optional: Max results, default 10, max 50
}
```

**Output Schema**:
```python
{
    "results": [
        # Same structure as search_code results
    ],
    "count": int,
}
```

**Behavior**:
1. Validate snippet length
2. Generate embedding from snippet
3. Search VectorStore collection `code_units`
4. Return results sorted by similarity

**Error Handling**:
- Empty snippet: Return empty results
- Snippet too long (>5k chars): Truncate with warning
- Embedding failure: Raise MCPError
- Search failure: Raise MCPError

---

## Git Tools

### Purpose

Enable semantic commit search and churn analysis.

### Tool Definitions

#### search_commits

**Purpose**: Search git commits semantically.

**Input Schema**:
```python
{
    "query": str,             # Required: Search query
    "author": str,            # Optional: Filter by author name
    "since": str,             # Optional: ISO date string (UTC)
    "limit": int,             # Optional: Max results, default 10, max 50
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "sha": str,
            "message": str,
            "author": str,
            "author_email": str,
            "timestamp": str,     # ISO timestamp (UTC)
            "files_changed": list[str],
            "file_count": int,
            "insertions": int,
            "deletions": int,
            "score": float,       # Similarity score (0.0-1.0)
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs (date format, limit)
2. Generate query embedding
3. Search VectorStore collection `commits` with filters
4. Return results sorted by score

**Error Handling**:
- Empty query: Return empty results
- Invalid date format: Raise ValueError
- Invalid author filter: No error, just no matches
- Embedding failure: Raise MCPError
- Search failure: Raise MCPError

#### get_file_history

**Purpose**: Get commit history for a specific file.

**Input Schema**:
```python
{
    "path": str,              # Required: File path relative to repo root
    "limit": int,             # Optional: Max commits, default 100, max 500
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "sha": str,
            "message": str,
            "author": str,
            "author_email": str,
            "timestamp": str,
            "insertions": int,
            "deletions": int,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate path
2. Delegate to GitReader.get_file_history()
3. Return commits sorted by timestamp (newest first)

**Error Handling**:
- File not in repo: Raise FileNotFoundError
- Limit out of range: Clamp to [1, 500]
- Git operation failure: Raise MCPError

#### get_churn_hotspots

**Purpose**: Find files with highest change frequency.

**Input Schema**:
```python
{
    "days": int,              # Optional: Analysis window, default 90, max 365
    "limit": int,             # Optional: Max results, default 10, max 50
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "file_path": str,
            "change_count": int,
            "total_insertions": int,
            "total_deletions": int,
            "authors": list[str],
            "author_emails": list[str],
            "last_changed": str,  # ISO timestamp (UTC)
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate days and limit
2. Delegate to GitAnalyzer.get_churn_hotspots()
3. Return results sorted by change_count (descending)

**Error Handling**:
- Days/limit out of range: Clamp to valid ranges
- No git repository: Raise RepositoryNotFoundError
- Git operation failure: Raise MCPError

#### get_code_authors

**Purpose**: Get author statistics for a file.

**Input Schema**:
```python
{
    "path": str,              # Required: File path relative to repo root
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "author": str,
            "author_email": str,
            "commit_count": int,
            "lines_added": int,
            "lines_removed": int,
            "first_commit": str,  # ISO timestamp (UTC)
            "last_commit": str,   # ISO timestamp (UTC)
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate path
2. Delegate to GitAnalyzer.get_file_authors()
3. Return results sorted by commit_count (descending)

**Error Handling**:
- File not in repo: Raise FileNotFoundError
- Binary file: Raise BinaryFileError
- Git operation failure: Raise MCPError

---

## Tool Registration

### Registration Pattern

Each tool module follows this pattern:

```python
def register_memory_tools(server: Server, settings: ServerSettings) -> None:
    """Register memory tools with MCP server."""

    # Initialize services (shared instances via settings)
    embedding_service = get_embedding_service(settings)
    vector_store = get_vector_store(settings)
    metadata_store = get_metadata_store(settings)

    @server.call_tool()
    async def store_memory(
        content: str,
        category: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict:
        """Store a new memory."""
        # Implementation
        ...

    # Register other memory tools
    ...
```

### Service Initialization

Services are initialized once per server instance and shared across tool calls:

```python
# In server/tools/__init__.py

def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server."""

    # Initialize shared services
    embedding_service = NomicEmbedding(settings.embedding_model)
    vector_store = QdrantVectorStore(settings.qdrant_url)
    metadata_store = MetadataStore(settings.db_path)

    # Store in server context for tool access
    server.request_context.embedding_service = embedding_service
    server.request_context.vector_store = vector_store
    server.request_context.metadata_store = metadata_store

    # Register tool modules
    register_memory_tools(server, settings)
    register_code_tools(server, settings)
    register_git_tools(server, settings)
```

---

## Error Handling

### Error Types

All MCP tools use consistent error handling:

```python
class MCPError(Exception):
    """Base error for MCP tool failures."""
    pass

class ValidationError(MCPError):
    """Input validation failed."""
    pass

class StorageError(MCPError):
    """Storage operation failed."""
    pass

class EmbeddingError(MCPError):
    """Embedding generation failed."""
    pass

class GitError(MCPError):
    """Git operation failed."""
    pass
```

### Error Response Format

All errors are caught and returned in MCP error format:

```python
try:
    # Tool implementation
    ...
except ValidationError as e:
    return {"error": {"type": "validation_error", "message": str(e)}}
except StorageError as e:
    return {"error": {"type": "storage_error", "message": str(e)}}
except Exception as e:
    logger.error("tool.unexpected_error", tool_name="...", error=str(e))
    return {"error": {"type": "internal_error", "message": "Internal server error"}}
```

---

## Performance Requirements

### Latency Targets

Target latencies (P95) for typical operations:

| Operation | Target | Notes |
|-----------|--------|-------|
| store_memory | <500ms | Includes embedding generation |
| retrieve_memories | <300ms | Includes embedding generation |
| list_memories | <100ms | No embedding needed |
| delete_memory | <100ms | Simple delete operation |
| index_codebase | <5s/100 files | Batch embedding optimization |
| search_code | <300ms | Includes embedding generation |
| find_similar_code | <300ms | Includes embedding generation |
| search_commits | <300ms | Includes embedding generation |
| get_file_history | <500ms | Git operation latency |
| get_churn_hotspots | <3s | Computation-heavy |
| get_code_authors | <1s | Git operation latency |

### Optimization Strategies

1. **Batch Embedding**: Code indexing batches units (100 at a time)
2. **Connection Pooling**: VectorStore connections reused across calls
3. **Async I/O**: All operations non-blocking
4. **Lazy Loading**: Services initialized only when needed
5. **Result Limiting**: Enforce max result counts to prevent large payloads

---

## Testing Strategy

### Unit Tests

Each tool tested independently with mocked services:

```python
@pytest.mark.asyncio
async def test_store_memory_success(mock_embedding_service, mock_vector_store):
    """Test successful memory storage."""
    result = await store_memory(
        content="Test memory",
        category="fact",
        importance=0.8,
        tags=["test"],
    )

    assert result["id"] is not None
    assert result["content"] == "Test memory"
    assert result["category"] == "fact"
    assert result["importance"] == 0.8

    # Verify service calls
    mock_embedding_service.embed.assert_called_once()
    mock_vector_store.upsert.assert_called_once()

@pytest.mark.asyncio
async def test_store_memory_invalid_category(mock_services):
    """Test validation error for invalid category."""
    with pytest.raises(ValidationError, match="Invalid category"):
        await store_memory(content="Test", category="invalid")
```

### Integration Tests

Test tools with real services (in-memory implementations):

```python
@pytest.mark.asyncio
async def test_memory_workflow_end_to_end():
    """Test full memory workflow: store, retrieve, delete."""
    # Setup
    embedding_service = MockEmbedding()
    vector_store = InMemoryVectorStore()

    # Store
    result1 = await store_memory("Python is dynamically typed", "fact")
    result2 = await store_memory("JavaScript is also dynamic", "fact")

    # Retrieve
    results = await retrieve_memories("dynamic typing", limit=5)
    assert len(results["results"]) == 2
    assert results["results"][0]["score"] > 0.5

    # Delete
    await delete_memory(result1["id"])

    # Verify deletion
    results = await retrieve_memories("Python", limit=5)
    assert len(results["results"]) == 0
```

### Test Coverage Requirements

- Unit tests: ≥90% coverage for all tool modules
- Integration tests: All happy paths and major error cases
- Error handling: Test all error types for each tool
- Input validation: Test boundary conditions for all parameters

---

## Acceptance Criteria

### Functional

1. ✅ All memory tools (store, retrieve, list, delete) work correctly
2. ✅ All code tools (index, search, find_similar) work correctly
3. ✅ All git tools (search, history, churn, authors) work correctly
4. ✅ Tools registered with MCP server via @server.call_tool()
5. ✅ Service initialization occurs once per server instance
6. ✅ Input validation enforced for all parameters
7. ✅ Error handling returns MCP-compliant error format
8. ✅ All tools documented with docstrings
9. ✅ Results sorted appropriately (by score, timestamp, count)
10. ✅ Pagination works correctly for list_memories

### Quality

1. ✅ All tools handle edge cases gracefully (empty results, not found, etc.)
2. ✅ Large payloads prevented via result limiting
3. ✅ Long strings truncated with warnings logged
4. ✅ Invalid inputs raise appropriate errors with helpful messages
5. ✅ Async operations never block event loop
6. ✅ Structured logging for all operations (success and failure)

### Performance

1. ✅ Latency targets met for typical operations
2. ✅ Batch embedding optimization used in index_codebase
3. ✅ No memory leaks with repeated tool calls
4. ✅ Connection pooling works correctly

### Testing

1. ✅ Unit test coverage ≥90%
2. ✅ All error cases tested
3. ✅ Integration tests pass with real services
4. ✅ Type checking passes (mypy --strict)
5. ✅ Linting passes (ruff)

---

## Out of Scope

- GHAP tools (SPEC-002-XX)
- Learning tools (clustering, values) (SPEC-002-XX)
- Verification tools (SPEC-002-XX)
- Authentication/authorization
- Rate limiting
- Tool usage analytics
- Multi-tenancy

---

## Notes

- All tools use async/await consistently
- All timestamps are ISO 8601 format (UTC)
- All file paths are absolute (relative to repo root for git tools)
- Logging via `structlog` following existing codebase patterns
- MCP SDK version: `mcp>=0.9.0`
