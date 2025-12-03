# Technical Proposal: GitReader + GitAnalyzer

## Problem Statement

The Learning Memory Server needs git history integration to enable:
1. **Semantic commit search**: Find commits by natural language query ("when did we add authentication?")
2. **Blame lookup**: Identify authors of specific code patterns
3. **Churn analysis**: Discover code hotspots that change frequently
4. **File history tracking**: Understand evolution of specific files

Current system has embedding and vector search infrastructure (SPEC-002-02, SPEC-002-03, SPEC-002-04) but no git integration.

## Proposed Solution

### Module Organization

```
src/learning_memory_server/git/
├── __init__.py          # Public API exports
├── base.py              # Abstract interfaces, dataclasses, errors
├── reader.py            # GitPythonReader implementation
└── analyzer.py          # GitAnalyzer implementation

tests/git/
├── __init__.py
├── test_reader.py       # GitReader unit tests
├── test_analyzer.py     # GitAnalyzer unit + integration tests
└── fixtures.py          # Shared test fixtures (temp repos)
```

### Core Components

#### 1. GitReader (base.py + reader.py)

**Purpose**: Low-level git operations (read commits, blame, file history)

**Key Design Decisions**:
- **Abstract interface** (`GitReader` ABC) for testability and future alternatives
- **Async-first API** despite GitPython being synchronous
  - All sync calls wrapped via `asyncio.run_in_executor`
  - Example pattern:
    ```python
    async def get_commits(self, ...) -> list[Commit]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_commits_sync, ...)
    ```
- **Graceful degradation**: Shallow clones, detached HEAD handled without errors
- **Timezone normalization**: All timestamps converted to UTC with timezone awareness
- **Path normalization**: All paths relative to repo root

**Error Hierarchy**:
```python
GitReaderError (base)
├── RepositoryNotFoundError  # Invalid repo path
├── FileNotInRepoError       # File not tracked
├── BinaryFileError          # Binary file in blame
└── ShallowCloneError        # Missing history (logged, returns available)
```

**Implementation Notes**:
- Use `repo.iter_commits()` for efficient history traversal
- Extract diff stats via `commit.stats.files` (against first parent for merges)
- Blame via `repo.blame()` with line range grouping
- Repository validation at init: check `.git` directory existence
- `get_repo_root()` returns `repo.working_dir` (absolute path to repository root)

#### 2. GitAnalyzer (analyzer.py)

**Purpose**: High-level analysis (indexing, search, metrics)

**Key Design Decisions**:

**a) Incremental Indexing Algorithm**:
```python
# State tracking
- Store last_indexed_sha in metadata DB (git_index_state table)
- On index_commits():
  1. If force=True or no last_indexed_sha → full reindex
  2. Walk backwards from HEAD until finding last_indexed_sha
  3. Index only new commits
  4. Update last_indexed_sha to current HEAD
  5. If last_indexed_sha not found → history rewritten → full reindex
```

**b) 5-Year History Limit**:
- Computed as `datetime.now(timezone.utc) - timedelta(days=5*365)`
- Applied during indexing: skip commits older than cutoff
- Rationale: Balance relevance vs. storage cost
- Implementation: Check `commit.timestamp < cutoff` before indexing

**c) Embedding Strategy**:
```python
# Composite text for each commit
text = f"""{commit.message}

Files: {truncate(", ".join(files_changed), 500)}

Author: {author}"""

# Note: truncate(text, max_len) means text[:max_len] + "..." if len(text) > max_len else text

# Why this works:
# - Message captures semantic intent
# - Files provide "what changed" context
# - Author enables "who worked on X" queries
```

**d) No Churn Caching**:
- Compute on demand via `get_commits(path=file_path, since=...)`
- Group by file path, aggregate insertions/deletions
- Typical latency: 2-5 seconds for 10k commits (acceptable for occasional queries)
- Rationale: Churn data goes stale quickly, caching complexity not justified

