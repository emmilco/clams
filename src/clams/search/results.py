"""Result dataclasses for search operations."""

from dataclasses import dataclass
from datetime import datetime

from clams.observation.models import Lesson, RootCause
from clams.storage.base import SearchResult

__all__ = [
    "CodeResult",
    "CommitResult",
    "ExperienceResult",
    "Lesson",
    "MemoryResult",
    "RootCause",
    "ValueResult",
]


@dataclass
class MemoryResult:
    """Result from memory search."""

    id: str
    category: str
    content: str
    score: float
    importance: float
    tags: list[str]
    created_at: datetime
    verified_at: datetime | None
    verification_status: str | None  # "passed", "failed", "pending", None

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "MemoryResult":
        """Convert VectorStore SearchResult to MemoryResult.

        Note: Datetime handling uses fromisoformat() which supports both
        'Z' and '+00:00' timezone formats. All datetimes should be timezone-aware UTC.

        Args:
            result: Raw search result from VectorStore

        Returns:
            Typed MemoryResult instance

        Raises:
            KeyError: If required payload fields are missing
            ValueError: If field values are invalid
        """
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            category=payload["category"],
            content=payload["content"],
            importance=payload.get("importance", 0.0),
            tags=payload.get("tags", []),
            created_at=datetime.fromisoformat(payload["created_at"]),
            verified_at=(
                datetime.fromisoformat(payload["verified_at"])
                if payload.get("verified_at")
                else None
            ),
            verification_status=payload.get("verification_status"),
        )


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

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "CodeResult":
        """Convert VectorStore SearchResult to CodeResult.

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

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "ExperienceResult":
        """Convert VectorStore SearchResult to ExperienceResult.

        Args:
            result: Raw search result from VectorStore

        Returns:
            Typed ExperienceResult instance

        Raises:
            KeyError: If required payload fields are missing
            ValueError: If field values are invalid
        """
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            ghap_id=payload["ghap_id"],
            axis=payload["axis"],
            domain=payload["domain"],
            strategy=payload["strategy"],
            goal=payload["goal"],
            hypothesis=payload["hypothesis"],
            action=payload["action"],
            prediction=payload["prediction"],
            outcome_status=payload["outcome_status"],
            outcome_result=payload["outcome_result"],
            surprise=payload.get("surprise"),
            root_cause=(
                RootCause(**payload["root_cause"])
                if payload.get("root_cause")
                else None
            ),
            lesson=(
                Lesson(**payload["lesson"]) if payload.get("lesson") else None
            ),
            confidence_tier=payload["confidence_tier"],
            iteration_count=payload["iteration_count"],
            created_at=datetime.fromisoformat(payload["created_at"]),
        )


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

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "ValueResult":
        """Convert VectorStore SearchResult to ValueResult.

        Args:
            result: Raw search result from VectorStore

        Returns:
            Typed ValueResult instance

        Raises:
            KeyError: If required payload fields are missing
            ValueError: If field values are invalid
        """
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            axis=payload["axis"],
            cluster_id=payload["cluster_id"],
            text=payload["text"],
            member_count=payload["member_count"],
            avg_confidence=payload["avg_confidence"],
            created_at=datetime.fromisoformat(payload["created_at"]),
        )


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

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "CommitResult":
        """Convert VectorStore SearchResult to CommitResult.

        Args:
            result: Raw search result from VectorStore

        Returns:
            Typed CommitResult instance

        Raises:
            KeyError: If required payload fields are missing
            ValueError: If field values are invalid
        """
        payload = result.payload
        return cls(
            id=result.id,
            score=result.score,
            sha=payload["sha"],
            message=payload["message"],
            author=payload["author"],
            author_email=payload["author_email"],
            committed_at=datetime.fromisoformat(payload["committed_at"]),
            files_changed=payload["files_changed"],
        )
