"""Tests for CALM GHAP modules."""

import tempfile
from pathlib import Path

import pytest

from calm.ghap import (
    ConfidenceTier,
    Domain,
    ObservationCollector,
    OutcomeStatus,
    Strategy,
)


class TestGHAPModels:
    """Test GHAP data models."""

    def test_domain_enum_values(self) -> None:
        """Test Domain enum has expected values."""
        assert Domain.DEBUGGING.value == "debugging"
        assert Domain.REFACTORING.value == "refactoring"
        assert Domain.FEATURE.value == "feature"
        assert Domain.TESTING.value == "testing"

    def test_strategy_enum_values(self) -> None:
        """Test Strategy enum has expected values."""
        assert Strategy.SYSTEMATIC_ELIMINATION.value == "systematic-elimination"
        assert Strategy.TRIAL_AND_ERROR.value == "trial-and-error"
        assert Strategy.ROOT_CAUSE_ANALYSIS.value == "root-cause-analysis"

    def test_outcome_status_enum_values(self) -> None:
        """Test OutcomeStatus enum has expected values."""
        assert OutcomeStatus.CONFIRMED.value == "confirmed"
        assert OutcomeStatus.FALSIFIED.value == "falsified"
        assert OutcomeStatus.ABANDONED.value == "abandoned"

    def test_confidence_tier_enum_values(self) -> None:
        """Test ConfidenceTier enum has expected values."""
        assert ConfidenceTier.GOLD.value == "gold"
        assert ConfidenceTier.SILVER.value == "silver"
        assert ConfidenceTier.BRONZE.value == "bronze"
        assert ConfidenceTier.ABANDONED.value == "abandoned"