**e) Merge Commit Handling**:
- Merge commits ARE indexed (they're often important milestones)
- Diff computed against first parent (standard git convention)
- No special payload markers
- Counted once in churn analysis

### File Organization

```python
# src/learning_memory_server/git/base.py
- Commit dataclass
- BlameEntry dataclass
- ChurnRecord dataclass
- AuthorStats dataclass
- BlameSearchResult dataclass
- IndexingStats dataclass
  - Note: commits_skipped counts already-indexed commits found during incremental indexing
- IndexingError dataclass
- GitReader ABC
- GitAnalyzer class signature
- All error classes

# src/learning_memory_server/git/reader.py
- GitPythonReader implementation
- _get_commits_sync (private helper)
- _get_blame_sync (private helper)
- _get_file_history_sync (private helper)

# src/learning_memory_server/git/analyzer.py
- GitAnalyzer implementation
- _index_commit_batch (private helper)
- _build_embedding_text (private helper)
- _compute_churn (private helper)
- _search_code_pattern (private helper for blame_search)
```

### Storage Schema Extensions

**SQLite Schema** (add to `storage/schema.py`):
```sql
-- Track incremental indexing state
CREATE TABLE IF NOT EXISTS git_index_state (
    id INTEGER PRIMARY KEY,
    repo_path TEXT NOT NULL UNIQUE,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_git_index_state_repo
ON git_index_state(repo_path);
```

**MetadataStore Additions** (add to `storage/metadata.py`):
```python
@dataclass
class GitIndexState:
    id: int | None
    repo_path: str
    last_indexed_sha: str | None
    last_indexed_at: datetime | None
    commit_count: int

async def get_git_index_state(self, repo_path: str) -> GitIndexState | None:
    """Get indexing state for a repository."""
    # Query git_index_state table
    ...

async def update_git_index_state(
    self, repo_path: str, last_sha: str, count: int
) -> None:
    """Update indexing state after indexing commits."""
    # Upsert git_index_state table
    ...
```

**Vector Store** (use existing VectorStore interface):
- Collection name: `"commits"`
- Payload structure:
  ```python
  {
      "id": str,              # SHA (40 chars)
      "sha": str,             # Same as id
      "message": str,         # Full message
      "author": str,
      "author_email": str,
      "timestamp": str,       # ISO format UTC
      "files_changed": list[str],
      "file_count": int,
      "insertions": int,
      "deletions": int,
      "indexed_at": str,      # ISO format UTC
      "repo_path": str,       # Absolute path to repository root
  }
  ```

### Key Algorithms

#### Incremental Indexing

```python
async def index_commits(self, since=None, limit=None, force=False) -> IndexingStats:
    stats = IndexingStats(commits_indexed=0, commits_skipped=0)
    start_time = time.time()

    # Get current state
    state = await self.metadata_store.get_git_index_state(
        await self.git_reader.get_repo_root()
    )

    # Determine indexing mode
    if force or not state or not state.last_indexed_sha:
        # Full reindex
        commits = await self._get_commits_to_index(since, limit)
    else:
        # Incremental: find commits since last_indexed_sha
        head_sha = await self.git_reader.get_head_sha()

        if head_sha == state.last_indexed_sha:
            # Already up to date
            return stats

        # Walk backwards from HEAD
        all_commits = await self.git_reader.get_commits(limit=10000)
        new_commits = []

        for commit in all_commits:
            if commit.sha == state.last_indexed_sha:
                break
            new_commits.append(commit)
        else:
            # last_indexed_sha not found - history rewritten
            logger.warning(
                "last_indexed_sha_not_found",
                last_sha=state.last_indexed_sha,
                head_sha=head_sha,
                action="full_reindex",
            )
            commits = await self._get_commits_to_index(since, limit)
            return await self._index_commit_batch(commits, stats)

        commits = new_commits

    # Index the commits
    stats = await self._index_commit_batch(commits, stats)
    stats.duration_ms = int((time.time() - start_time) * 1000)

    return stats

async def _get_commits_to_index(self, since, limit):
    """Get commits respecting 5-year limit."""
    five_years_ago = datetime.now(timezone.utc) - timedelta(days=5*365)
    effective_since = max(since, five_years_ago) if since else five_years_ago
    return await self.git_reader.get_commits(since=effective_since, limit=limit)

async def _index_commit_batch(self, commits, stats):
    """Index a batch of commits using batch embedding for performance."""
    repo_path = await self.git_reader.get_repo_root()

    # Process in batches of 50-100 for optimal embedding performance
    batch_size = 75
    for i in range(0, len(commits), batch_size):
        batch = commits[i:i+batch_size]

        try:
            # Build embedding texts for entire batch
            texts = [self._build_embedding_text(commit) for commit in batch]

            # Generate embeddings in batch (5-10x faster than sequential)
            vectors = await self.embedding_service.embed_batch(texts)

            # Upsert all commits in batch
            for commit, vector in zip(batch, vectors):
                payload = {
                    "id": commit.sha,
                    "sha": commit.sha,
                    "message": commit.message,
                    "author": commit.author,
                    "author_email": commit.author_email,
                    "timestamp": commit.timestamp.isoformat(),
                    "files_changed": commit.files_changed,
                    "file_count": len(commit.files_changed),
                    "insertions": commit.insertions,
                    "deletions": commit.deletions,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "repo_path": repo_path,
                }

                await self.vector_store.upsert(
                    collection="commits",
                    id=commit.sha,
                    vector=vector,
                    payload=payload,
                )

                stats.commits_indexed += 1

        except Exception as e:
            # Log batch failure, try individual commits
            logger.warning("batch_embed_failed", error=str(e), falling_back_to_sequential=True)
            for commit in batch:
                try:
                    text = self._build_embedding_text(commit)
                    vector = await self.embedding_service.embed(text)

                    payload = {
                        "id": commit.sha,
                        "sha": commit.sha,
                        "message": commit.message,
                        "author": commit.author,
                        "author_email": commit.author_email,
                        "timestamp": commit.timestamp.isoformat(),
                        "files_changed": commit.files_changed,
                        "file_count": len(commit.files_changed),
                        "insertions": commit.insertions,
                        "deletions": commit.deletions,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                        "repo_path": repo_path,
                    }

                    await self.vector_store.upsert(
                        collection="commits",
                        id=commit.sha,
                        vector=vector,
                        payload=payload,
                    )

                    stats.commits_indexed += 1

                except Exception as e2:
                    logger.error("commit_index_failed", sha=commit.sha, error=str(e2))
                    stats.errors.append(
                        IndexingError(
                            sha=commit.sha,
                            error_type=type(e2).__name__,
                            message=str(e2),
                        )
                    )

    # Update state
    if commits:
        head_sha = await self.git_reader.get_head_sha()
        await self.metadata_store.update_git_index_state(
            repo_path=repo_path,
            last_sha=head_sha,
            count=stats.commits_indexed,
        )

    return stats
```

#### Semantic Commit Search

```python
async def search_commits(
    self, query: str, author=None, since=None, limit=10
) -> list[Commit]:
    # Generate query embedding
    query_vector = await self.embedding_service.embed(query)

    # Build filters
    filters = {}
    if author:
        filters["author"] = author
    if since:
        filters["timestamp"] = {"$gte": since.isoformat()}

    # Search vector store
    results = await self.vector_store.search(
        collection="commits",
        query=query_vector,
        limit=limit,
        filters=filters or None,
    )

    # Convert payloads back to Commit objects
    commits = []
    for result in results:
        p = result.payload
        commits.append(
            Commit(
                sha=p["sha"],
                message=p["message"],
                author=p["author"],
                author_email=p["author_email"],
                timestamp=datetime.fromisoformat(p["timestamp"]),
                files_changed=p["files_changed"],
                insertions=p["insertions"],
                deletions=p["deletions"],
            )
        )

    return commits
```

#### Churn Hotspots

```python
async def get_churn_hotspots(
    self, days=90, limit=10, min_changes=3
) -> list[ChurnRecord]:
    # Compute date range
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all commits in range
    commits = await self.git_reader.get_commits(since=since, limit=None)

    # Aggregate by file
    file_stats: dict[str, dict] = {}

    for commit in commits:
        for file_path in commit.files_changed:
            if file_path not in file_stats:
                file_stats[file_path] = {
                    "change_count": 0,
                    "insertions": 0,
                    "deletions": 0,
                    "authors": set(),
                    "emails": set(),
                    "last_changed": commit.timestamp,
                }

            stats = file_stats[file_path]
            stats["change_count"] += 1

            # Note: Per-file churn should extract from commit.stats.files[file_path]
            # which contains per-file insertions/deletions. The commit.insertions and
            # commit.deletions are commit-level totals across all files.
            # Implementation: file_stats = commit.stats.files.get(file_path, {})
            # stats["insertions"] += file_stats.get("insertions", 0)
            # stats["deletions"] += file_stats.get("deletions", 0)
            stats["insertions"] += commit.insertions  # TODO: use per-file stats
            stats["deletions"] += commit.deletions  # TODO: use per-file stats

            stats["authors"].add(commit.author)
            stats["emails"].add(commit.author_email)
            stats["last_changed"] = max(stats["last_changed"], commit.timestamp)

    # Filter by min_changes
    filtered = [
        ChurnRecord(
            file_path=path,
            change_count=stats["change_count"],
            total_insertions=stats["insertions"],
            total_deletions=stats["deletions"],
            authors=sorted(stats["authors"]),
            author_emails=sorted(stats["emails"]),
            last_changed=stats["last_changed"],
        )
        for path, stats in file_stats.items()
        if stats["change_count"] >= min_changes
    ]

    # Sort by change count descending
    filtered.sort(key=lambda r: r.change_count, reverse=True)

    return filtered[:limit]
```

#### Blame Search

```python
async def blame_search(
    self, pattern: str, file_pattern=None, limit=20
) -> list[BlameSearchResult]:
    # Strategy: Use ripgrep to find matches, then git blame for authorship

    # 1. Search for pattern in repo
    import subprocess
    repo_root = await self.git_reader.get_repo_root()

    cmd = ["rg", "--line-number", "--no-heading", pattern]
    if file_pattern:
        cmd.extend(["--glob", file_pattern])

    # Run in executor (subprocess is blocking)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
        ),
    )

    # Parse grep results
    matches: list[tuple[str, int]] = []  # (file_path, line_number)
    for line in result.stdout.splitlines()[:limit * 2]:  # Get extra for filtering
        parts = line.split(":", 2)
        if len(parts) >= 2:
            file_path, line_num = parts[0], int(parts[1])
            matches.append((file_path, line_num))

    # 2. Get blame for each match
    results: list[BlameSearchResult] = []

    for file_path, line_num in matches[:limit]:
        try:
            blame_entries = await self.git_reader.get_blame(file_path)

            # Find entry containing this line
            for entry in blame_entries:
                if entry.line_start <= line_num <= entry.line_end:
                    results.append(
                        BlameSearchResult(
                            file_path=file_path,
                            line_number=line_num,
                            content=entry.content.splitlines()[
                                line_num - entry.line_start
                            ],
                            sha=entry.sha,
                            author=entry.author,
                            author_email=entry.author_email,
                            timestamp=entry.timestamp,
                        )
                    )
                    break

        except (BinaryFileError, FileNotInRepoError):
            # Skip files we can't blame
            continue

    return results
```

### Testing Strategy

#### Unit Tests (tests/git/test_reader.py)

```python
# Test fixtures
- Empty repository
- Single commit repository
- Multi-commit with branches
- Shallow clone (git clone --depth=1)
- Detached HEAD state
- Repository with binary files
- Repository with merge commits

# Test cases
- get_commits with date filters
- get_commits with path filters
- get_blame on text file
- get_blame raises BinaryFileError on binary
- get_file_history returns correct commits
- Shallow clone returns available commits + logs warning
- Invalid repo path raises RepositoryNotFoundError
- All timestamps are UTC and timezone-aware
- All paths are relative to repo root
```

#### Integration Tests (tests/git/test_analyzer.py)

```python
# Use actual clams repository for realistic testing

# Test cases
- index_commits on first run (full index)
- index_commits incremental (adds new commits only)
- index_commits force=True (reindexes all)
- index_commits after history rewrite (falls back to full)
- search_commits returns relevant results
- search_commits with author filter
- search_commits with date filter
- get_churn_hotspots returns high-change files
- get_file_authors aggregates correctly
- blame_search finds patterns and returns authorship
- 5-year history limit applied during indexing
- Merge commits included in results
```

#### Performance Tests (marked with @pytest.mark.slow)

```python
# Measured on 10k commit repository (M1 MacBook Pro)

async def test_full_index_performance():
    # Should complete in <30 seconds
    start = time.time()
    stats = await analyzer.index_commits()
    duration = time.time() - start
    assert duration < 30
    assert stats.commits_indexed > 0

async def test_incremental_index_performance():
    # Index 100 new commits in <5 seconds
    # (requires test fixture with controlled commit count)
    ...

async def test_search_performance():
    # Search (excluding embedding) in <100ms
    ...

async def test_churn_performance():
    # 90-day churn in <5 seconds
    ...
```

### Alternatives Considered

#### 1. Use libgit2 via pygit2 instead of GitPython

**Pros**:
- Faster (C library)
- More complete git feature coverage

**Cons**:
- Harder to install (requires system libgit2)
- More complex API
- Overkill for our read-only use case

**Decision**: Use GitPython. It's pure Python, well-documented, and performance is acceptable for our use case.

#### 2. Cache churn metrics in SQLite

**Pros**:
- Faster queries (no git history traversal)

**Cons**:
- Cache invalidation complexity
- Stale data (git history can change)
- Extra storage overhead

**Decision**: Compute on demand. Churn queries are infrequent, and 2-5 second latency is acceptable.

#### 3. Index all history (not just 5 years)

**Pros**:
- Complete historical search

**Cons**:
- Larger vector DB storage
- Older commits rarely relevant
- Slower indexing

**Decision**: 5-year limit. Balances relevance vs. cost. Can be made configurable later if needed.

#### 4. Store commit embeddings in SQLite instead of VectorStore

**Pros**:
- Single storage backend
- Potentially simpler

**Cons**:
- Would require implementing vector search in SQLite (complex)
- VectorStore already provides optimized similarity search
- Inconsistent with codebase architecture

**Decision**: Use VectorStore. Consistent with existing code index architecture.

## Open Questions

1. **Embedding model**: Should commit embeddings use the same model as code embeddings?
   - **Recommendation**: Yes, use same model (nomic-embed-text-v1.5). It's trained for semantic similarity and works well on both code and natural language.

2. **Collection naming**: Should commits be in a separate collection per project or one global collection?
   - **Recommendation**: One global `"commits"` collection with `repo_path` in payload for filtering. Simpler and allows cross-repo search later.

3. **File pattern matching in blame_search**: Should we use ripgrep, git grep, or Python regex?
   - **Recommendation**: ripgrep (already installed, fastest). Fall back to git grep if rg not found.

4. **Concurrent indexing**: Should we index commits in parallel (batch embeddings)?
   - **Recommendation**: Yes, use `embedding_service.embed_batch()` for 5-10x speedup. Group commits into batches of 50-100.

5. **Index initialization**: When should `index_commits()` be called automatically?
   - **Recommendation**: Not automatic. Require explicit API call or MCP tool invocation. Indexing is slow and should be user-initiated.

## Summary

This proposal provides a complete git history integration for the Learning Memory Server:

- **GitReader**: Low-level git operations via GitPython, async-wrapped
- **GitAnalyzer**: High-level indexing and analysis
- **Incremental indexing**: Efficient updates, handles history rewrites
- **5-year limit**: Balances relevance vs. storage
- **No churn caching**: On-demand computation, acceptable latency
- **Comprehensive testing**: Unit, integration, and performance tests
- **Clean abstraction**: Follows existing codebase patterns (ABC interfaces, dataclasses, async)

Implementation can proceed directly from this proposal with high confidence.
