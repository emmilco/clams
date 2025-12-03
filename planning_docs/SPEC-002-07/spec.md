# SPEC-002-07: GitReader + GitAnalyzer

## Overview

Implement git history analysis for the Learning Memory Server. This enables semantic commit search, blame lookup, churn analysis, and file history tracking.

## Dependencies

- SPEC-002-02: EmbeddingService (completed)
- SPEC-002-03: VectorStore (completed)
- SPEC-002-04: SQLite metadata store (completed)

## Components

### 1. GitReader

**Purpose**: Read git repository data (commits, blame, file history).

**Interface**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class Commit:
    sha: str
    message: str
    author: str
    author_email: str
    timestamp: datetime  # Always UTC, timezone-aware
    files_changed: list[str]  # Paths relative to repo root
    insertions: int
    deletions: int

@dataclass
class BlameEntry:
    sha: str
    author: str
    author_email: str
    timestamp: datetime  # Always UTC, timezone-aware
    line_start: int
    line_end: int
    content: str

class GitReader(ABC):
    def __init__(self, repo_path: str):
        """
        Initialize reader with repository path.

        Args:
            repo_path: Absolute path to repository root (containing .git/)

        Raises:
            GitReaderError: If path is not a valid git repository
        """
        ...

    @abstractmethod
    async def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,  # Relative to repo root
        limit: int = 100,
    ) -> list[Commit]:
        """Get commits, optionally filtered by date range and path."""
        pass

    @abstractmethod
    async def get_blame(self, file_path: str) -> list[BlameEntry]:
        """
        Get blame information for a file.

        Args:
            file_path: Path relative to repo root

        Raises:
            GitReaderError: If file doesn't exist or is binary
        """
        pass

    @abstractmethod
    async def get_file_history(
        self,
        file_path: str,  # Relative to repo root
        limit: int = 100,
    ) -> list[Commit]:
        """Get commit history for a specific file."""
        pass

    @abstractmethod
    async def get_repo_root(self) -> str:
        """Get the absolute repository root path."""
        pass

    @abstractmethod
    async def get_head_sha(self) -> str:
        """Get the current HEAD commit SHA."""
        pass
```

**Implementation**: `GitPythonReader`
- Uses `GitPython` library
- All GitPython calls wrapped with `run_in_executor` (sync library)
- Handles detached HEAD, shallow clones gracefully (returns available history)
- All paths in results are relative to repo root

### 2. GitAnalyzer

**Purpose**: Analyze and index git history for semantic search and metrics.

**Interface**:
```python
from dataclasses import dataclass, field

@dataclass
class ChurnRecord:
    file_path: str
    change_count: int
    total_insertions: int
    total_deletions: int
    authors: list[str]  # Unique author names
    author_emails: list[str]  # Corresponding emails
    last_changed: datetime

@dataclass
class AuthorStats:
    author: str
    author_email: str
    commit_count: int
    lines_added: int
    lines_removed: int
    first_commit: datetime
    last_commit: datetime

@dataclass
class BlameSearchResult:
    file_path: str
    line_number: int
    content: str
    sha: str
    author: str
    author_email: str
    timestamp: datetime

@dataclass
class IndexingError:
    sha: str | None
    error_type: str
    message: str

@dataclass
class IndexingStats:
    commits_indexed: int
    commits_skipped: int  # Already indexed
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0

