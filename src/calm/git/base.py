"""Base classes, dataclasses, and types for git integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


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


class GitAnalyzerError(Exception):
    """Base exception for GitAnalyzer errors."""

    pass


@dataclass
class Commit:
    """Represents a git commit."""

    sha: str
    message: str
    author: str
    author_email: str
    timestamp: datetime  # Always UTC, timezone-aware
    files_changed: list[str]  # Paths relative to repo root
    insertions: int
    deletions: int


@dataclass
class CommitSearchResult:
    """Represents a commit with search relevance score."""

    commit: Commit
    score: float


@dataclass
class BlameEntry:
    """Represents blame information for a range of lines."""

    sha: str
    author: str
    author_email: str
    timestamp: datetime  # Always UTC, timezone-aware
    line_start: int
    line_end: int
    content: str


@dataclass
class ChurnRecord:
    """Represents file change frequency metrics."""

    file_path: str
    change_count: int
    total_insertions: int
    total_deletions: int
    authors: list[str]
    author_emails: list[str]
    last_changed: datetime


@dataclass
class AuthorStats:
    """Represents contribution statistics for an author."""

    author: str
    author_email: str
    commit_count: int
    lines_added: int
    lines_removed: int
    first_commit: datetime
    last_commit: datetime


@dataclass
class BlameSearchResult:
    """Represents a blame search result with authorship info."""

    file_path: str
    line_number: int
    content: str
    sha: str
    author: str
    author_email: str
    timestamp: datetime


@dataclass
class IndexingError:
    """Represents an error that occurred during indexing."""

    sha: str | None
    error_type: str
    message: str


@dataclass
class IndexingStats:
    """Statistics from a commit indexing operation."""

    commits_indexed: int
    commits_skipped: int
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0


class GitReader(ABC):
    """Abstract base class for git repository readers."""

    @abstractmethod
    def __init__(self, repo_path: str) -> None:
        pass

    @abstractmethod
    async def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,
        limit: int = 100,
    ) -> list[Commit]:
        pass

    @abstractmethod
    async def get_blame(self, file_path: str) -> list[BlameEntry]:
        pass

    @abstractmethod
    async def get_file_history(
        self,
        file_path: str,
        limit: int = 100,
    ) -> list[Commit]:
        pass

    @abstractmethod
    def get_repo_root(self) -> str:
        pass

    @abstractmethod
    async def get_head_sha(self) -> str:
        pass