class TestObservationCollector:
    """Test ObservationCollector functionality."""

    @pytest.fixture
    def journal_dir(self) -> Path:
        """Create a temporary journal directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def collector(self, journal_dir: Path) -> ObservationCollector:
        """Create an ObservationCollector instance for testing."""
        return ObservationCollector(journal_dir)

    @pytest.mark.asyncio
    async def test_create_ghap(self, collector: ObservationCollector) -> None:
        """Test creating a GHAP entry."""
        entry = await collector.create_ghap(
            domain=Domain.DEBUGGING,
            strategy=Strategy.ROOT_CAUSE_ANALYSIS,
            goal="Fix the null pointer exception",
            hypothesis="The error occurs because variable x is not initialized",
            action="Add initialization for variable x",
            prediction="The null pointer exception will be resolved",
        )

        assert entry.id is not None
        assert entry.id.startswith("ghap_")
        assert entry.domain == Domain.DEBUGGING
        assert entry.strategy == Strategy.ROOT_CAUSE_ANALYSIS
        assert entry.goal == "Fix the null pointer exception"
        assert entry.iteration_count == 1

    @pytest.mark.asyncio
    async def test_get_current(self, collector: ObservationCollector) -> None:
        """Test getting current active GHAP entry."""
        # Initially no active entry
        current = await collector.get_current()
        assert current is None

        # Create an entry
        entry = await collector.create_ghap(
            domain=Domain.FEATURE,
            strategy=Strategy.DIVIDE_AND_CONQUER,
            goal="Implement new feature",
            hypothesis="Break into subtasks",
            action="Complete first subtask",
            prediction="First subtask will work",
        )

        # Now there should be an active entry
        current = await collector.get_current()
        assert current is not None
        assert current.id == entry.id

    @pytest.mark.asyncio
    async def test_update_ghap(self, collector: ObservationCollector) -> None:
        """Test updating a GHAP entry."""
        await collector.create_ghap(
            domain=Domain.DEBUGGING,
            strategy=Strategy.TRIAL_AND_ERROR,
            goal="Find the bug",
            hypothesis="Original hypothesis",
            action="Original action",
            prediction="Original prediction",
        )

        # Update the entry
        updated = await collector.update_ghap(
            hypothesis="Updated hypothesis",
            action="Updated action",
        )

        assert updated.hypothesis == "Updated hypothesis"
        assert updated.action == "Updated action"
        assert updated.prediction == "Original prediction"  # Unchanged
        assert updated.iteration_count == 2  # Incremented
        assert len(updated.history) == 1  # Original state saved

    @pytest.mark.asyncio
    async def test_resolve_ghap_confirmed(
        self, collector: ObservationCollector
    ) -> None:
        """Test resolving a GHAP entry as confirmed."""
        await collector.create_ghap(
            domain=Domain.TESTING,
            strategy=Strategy.CHECK_ASSUMPTIONS,
            goal="Verify assumption",
            hypothesis="The assumption is correct",
            action="Write test to verify",
            prediction="Test will pass",
        )

        resolved = await collector.resolve_ghap(
            status=OutcomeStatus.CONFIRMED,
            result="Test passed as expected",
        )

        assert resolved.outcome is not None
        assert resolved.outcome.status == OutcomeStatus.CONFIRMED
        assert resolved.outcome.result == "Test passed as expected"
        assert resolved.confidence_tier == ConfidenceTier.SILVER

        # Entry should be cleared
        current = await collector.get_current()
        assert current is None

    @pytest.mark.asyncio
    async def test_resolve_ghap_falsified(
        self, collector: ObservationCollector
    ) -> None:
        """Test resolving a GHAP entry as falsified."""
        from calm.ghap import Lesson, RootCause

        await collector.create_ghap(
            domain=Domain.DEBUGGING,
            strategy=Strategy.ROOT_CAUSE_ANALYSIS,
            goal="Find root cause",
            hypothesis="Problem is in module A",
            action="Investigate module A",
            prediction="Will find bug in module A",
        )

        resolved = await collector.resolve_ghap(
            status=OutcomeStatus.FALSIFIED,
            result="Bug was actually in module B",
            surprise="Module A was functioning correctly",
            root_cause=RootCause(
                category="wrong-assumption",
                description="Assumed module A was faulty without evidence",
            ),
            lesson=Lesson(
                what_worked="Systematic investigation",
                takeaway="Check all modules before focusing",
            ),
        )

        assert resolved.outcome is not None
        assert resolved.outcome.status == OutcomeStatus.FALSIFIED
        assert resolved.surprise == "Module A was functioning correctly"
        assert resolved.root_cause is not None
        assert resolved.root_cause.category == "wrong-assumption"
        assert resolved.lesson is not None
        assert resolved.lesson.what_worked == "Systematic investigation"

    @pytest.mark.asyncio
    async def test_abandon_ghap(self, collector: ObservationCollector) -> None:
        """Test abandoning a GHAP entry."""
        await collector.create_ghap(
            domain=Domain.FEATURE,
            strategy=Strategy.RESEARCH_FIRST,
            goal="Implement feature",
            hypothesis="This approach will work",
            action="Start implementation",
            prediction="Feature will be complete",
        )

        abandoned = await collector.abandon_ghap("Requirements changed")

        assert abandoned.outcome is not None
        assert abandoned.outcome.status == OutcomeStatus.ABANDONED
        assert abandoned.outcome.result == "Requirements changed"
        assert abandoned.confidence_tier == ConfidenceTier.ABANDONED

    @pytest.mark.asyncio
    async def test_session_management(self, collector: ObservationCollector) -> None:
        """Test session ID management."""
        # Start a session
        session_id = await collector.start_session()
        assert session_id is not None
        assert session_id.startswith("session_")

        # Get current session ID
        current_id = await collector.get_session_id()
        assert current_id == session_id

    @pytest.mark.asyncio
    async def test_tool_count(self, collector: ObservationCollector) -> None:
        """Test tool count tracking."""
        # Start session
        await collector.start_session()

        # Increment tool count
        count1 = await collector.increment_tool_count()
        assert count1 == 1

        count2 = await collector.increment_tool_count()
        assert count2 == 2

        # Reset count
        await collector.reset_tool_count()

        # Should be back to 0 after next increment
        count3 = await collector.increment_tool_count()
        assert count3 == 1
