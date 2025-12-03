"""Tests for ObservationCollector."""

import json
from pathlib import Path

import pytest

from learning_memory_server.observation import (
    ConfidenceTier,
    Domain,
    GHAPAlreadyActiveError,
    Lesson,
    NoActiveGHAPError,
    ObservationCollector,
    OutcomeStatus,
    RootCause,
    Strategy,
)


@pytest.fixture
async def journal_dir(tmp_path: Path) -> Path:
    """Create isolated journal directory."""
    return tmp_path / "journal"


@pytest.fixture
async def collector(journal_dir: Path) -> ObservationCollector:
    """Create collector with temp directory."""
    return ObservationCollector(journal_dir)


# === GHAP Lifecycle Tests ===


async def test_create_ghap(collector: ObservationCollector) -> None:
    """Test GHAP creation."""
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test failure",
        hypothesis="Cache pollution",
        action="Add teardown",
        prediction="Test passes consistently",
    )

    assert entry.id.startswith("ghap_")
    assert entry.session_id.startswith("session_")
    assert entry.domain == Domain.DEBUGGING
    assert entry.strategy == Strategy.SYSTEMATIC_ELIMINATION
    assert entry.goal == "Fix test failure"
    assert entry.hypothesis == "Cache pollution"
    assert entry.action == "Add teardown"
    assert entry.prediction == "Test passes consistently"
    assert entry.iteration_count == 1
    assert entry.history == []
    assert entry.outcome is None

    # Verify persistence
    current = await collector.get_current()
    assert current is not None
    assert current.id == entry.id


async def test_create_ghap_auto_starts_session(
    collector: ObservationCollector,
) -> None:
    """Test that creating GHAP auto-starts session if not started."""
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H",
        action="A",
        prediction="P",
    )

    session_id = await collector.get_session_id()
    assert session_id is not None
    assert entry.session_id == session_id


async def test_create_ghap_when_active_raises(
    collector: ObservationCollector,
) -> None:
    """Test creating GHAP when one is already active raises error."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="First",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    with pytest.raises(GHAPAlreadyActiveError):
        await collector.create_ghap(
            domain=Domain.FEATURE,
            strategy=Strategy.RESEARCH_FIRST,
            goal="Second",
            hypothesis="H2",
            action="A2",
            prediction="P2",
        )


async def test_update_ghap_changes_hypothesis(
    collector: ObservationCollector,
) -> None:
    """Test updating hypothesis pushes to history."""
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    updated = await collector.update_ghap(hypothesis="H2")

    assert updated.hypothesis == "H2"
    assert updated.action == "A1"
    assert updated.prediction == "P1"
    assert updated.iteration_count == 2
    assert len(updated.history) == 1
    assert updated.history[0].hypothesis == "H1"
    assert updated.history[0].action == "A1"
    assert updated.history[0].prediction == "P1"


async def test_update_ghap_changes_all_hap(collector: ObservationCollector) -> None:
    """Test updating all H/A/P fields."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    updated = await collector.update_ghap(
        hypothesis="H2", action="A2", prediction="P2"
    )

    assert updated.hypothesis == "H2"
    assert updated.action == "A2"
    assert updated.prediction == "P2"
    assert updated.iteration_count == 2
    assert len(updated.history) == 1


async def test_update_ghap_note_only(collector: ObservationCollector) -> None:
    """Test updating with only note doesn't create history entry."""
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    updated = await collector.update_ghap(note="Checked logs")

    assert updated.hypothesis == "H1"
    assert updated.iteration_count == 1
    assert len(updated.history) == 0
    assert "Checked logs" in updated.notes


async def test_update_ghap_strategy_only(collector: ObservationCollector) -> None:
    """Test updating only strategy doesn't create history entry."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    updated = await collector.update_ghap(strategy=Strategy.TRIAL_AND_ERROR)

    assert updated.strategy == Strategy.TRIAL_AND_ERROR
    assert updated.iteration_count == 1
    assert len(updated.history) == 0


async def test_update_ghap_no_active_raises(collector: ObservationCollector) -> None:
    """Test updating without active GHAP raises error."""
    with pytest.raises(NoActiveGHAPError):
        await collector.update_ghap(hypothesis="H2")


async def test_resolve_ghap_confirmed(collector: ObservationCollector) -> None:
    """Test resolving GHAP as confirmed."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    resolved = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Test passes now",
        surprise="Unexpected side effect",
        root_cause=RootCause(category="oversight", description="Missed edge case"),
        lesson=Lesson(what_worked="Check all branches", takeaway="Use coverage"),
        auto_captured=False,
    )

    assert resolved.outcome is not None
    assert resolved.outcome.status == OutcomeStatus.CONFIRMED
    assert resolved.outcome.result == "Test passes now"
    assert resolved.outcome.auto_captured is False
    assert resolved.surprise == "Unexpected side effect"
    assert resolved.root_cause is not None
    assert resolved.root_cause.category == "oversight"
    assert resolved.lesson is not None
    assert resolved.lesson.what_worked == "Check all branches"
    assert resolved.confidence_tier == ConfidenceTier.SILVER

    # Current should be cleared
    current = await collector.get_current()
    assert current is None

    # Should be in session entries
    entries = await collector.get_session_entries()
    assert len(entries) == 1
    assert entries[0].id == resolved.id