class GitAnalyzer:
    def __init__(
        self,
        git_reader: GitReader,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
    ):
        ...

    async def index_commits(
        self,
        since: datetime | None = None,
        limit: int | None = None,
        force: bool = False,  # If True, reindex all commits
    ) -> IndexingStats:
        """
        Index commits for semantic search.

        History limit: Only indexes commits from the last 5 years.
        Older commits are ignored (diminishing relevance, storage cost).

        Incremental indexing algorithm:
        1. Get last_indexed_sha from git_index_state table
        2. If force=True or no last_indexed_sha, index all commits (up to 5 years)
        3. Otherwise, traverse from HEAD backwards until we find last_indexed_sha
        4. Index only commits between HEAD and last_indexed_sha
        5. Update last_indexed_sha to current HEAD

        Note: If last_indexed_sha is not in current history (force push, rebase),
        falls back to full reindex.
        """
        pass

    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[Commit]:
        """
        Semantic search over commit messages.

        Embeds query, searches VectorStore, returns matched commits.
        Search latency excludes embedding time.
        """
        pass

    async def get_churn_hotspots(
        self,
        days: int = 90,
        limit: int = 10,
        min_changes: int = 3,
    ) -> list[ChurnRecord]:
        """
        Find files with highest change frequency.

        Computes on demand from git history (no caching).
        Typical latency: 2-5 seconds for repos with 10k commits.
        """
        pass

    async def get_file_authors(self, file_path: str) -> list[AuthorStats]:
        """Get author statistics for a file (not cached, computed on demand)."""
        pass

    async def get_change_frequency(
        self,
        file_or_function: str,
        since: datetime | None = None,
    ) -> ChurnRecord | None:
        """Get change frequency for a specific file or function name."""
        pass

    async def blame_search(
        self,
        pattern: str,
        file_pattern: str | None = None,
        limit: int = 20,
    ) -> list[BlameSearchResult]:
        """
        Search for code pattern and return blame info for matches.

        Uses grep to find matches, then git blame to get authorship.
        """
        pass
```

## Incremental Indexing Algorithm

```python
async def index_commits(self, since=None, limit=None, force=False) -> IndexingStats:
    state = await self.metadata_store.get_git_index_state(self.repo_path)

    if force or state is None or state.last_indexed_sha is None:
        # Full index
        commits = await self.git_reader.get_commits(since=since, limit=limit)
        return await self._index_commit_batch(commits, update_state=True)

    # Incremental: find commits since last indexed
    head_sha = await self.git_reader.get_head_sha()

    if head_sha == state.last_indexed_sha:
        return IndexingStats(commits_indexed=0, commits_skipped=0)

    # Walk backwards from HEAD until we find last_indexed_sha
    new_commits = []
    for commit in await self.git_reader.get_commits(limit=10000):
        if commit.sha == state.last_indexed_sha:
            break
        new_commits.append(commit)
    else:
        # last_indexed_sha not found - history was rewritten
        # Fall back to full reindex
        logger.warning("Last indexed SHA not in history, doing full reindex")
        commits = await self.git_reader.get_commits(since=since, limit=limit)
        return await self._index_commit_batch(commits, update_state=True)

    return await self._index_commit_batch(new_commits, update_state=True)
```

## Error Handling

```python
class GitReaderError(Exception):
    """Base exception for GitReader errors."""
    pass

class RepositoryNotFoundError(GitReaderError):
    """Repository path is not a valid git repository."""
    pass

class FileNotInRepoError(GitReaderError):
    """Requested file is not tracked in the repository."""
    pass

class BinaryFileError(GitReaderError):
    """Cannot perform operation on binary file (e.g., blame)."""
    pass

class ShallowCloneError(GitReaderError):
    """Operation requires history not available in shallow clone."""
    pass
