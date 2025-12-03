"""Git history integration for Learning Memory Server.

Provides git history analysis, semantic commit search, blame lookup,
and churn analysis.
"""

from .analyzer import GitAnalyzer
from .base import (
    AuthorStats,
    BinaryFileError,
    BlameEntry,
    BlameSearchResult,
    ChurnRecord,
    Commit,
    FileNotInRepoError,
    GitAnalyzerError,
    GitReader,
    GitReaderError,
    IndexingError,
    IndexingStats,
    RepositoryNotFoundError,
    ShallowCloneError,
)
from .reader import GitPythonReader

__all__ = [
    # Classes
    "GitAnalyzer",
    "GitPythonReader",
    "GitReader",
    # Data classes
    "Commit",
    "BlameEntry",
    "ChurnRecord",
    "AuthorStats",
    "BlameSearchResult",
    "IndexingStats",
    "IndexingError",
    # Errors
    "GitReaderError",
    "RepositoryNotFoundError",
    "FileNotInRepoError",
    "BinaryFileError",
    "ShallowCloneError",
    "GitAnalyzerError",
]
