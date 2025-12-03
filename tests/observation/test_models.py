"""Tests for observation data models."""

from datetime import UTC, datetime

from learning_memory_server.observation.models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    HistoryEntry,
    Lesson,
    Outcome,
    OutcomeStatus,
    RootCause,
    Strategy,
)


def test_root_cause_serialization() -> None:
    """Test RootCause to_dict and from_dict."""
    rc = RootCause(category="wrong-assumption", description="Test description")
    data = rc.to_dict()

    assert data["category"] == "wrong-assumption"
    assert data["description"] == "Test description"

    restored = RootCause.from_dict(data)
    assert restored.category == rc.category
    assert restored.description == rc.description


def test_lesson_serialization() -> None:
    """Test Lesson to_dict and from_dict."""
    lesson = Lesson(what_worked="Try X first", takeaway="Always check Y")
    data = lesson.to_dict()

    assert data["what_worked"] == "Try X first"
    assert data["takeaway"] == "Always check Y"

    restored = Lesson.from_dict(data)
    assert restored.what_worked == lesson.what_worked
    assert restored.takeaway == lesson.takeaway


def test_lesson_optional_takeaway() -> None:
    """Test Lesson with None takeaway."""
    lesson = Lesson(what_worked="Try X first", takeaway=None)
    data = lesson.to_dict()

    assert data["what_worked"] == "Try X first"
    assert data["takeaway"] is None

    restored = Lesson.from_dict(data)
    assert restored.takeaway is None


def test_history_entry_serialization() -> None:
    """Test HistoryEntry to_dict and from_dict."""
    ts = datetime.now(UTC)
    entry = HistoryEntry(
        timestamp=ts,
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )
    data = entry.to_dict()

    assert data["hypothesis"] == "H1"
    assert data["action"] == "A1"
    assert data["prediction"] == "P1"
    assert data["timestamp"].endswith("Z")

    restored = HistoryEntry.from_dict(data)
    assert restored.hypothesis == entry.hypothesis
    assert restored.action == entry.action
    assert restored.prediction == entry.prediction
    # Timestamps should be equal within microsecond precision
    assert abs((restored.timestamp - entry.timestamp).total_seconds()) < 0.001


def test_outcome_serialization() -> None:
    """Test Outcome to_dict and from_dict."""
    ts = datetime.now(UTC)
    outcome = Outcome(
        status=OutcomeStatus.CONFIRMED,
        result="Success",
        captured_at=ts,
        auto_captured=True,
    )
    data = outcome.to_dict()

    assert data["status"] == "confirmed"
    assert data["result"] == "Success"
    assert data["auto_captured"] is True
    assert data["captured_at"].endswith("Z")

    restored = Outcome.from_dict(data)
    assert restored.status == outcome.status
    assert restored.result == outcome.result
    assert restored.auto_captured == outcome.auto_captured
    assert abs((restored.captured_at - outcome.captured_at).total_seconds()) < 0.001