```

**Error handling behavior**:
- `RepositoryNotFoundError`: Raised on GitReader init, caller must handle
- `FileNotInRepoError`: Raised from get_blame/get_file_history, caller handles
- `BinaryFileError`: Raised from get_blame, caller handles
- `ShallowCloneError`: Logged as warning, returns available history
- Detached HEAD: Works normally, just no branch name
- Individual commit parse errors: Logged, skipped, accumulated in IndexingStats.errors

## Merge Commit Handling

- Merge commits ARE indexed (included in search results)
- `files_changed`: Computed as diff against first parent only (standard convention)
- `insertions`/`deletions`: Computed against first parent
- No special payload markers; merge commits are treated like regular commits
- Churn analysis counts merge commits once (not split across parents)

## Async Pattern

GitPython is synchronous. All calls are wrapped:

```python
async def get_commits(self, ...) -> list[Commit]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._get_commits_sync, ...)
```

## Storage Schema

### Vector Store Collection: `commits`

**Payload fields**:
```python
{
    "id": str,              # Commit SHA (full 40 chars)
    "sha": str,             # Same as id (for clarity in search results)
    "message": str,         # Full commit message
    "author": str,
    "author_email": str,
    "timestamp": str,       # ISO timestamp (UTC)
    "files_changed": list[str],  # Relative paths
    "file_count": int,
    "insertions": int,
    "deletions": int,
    "indexed_at": str,      # ISO timestamp (UTC)
}
```

### SQLite Metadata Extensions

Add to existing MetadataStore:

```sql
-- Track indexed commit range
CREATE TABLE IF NOT EXISTS git_index_state (
    id INTEGER PRIMARY KEY,
    repo_path TEXT NOT NULL UNIQUE,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);
```

**MetadataStore additions**:
```python
async def get_git_index_state(self, repo_path: str) -> GitIndexState | None: ...
async def update_git_index_state(self, repo_path: str, last_sha: str, count: int) -> None: ...
```

## Embedding Strategy

For each commit, create embedding from:
```
{commit_message}

Files: {files_changed joined by ", " - truncated to 500 chars if longer}

Author: {author}
```

This captures:
- Semantic intent from message
- File context for "what files were changed" queries
- Author for "who worked on X" queries

## Acceptance Criteria

### Functional
1. Can list commits with date/path filters
2. Can get blame for any tracked text file
3. Can get file history (commits touching a file)
4. Index stores commits in VectorStore with correct payloads
5. Semantic search returns relevant commits
6. Churn hotspots correctly identifies high-change files
7. Author stats accurately reflect contribution
8. Incremental indexing only indexes new commits
9. Force reindex works when history is rewritten

### Edge Cases
1. Empty repository: Returns empty lists, no errors
2. Shallow clones: Returns available history, logs warning
3. Detached HEAD: Works normally
4. Binary files in blame: Raises BinaryFileError
5. Deleted files in history: File history still works
6. Merge commits: Included, files computed against first parent
7. Non-ASCII in messages/names: Handled correctly (UTF-8)
8. Very long commit messages: Truncated in embedding, full in payload

### Performance
Measured on repository with 10k commits, M1 MacBook Pro:
1. Full index (10k commits): <30 seconds
2. Incremental index (100 new commits): <5 seconds
3. Semantic search (excluding embedding): <100ms
4. Semantic search (including embedding): <200ms
5. Churn computation (90 days): <5 seconds
6. Blame (<5000 lines): <1 second
7. Blame (>5000 lines): <3 seconds

## Testing Strategy

### Unit Tests
- GitReader extracts correct commit data
- GitReader handles edge cases (empty repo, shallow clone, detached HEAD)
- GitReader path handling (relative paths, special characters)
- GitAnalyzer incremental indexing logic
- GitAnalyzer 5-year history limit applied correctly
- Error types raised correctly

### Integration Tests
- Index this repository's history
- Verify search returns relevant commits
- Verify churn matches `git log --stat` output
- Verify incremental index after adding commits

### Test Fixtures
- Use the actual clams repository for realistic testing
- Create test scenarios with `git init` in temp directories:
  - Empty repo
  - Single commit
  - Merge commits
  - Shallow clone (via `git clone --depth=1`)
  - Detached HEAD state

## Out of Scope

- Git operations (commit, push, pull, etc.)
- Branch comparison
- Merge conflict analysis
- Submodule handling
- Git LFS content
- Remote repository fetching
- Authentication/credentials handling
- Working directory state (staged/unstaged changes)

## Notes

- Use `GitPython` library (well-maintained, pure Python)
- All methods are async; GitPython calls use `run_in_executor`
- All timestamps are UTC and timezone-aware
- All file paths in results are relative to repo root
- Logging via `structlog` following existing codebase patterns
