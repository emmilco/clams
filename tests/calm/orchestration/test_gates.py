"""Tests for CALM orchestration gates module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.gates import (
    GATE_REQUIREMENTS,
    GateCheck,
    GateRequirement,
    list_gates,
    record_gate_pass,
    verify_gate_pass,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


class TestGateRequirements:
    """Tests for gate requirements definitions."""

    def test_feature_transitions_have_requirements(self) -> None:
        """Test that feature transitions have gate requirements."""
        feature_transitions = [
            "SPEC-DESIGN",
            "DESIGN-IMPLEMENT",
            "IMPLEMENT-CODE_REVIEW",
            "CODE_REVIEW-TEST",
            "TEST-INTEGRATE",
            "INTEGRATE-VERIFY",
        ]

        for transition in feature_transitions:
            assert transition in GATE_REQUIREMENTS
            assert len(GATE_REQUIREMENTS[transition]) > 0

    def test_bug_transitions_have_requirements(self) -> None:
        """Test that bug transitions have gate requirements."""
        bug_transitions = [
            "REPORTED-INVESTIGATED",
            "INVESTIGATED-FIXED",
            "FIXED-REVIEWED",
            "REVIEWED-TESTED",
            "TESTED-MERGED",
        ]

        for transition in bug_transitions:
            assert transition in GATE_REQUIREMENTS
            assert len(GATE_REQUIREMENTS[transition]) > 0


class TestGateCheck:
    """Tests for GateCheck dataclass."""

    def test_gate_check_creation(self) -> None:
        """Test creating a GateCheck."""
        check = GateCheck(
            name="Test check",
            passed=True,
            message="All good",
            duration_seconds=1.5,
        )

        assert check.name == "Test check"
        assert check.passed is True
        assert check.message == "All good"
        assert check.duration_seconds == 1.5

    def test_gate_check_defaults(self) -> None:
        """Test GateCheck defaults."""
        check = GateCheck(
            name="Test",
            passed=False,
            message="Failed",
        )

        assert check.duration_seconds is None


class TestGateRequirement:
    """Tests for GateRequirement dataclass."""

    def test_gate_requirement_creation(self) -> None:
        """Test creating a GateRequirement."""
        req = GateRequirement(
            transition="SPEC-DESIGN",
            name="spec_reviews",
            description="2 spec reviews approved",
            automated=True,
        )

        assert req.transition == "SPEC-DESIGN"
        assert req.name == "spec_reviews"
        assert req.description == "2 spec reviews approved"
        assert req.automated is True


class TestListGates:
    """Tests for list_gates function."""

    def test_list_gates_returns_all(self) -> None:
        """Test listing all gates."""
        gates = list_gates()

        # Should have gates for all transitions
        assert len(gates) > 0

        # Check that we have gates for key transitions
        gate_names = {g.name for g in gates}
        assert "spec_reviews" in gate_names
        assert "tests_pass" in gate_names
        assert "code_exists" in gate_names


class TestRecordGatePass:
    """Tests for record_gate_pass function."""

    def test_record_gate_pass(self, test_db: Path) -> None:
        """Test recording a gate pass."""
        record_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            commit_sha="abc1234",
            db_path=test_db,
        )

        # Verify it was recorded
        passed = verify_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            current_sha="abc1234",
            db_path=test_db,
        )
        assert passed is True


class TestVerifyGatePass:
    """Tests for verify_gate_pass function."""

    def test_verify_gate_pass_success(self, test_db: Path) -> None:
        """Test verifying a gate pass that exists."""
        record_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            commit_sha="abc1234",
            db_path=test_db,
        )

        result = verify_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            current_sha="abc1234",
            db_path=test_db,
        )
        assert result is True

    def test_verify_gate_pass_different_commit(self, test_db: Path) -> None:
        """Test verifying gate pass with different commit."""
        record_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            commit_sha="abc1234",
            db_path=test_db,
        )

        result = verify_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            current_sha="def5678",  # Different commit
            db_path=test_db,
        )
        assert result is False

    def test_verify_gate_pass_not_recorded(self, test_db: Path) -> None:
        """Test verifying gate pass that wasn't recorded."""
        result = verify_gate_pass(
            task_id="SPEC-001",
            transition="IMPLEMENT-CODE_REVIEW",
            current_sha="abc1234",
            db_path=test_db,
        )
        assert result is False