def test_ghap_entry_minimal_serialization() -> None:
    """Test GHAPEntry serialization with minimal fields."""
    ts = datetime.now(UTC)
    entry = GHAPEntry(
        id="ghap_20251203_140000_abc123",
        session_id="session_20251203_140000_xyz789",
        created_at=ts,
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    data = entry.to_dict()

    assert data["id"] == "ghap_20251203_140000_abc123"
    assert data["session_id"] == "session_20251203_140000_xyz789"
    assert data["domain"] == "debugging"
    assert data["strategy"] == "systematic-elimination"
    assert data["goal"] == "Fix test"
    assert data["hypothesis"] == "H1"
    assert data["action"] == "A1"
    assert data["prediction"] == "P1"
    assert data["iteration_count"] == 1
    assert data["history"] == []
    assert data["notes"] == []
    assert "outcome" not in data
    assert "surprise" not in data
    assert "root_cause" not in data
    assert "lesson" not in data
    assert "confidence_tier" not in data

    restored = GHAPEntry.from_dict(data)
    assert restored.id == entry.id
    assert restored.session_id == entry.session_id
    assert restored.domain == entry.domain
    assert restored.strategy == entry.strategy
    assert restored.goal == entry.goal
    assert restored.hypothesis == entry.hypothesis
    assert restored.action == entry.action
    assert restored.prediction == entry.prediction
    assert restored.iteration_count == entry.iteration_count
    assert restored.history == []
    assert restored.notes == []
    assert restored.outcome is None
    assert restored.surprise is None
    assert restored.root_cause is None
    assert restored.lesson is None
    assert restored.confidence_tier is None


def test_ghap_entry_full_serialization() -> None:
    """Test GHAPEntry serialization with all fields."""
    ts = datetime.now(UTC)
    entry = GHAPEntry(
        id="ghap_20251203_140000_abc123",
        session_id="session_20251203_140000_xyz789",
        created_at=ts,
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H2",
        action="A2",
        prediction="P2",
        history=[
            HistoryEntry(timestamp=ts, hypothesis="H1", action="A1", prediction="P1")
        ],
        iteration_count=2,
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Success",
            captured_at=ts,
            auto_captured=True,
        ),
        surprise="Unexpected behavior",
        root_cause=RootCause(category="oversight", description="Missed case"),
        lesson=Lesson(what_worked="Check logs", takeaway="Always verify"),
        confidence_tier=ConfidenceTier.GOLD,
        notes=["Note 1", "Note 2"],
    )

    data = entry.to_dict()

    assert data["iteration_count"] == 2
    assert len(data["history"]) == 1
    assert data["outcome"]["status"] == "confirmed"
    assert data["surprise"] == "Unexpected behavior"
    assert data["root_cause"]["category"] == "oversight"
    assert data["lesson"]["what_worked"] == "Check logs"
    assert data["confidence_tier"] == "gold"
    assert len(data["notes"]) == 2

    restored = GHAPEntry.from_dict(data)
    assert restored.iteration_count == 2
    assert len(restored.history) == 1
    assert restored.outcome is not None
    assert restored.outcome.status == OutcomeStatus.CONFIRMED
    assert restored.surprise == "Unexpected behavior"
    assert restored.root_cause is not None
    assert restored.root_cause.category == "oversight"
    assert restored.lesson is not None
    assert restored.lesson.what_worked == "Check logs"
    assert restored.confidence_tier == ConfidenceTier.GOLD
    assert len(restored.notes) == 2


def test_domain_enum_values() -> None:
    """Test Domain enum has expected values."""
    assert Domain.DEBUGGING.value == "debugging"
    assert Domain.REFACTORING.value == "refactoring"
    assert Domain.FEATURE.value == "feature"
    assert Domain.TESTING.value == "testing"
    assert Domain.CONFIGURATION.value == "configuration"
    assert Domain.DOCUMENTATION.value == "documentation"
    assert Domain.PERFORMANCE.value == "performance"
    assert Domain.SECURITY.value == "security"
    assert Domain.INTEGRATION.value == "integration"


def test_strategy_enum_values() -> None:
    """Test Strategy enum has expected values."""
    assert Strategy.SYSTEMATIC_ELIMINATION.value == "systematic-elimination"
    assert Strategy.TRIAL_AND_ERROR.value == "trial-and-error"
    assert Strategy.RESEARCH_FIRST.value == "research-first"
    assert Strategy.DIVIDE_AND_CONQUER.value == "divide-and-conquer"
    assert Strategy.ROOT_CAUSE_ANALYSIS.value == "root-cause-analysis"
    assert Strategy.COPY_FROM_SIMILAR.value == "copy-from-similar"
    assert Strategy.CHECK_ASSUMPTIONS.value == "check-assumptions"
    assert Strategy.READ_THE_ERROR.value == "read-the-error"
    assert Strategy.ASK_USER.value == "ask-user"


def test_outcome_status_enum_values() -> None:
    """Test OutcomeStatus enum has expected values."""
    assert OutcomeStatus.CONFIRMED.value == "confirmed"
    assert OutcomeStatus.FALSIFIED.value == "falsified"
    assert OutcomeStatus.ABANDONED.value == "abandoned"


def test_confidence_tier_enum_values() -> None:
    """Test ConfidenceTier enum has expected values."""
    assert ConfidenceTier.GOLD.value == "gold"
    assert ConfidenceTier.SILVER.value == "silver"
    assert ConfidenceTier.BRONZE.value == "bronze"
    assert ConfidenceTier.ABANDONED.value == "abandoned"
