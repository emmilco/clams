"""Git history integration for CALM.

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
    "GitAnalyzer",
    "GitPythonReader",
    "GitReader",
    "Commit",
    "BlameEntry",
    "ChurnRecord",
    "AuthorStats",
    "BlameSearchResult",
    "IndexingStats",
    "IndexingError",
    "GitReaderError",
    "RepositoryNotFoundError",
    "FileNotInRepoError",
    "BinaryFileError",
    "ShallowCloneError",
    "GitAnalyzerError",
]
