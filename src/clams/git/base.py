"""Base classes, dataclasses, and types for git integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

# Error classes


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


# Data classes


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
    authors: list[str]  # Unique author names
    author_emails: list[str]  # Corresponding emails
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
    commits_skipped: int  # Already indexed
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0


# Abstract interfaces


class GitReader(ABC):
    """Abstract base class for git repository readers."""

    @abstractmethod
    def __init__(self, repo_path: str) -> None:
        """Initialize reader with repository path.

        Args:
            repo_path: Absolute path to repository root (containing .git/)

        Raises:
            RepositoryNotFoundError: If path is not a valid git repository
        """
        pass

    @abstractmethod
    async def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,  # Relative to repo root
        limit: int = 100,
    ) -> list[Commit]:
        """Get commits, optionally filtered by date range and path.

        Args:
            since: Optional start date (UTC, timezone-aware)
            until: Optional end date (UTC, timezone-aware)
            path: Optional file/directory path relative to repo root
            limit: Maximum number of commits to return

        Returns:
            List of commits ordered by timestamp descending (newest first)
        """
        pass

    @abstractmethod
    async def get_blame(self, file_path: str) -> list[BlameEntry]:
        """Get blame information for a file.

        Args:
            file_path: Path relative to repo root

        Returns:
            List of blame entries covering all lines in the file

        Raises:
            FileNotInRepoError: If file doesn't exist or is not tracked
            BinaryFileError: If file is binary
        """
        pass

    @abstractmethod
    async def get_file_history(
        self,
        file_path: str,  # Relative to repo root
        limit: int = 100,
    ) -> list[Commit]:
        """Get commit history for a specific file.

        Args:
            file_path: Path relative to repo root
            limit: Maximum number of commits to return

        Returns:
            List of commits that modified this file, ordered by timestamp descending
        """
        pass

    @abstractmethod
    def get_repo_root(self) -> str:
        """Get the absolute repository root path.

        Returns:
            Absolute path to repository root
        """
        pass

    @abstractmethod
    async def get_head_sha(self) -> str:
        """Get the current HEAD commit SHA.

        Returns:
            40-character commit SHA

        Raises:
            GitReaderError: If HEAD cannot be resolved (e.g., empty repo)
        """
        pass
