"""Data models for GHAP entries."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Domain(Enum):
    """Domain values match parent spec SPEC-001 exactly."""

    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    FEATURE = "feature"
    TESTING = "testing"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"


class Strategy(Enum):
    """Strategy values match parent spec SPEC-001 exactly."""

    SYSTEMATIC_ELIMINATION = "systematic-elimination"
    TRIAL_AND_ERROR = "trial-and-error"
    RESEARCH_FIRST = "research-first"
    DIVIDE_AND_CONQUER = "divide-and-conquer"
    ROOT_CAUSE_ANALYSIS = "root-cause-analysis"
    COPY_FROM_SIMILAR = "copy-from-similar"
    CHECK_ASSUMPTIONS = "check-assumptions"
    READ_THE_ERROR = "read-the-error"
    ASK_USER = "ask-user"


class OutcomeStatus(Enum):
    """Outcome status for GHAP resolution."""

    CONFIRMED = "confirmed"
    FALSIFIED = "falsified"
    ABANDONED = "abandoned"


class ConfidenceTier(Enum):
    """Confidence tier for GHAP entries."""

    GOLD = "gold"  # Auto-captured outcome (test/build triggered resolution)
    SILVER = "silver"  # Manual resolution (agent explicitly resolved)
    BRONZE = "bronze"  # Poor quality hypothesis (assigned by Persister, not Collector)
    ABANDONED = "abandoned"  # Goal abandoned before resolution


@dataclass
class RootCause:
    """Root cause information for failures."""

    category: str  # wrong-assumption, missing-knowledge, oversight, etc.
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "category": self.category,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RootCause":
        """Parse from dict."""
        return cls(
            category=data["category"],
            description=data["description"],
        )


@dataclass
class Lesson:
    """Lesson learned from GHAP experience."""

    what_worked: str
    takeaway: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "what_worked": self.what_worked,
            "takeaway": self.takeaway,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lesson":
        """Parse from dict."""
        return cls(
            what_worked=data["what_worked"],
            takeaway=data.get("takeaway"),
        )


@dataclass
class HistoryEntry:
    """Historical iteration of hypothesis/action/prediction."""

    timestamp: datetime  # UTC, timezone-aware
    hypothesis: str
    action: str
    prediction: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "hypothesis": self.hypothesis,
            "action": self.action,
            "prediction": self.prediction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        """Parse from dict."""
        # Handle both 'Z' suffix and '+00:00' format
        ts = data["timestamp"].replace("Z", "+00:00")
        return cls(
            timestamp=datetime.fromisoformat(ts),
            hypothesis=data["hypothesis"],
            action=data["action"],
            prediction=data["prediction"],
        )


@dataclass
class Outcome:
    """Resolution outcome for a GHAP entry."""

    status: OutcomeStatus
    result: str
    captured_at: datetime  # UTC, timezone-aware
    auto_captured: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status.value,
            "result": self.result,
            "captured_at": self.captured_at.isoformat().replace("+00:00", "Z"),
            "auto_captured": self.auto_captured,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Outcome":
        """Parse from dict."""
        # Handle both 'Z' suffix and '+00:00' format
        ts = data["captured_at"].replace("Z", "+00:00")
        return cls(
            status=OutcomeStatus(data["status"]),
            result=data["result"],
            captured_at=datetime.fromisoformat(ts),
            auto_captured=data.get("auto_captured", False),
        )


@dataclass
class GHAPEntry:
    """A complete GHAP (Goal-Hypothesis-Action-Prediction) entry."""

    id: str
    session_id: str
    created_at: datetime  # UTC, timezone-aware
    domain: Domain
    strategy: Strategy
    goal: str

    # Current state
    hypothesis: str
    action: str
    prediction: str

    # History of iterations
    history: list[HistoryEntry] = field(default_factory=list)
    iteration_count: int = 1

    # Resolution (filled when resolved)
    outcome: Outcome | None = None
    surprise: str | None = None
    root_cause: RootCause | None = None
    lesson: Lesson | None = None

    # Metadata
    confidence_tier: ConfidenceTier | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "domain": self.domain.value,
            "strategy": self.strategy.value,
            "goal": self.goal,
            "hypothesis": self.hypothesis,
            "action": self.action,
            "prediction": self.prediction,
            "history": [h.to_dict() for h in self.history],
            "iteration_count": self.iteration_count,
            "notes": self.notes,
        }

        # Optional fields
        if self.outcome is not None:
            result["outcome"] = self.outcome.to_dict()
        if self.surprise is not None:
            result["surprise"] = self.surprise
        if self.root_cause is not None:
            result["root_cause"] = self.root_cause.to_dict()
        if self.lesson is not None:
            result["lesson"] = self.lesson.to_dict()
        if self.confidence_tier is not None:
            result["confidence_tier"] = self.confidence_tier.value

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GHAPEntry":
        """Parse from dict with validation."""
        # Handle both 'Z' suffix and '+00:00' format for timestamps
        created_ts = data["created_at"].replace("Z", "+00:00")

        # Parse history
        history = [HistoryEntry.from_dict(h) for h in data.get("history", [])]

        # Parse optional outcome
        outcome = None
        if "outcome" in data and data["outcome"] is not None:
            outcome = Outcome.from_dict(data["outcome"])

        # Parse optional root_cause
        root_cause = None
        if "root_cause" in data and data["root_cause"] is not None:
            root_cause = RootCause.from_dict(data["root_cause"])

        # Parse optional lesson
        lesson = None
        if "lesson" in data and data["lesson"] is not None:
            lesson = Lesson.from_dict(data["lesson"])

        # Parse optional confidence_tier
        confidence_tier = None
        if "confidence_tier" in data and data["confidence_tier"] is not None:
            confidence_tier = ConfidenceTier(data["confidence_tier"])

        return cls(
            id=data["id"],
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(created_ts),
            domain=Domain(data["domain"]),
            strategy=Strategy(data["strategy"]),
            goal=data["goal"],
            hypothesis=data["hypothesis"],
            action=data["action"],
            prediction=data["prediction"],
            history=history,
            iteration_count=data.get("iteration_count", 1),
            outcome=outcome,
            surprise=data.get("surprise"),
            root_cause=root_cause,
            lesson=lesson,
            confidence_tier=confidence_tier,
            notes=data.get("notes", []),
        )