async def test_resolve_ghap_auto_captured_gold(
    collector: ObservationCollector,
) -> None:
    """Test auto-captured resolution gets GOLD tier."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    resolved = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Test passes",
        auto_captured=True,
    )

    assert resolved.confidence_tier == ConfidenceTier.GOLD


async def test_abandon_ghap(collector: ObservationCollector) -> None:
    """Test abandoning GHAP."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    abandoned = await collector.abandon_ghap("Not relevant anymore")

    assert abandoned.outcome is not None
    assert abandoned.outcome.status == OutcomeStatus.ABANDONED
    assert abandoned.outcome.result == "Not relevant anymore"
    assert abandoned.confidence_tier == ConfidenceTier.ABANDONED

    # Current should be cleared
    current = await collector.get_current()
    assert current is None


# === Session Management Tests ===


async def test_start_session(collector: ObservationCollector) -> None:
    """Test starting a session."""
    session_id = await collector.start_session()

    assert session_id.startswith("session_")

    retrieved = await collector.get_session_id()
    assert retrieved == session_id


async def test_start_session_archives_previous(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test starting new session archives previous entries."""
    # Start first session and create entry
    session1 = await collector.start_session()
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )
    await collector.resolve_ghap(OutcomeStatus.CONFIRMED, "Success")

    # Start new session
    session2 = await collector.start_session()

    assert session2 != session1

    # Session entries should be cleared
    entries = await collector.get_session_entries()
    assert len(entries) == 0

    # Archive should exist
    archive_files = list((journal_dir / "archive").glob("*.jsonl"))
    assert len(archive_files) == 1


async def test_end_session(collector: ObservationCollector) -> None:
    """Test ending a session."""
    await collector.start_session()
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )
    await collector.resolve_ghap(OutcomeStatus.CONFIRMED, "Success")

    entries = await collector.end_session()

    assert len(entries) == 1

    # Session ID should be cleared
    session_id = await collector.get_session_id()
    assert session_id is None

    # Session entries should be cleared
    remaining = await collector.get_session_entries()
    assert len(remaining) == 0


async def test_end_session_abandons_current(
    collector: ObservationCollector,
) -> None:
    """Test ending session abandons current GHAP."""
    await collector.start_session()
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    entries = await collector.end_session()

    assert len(entries) == 1
    assert entries[0].outcome is not None
    assert entries[0].outcome.status == OutcomeStatus.ABANDONED
    assert entries[0].outcome.result == "session ended"


# === Orphan Handling Tests ===


async def test_has_orphaned_entry(collector: ObservationCollector) -> None:
    """Test orphan detection."""
    # Create entry in first session
    session1 = await collector.start_session()
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Start new session (without resolving)
    session2 = await collector.start_session()

    # Should detect orphan
    has_orphan = await collector.has_orphaned_entry()
    assert has_orphan is True

    orphan = await collector.get_orphaned_entry()
    assert orphan is not None
    assert orphan.session_id == session1


async def test_adopt_orphan(collector: ObservationCollector) -> None:
    """Test adopting orphaned entry."""
    # Create entry in first session
    session1 = await collector.start_session()
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Start new session
    session2 = await collector.start_session()

    # Adopt orphan
    adopted = await collector.adopt_orphan()

    assert adopted is not None
    assert adopted.id == entry.id
    assert adopted.session_id == session2

    # Should no longer be orphaned
    has_orphan = await collector.has_orphaned_entry()
    assert has_orphan is False


async def test_abandon_orphan(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test abandoning orphaned entry."""
    # Create entry in first session
    session1 = await collector.start_session()
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Start new session
    session2 = await collector.start_session()

    # Abandon orphan
    abandoned = await collector.abandon_orphan("Session crashed")

    assert abandoned is not None
    assert abandoned.id == entry.id
    assert abandoned.outcome is not None
    assert abandoned.outcome.status == OutcomeStatus.ABANDONED
    assert abandoned.outcome.result == "Session crashed"

    # Current should be cleared
    current = await collector.get_current()
    assert current is None

    # Should be archived to original session
    archive_files = list((journal_dir / "archive").glob("*.jsonl"))
    assert len(archive_files) >= 1


# === Tool Count Tests ===


async def test_increment_tool_count(collector: ObservationCollector) -> None:
    """Test tool count increment."""
    count1 = await collector.increment_tool_count()
    assert count1 == 1

    count2 = await collector.increment_tool_count()
    assert count2 == 2

    count3 = await collector.increment_tool_count()
    assert count3 == 3


async def test_should_check_in(collector: ObservationCollector) -> None:
    """Test check-in logic."""
    # No check-in without active GHAP
    assert await collector.should_check_in(frequency=3) is False

    # Create GHAP
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Not yet at frequency
    await collector.increment_tool_count()
    await collector.increment_tool_count()
    assert await collector.should_check_in(frequency=3) is False

    # At frequency
    await collector.increment_tool_count()
    assert await collector.should_check_in(frequency=3) is True


async def test_reset_tool_count(collector: ObservationCollector) -> None:
    """Test resetting tool count."""
    await collector.increment_tool_count()
    await collector.increment_tool_count()
    await collector.increment_tool_count()

    await collector.reset_tool_count()

    count = await collector.increment_tool_count()
    assert count == 1


async def test_tool_count_persists(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test tool count persists across collector instances."""
    await collector.increment_tool_count()
    await collector.increment_tool_count()

    # Create new collector
    collector2 = ObservationCollector(journal_dir)
    count = await collector2.increment_tool_count()

    assert count == 3


# === Integration Tests ===


async def test_full_session_lifecycle(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test complete session from start to end."""
    # Start session
    session_id = await collector.start_session()

    # Create and resolve multiple GHAPs
    for i in range(3):
        await collector.create_ghap(
            domain=Domain.DEBUGGING,
            strategy=Strategy.SYSTEMATIC_ELIMINATION,
            goal=f"Fix test {i}",
            hypothesis=f"H{i}",
            action=f"A{i}",
            prediction=f"P{i}",
        )
        await collector.resolve_ghap(
            status=OutcomeStatus.CONFIRMED,
            result=f"Success {i}",
        )

    # End session
    entries = await collector.end_session()
    assert len(entries) == 3

    # Verify archive created
    archives = list((journal_dir / "archive").glob("*.jsonl"))
    assert len(archives) == 1

    # Verify archive content
    with open(archives[0]) as f:
        lines = f.readlines()
        assert len(lines) == 3


async def test_state_survives_restart(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test state persists across collector instances."""
    # Create GHAP
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Create new collector instance
    collector2 = ObservationCollector(journal_dir)

    # State should persist
    current = await collector2.get_current()
    assert current is not None
    assert current.id == entry.id
    assert current.goal == "Fix test"


async def test_multiple_iterations(collector: ObservationCollector) -> None:
    """Test multiple H/A/P iterations build history correctly."""
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    await collector.update_ghap(hypothesis="H2", action="A2", prediction="P2")
    await collector.update_ghap(hypothesis="H3", action="A3", prediction="P3")

    current = await collector.get_current()
    assert current is not None
    assert current.iteration_count == 3
    assert len(current.history) == 2
    assert current.hypothesis == "H3"
    assert current.history[0].hypothesis == "H1"
    assert current.history[1].hypothesis == "H2"


async def test_text_truncation(collector: ObservationCollector) -> None:
    """Test long text is truncated."""
    long_text = "x" * 15000

    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal=long_text,
        hypothesis="H",
        action="A",
        prediction="P",
    )

    assert len(entry.goal) == 10000


# === Error Handling Tests ===


async def test_corrupted_current_ghap_recovery(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test recovery from corrupted current_ghap.json."""
    # Create valid GHAP
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )

    # Corrupt the file
    ghap_path = journal_dir / "current_ghap.json"
    ghap_path.write_text("invalid json {{{")

    # Should recover gracefully
    current = await collector.get_current()
    assert current is None

    # Backup should exist (with_suffix replaces .json with .corrupted.timestamp)
    backup_files = list(journal_dir.glob("current_ghap.corrupted.*"))
    assert len(backup_files) == 1


async def test_corrupted_session_entries_recovery(
    collector: ObservationCollector, journal_dir: Path
) -> None:
    """Test recovery from corrupted session_entries.jsonl."""
    # Create and resolve valid GHAPs
    await collector.start_session()
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test 1",
        hypothesis="H1",
        action="A1",
        prediction="P1",
    )
    await collector.resolve_ghap(OutcomeStatus.CONFIRMED, "Success 1")

    # Corrupt entries file by adding invalid line
    entries_path = journal_dir / "session_entries.jsonl"
    with open(entries_path, "a") as f:
        f.write("invalid json line\n")

    # Add another valid entry
    await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test 2",
        hypothesis="H2",
        action="A2",
        prediction="P2",
    )
    await collector.resolve_ghap(OutcomeStatus.CONFIRMED, "Success 2")

    # Should recover valid entries, skip corrupted
    entries = await collector.get_session_entries()
    assert len(entries) == 2  # Both valid entries loaded
