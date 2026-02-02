"""Tests for CALM orchestration phases module."""

import pytest

from calm.orchestration.phases import (
    BUG_PHASES,
    BUG_TRANSITIONS,
    FEATURE_PHASES,
    FEATURE_TRANSITIONS,
    get_initial_phase,
    get_next_phases,
    get_phases,
    get_transition_name,
    get_transitions,
    is_valid_transition,
    parse_transition,
)


class TestPhaseDefinitions:
    """Tests for phase definitions."""

    def test_feature_phases_order(self) -> None:
        """Test that feature phases are in correct order."""
        assert FEATURE_PHASES == [
            "SPEC",
            "DESIGN",
            "IMPLEMENT",
            "CODE_REVIEW",
            "TEST",
            "INTEGRATE",
            "VERIFY",
            "DONE",
        ]

    def test_bug_phases_order(self) -> None:
        """Test that bug phases are in correct order."""
        assert BUG_PHASES == [
            "REPORTED",
            "INVESTIGATED",
            "FIXED",
            "REVIEWED",
            "TESTED",
            "MERGED",
            "DONE",
        ]

    def test_feature_transitions_complete(self) -> None:
        """Test that all feature phases have transitions defined."""
        for phase in FEATURE_PHASES:
            assert phase in FEATURE_TRANSITIONS

    def test_bug_transitions_complete(self) -> None:
        """Test that all bug phases have transitions defined."""
        for phase in BUG_PHASES:
            assert phase in BUG_TRANSITIONS


class TestGetInitialPhase:
    """Tests for get_initial_phase function."""

    def test_feature_initial_phase(self) -> None:
        """Test initial phase for features is SPEC."""
        assert get_initial_phase("feature") == "SPEC"

    def test_bug_initial_phase(self) -> None:
        """Test initial phase for bugs is REPORTED."""
        assert get_initial_phase("bug") == "REPORTED"

    def test_invalid_type_raises(self) -> None:
        """Test that invalid task type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid task type"):
            get_initial_phase("invalid")


class TestGetPhases:
    """Tests for get_phases function."""

    def test_get_feature_phases(self) -> None:
        """Test getting feature phases."""
        phases = get_phases("feature")
        assert phases == FEATURE_PHASES

    def test_get_bug_phases(self) -> None:
        """Test getting bug phases."""
        phases = get_phases("bug")
        assert phases == BUG_PHASES

    def test_invalid_type_raises(self) -> None:
        """Test that invalid task type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid task type"):
            get_phases("invalid")


class TestGetTransitions:
    """Tests for get_transitions function."""

    def test_get_feature_transitions(self) -> None:
        """Test getting feature transitions."""
        transitions = get_transitions("feature")
        assert transitions == FEATURE_TRANSITIONS

    def test_get_bug_transitions(self) -> None:
        """Test getting bug transitions."""
        transitions = get_transitions("bug")
        assert transitions == BUG_TRANSITIONS

    def test_invalid_type_raises(self) -> None:
        """Test that invalid task type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid task type"):
            get_transitions("invalid")


class TestIsValidTransition:
    """Tests for is_valid_transition function."""

    def test_valid_feature_transition(self) -> None:
        """Test valid feature transition."""
        assert is_valid_transition("feature", "SPEC", "DESIGN") is True
        assert is_valid_transition("feature", "IMPLEMENT", "CODE_REVIEW") is True

    def test_invalid_feature_transition(self) -> None:
        """Test invalid feature transition (skipping phases)."""
        assert is_valid_transition("feature", "SPEC", "IMPLEMENT") is False
        assert is_valid_transition("feature", "SPEC", "DONE") is False

    def test_valid_bug_transition(self) -> None:
        """Test valid bug transition."""
        assert is_valid_transition("bug", "REPORTED", "INVESTIGATED") is True
        assert is_valid_transition("bug", "FIXED", "REVIEWED") is True

    def test_invalid_bug_transition(self) -> None:
        """Test invalid bug transition."""
        assert is_valid_transition("bug", "REPORTED", "FIXED") is False
        assert is_valid_transition("bug", "REPORTED", "DONE") is False

    def test_no_transition_from_done(self) -> None:
        """Test that DONE has no valid transitions."""
        assert is_valid_transition("feature", "DONE", "SPEC") is False
        assert is_valid_transition("bug", "DONE", "REPORTED") is False


class TestGetNextPhases:
    """Tests for get_next_phases function."""

    def test_feature_next_phases(self) -> None:
        """Test getting next phases for features."""
        assert get_next_phases("feature", "SPEC") == ["DESIGN"]
        assert get_next_phases("feature", "IMPLEMENT") == ["CODE_REVIEW"]

    def test_bug_next_phases(self) -> None:
        """Test getting next phases for bugs."""
        assert get_next_phases("bug", "REPORTED") == ["INVESTIGATED"]
        assert get_next_phases("bug", "FIXED") == ["REVIEWED"]

    def test_done_has_no_next(self) -> None:
        """Test that DONE has no next phases."""
        assert get_next_phases("feature", "DONE") == []
        assert get_next_phases("bug", "DONE") == []


class TestTransitionName:
    """Tests for transition name functions."""

    def test_get_transition_name(self) -> None:
        """Test getting transition name."""
        assert get_transition_name("SPEC", "DESIGN") == "SPEC-DESIGN"
        assert get_transition_name("IMPLEMENT", "CODE_REVIEW") == "IMPLEMENT-CODE_REVIEW"

    def test_parse_transition(self) -> None:
        """Test parsing transition name."""
        assert parse_transition("SPEC-DESIGN") == ("SPEC", "DESIGN")
        assert parse_transition("IMPLEMENT-CODE_REVIEW") == ("IMPLEMENT", "CODE_REVIEW")

    def test_parse_invalid_transition(self) -> None:
        """Test parsing invalid transition raises error."""
        with pytest.raises(ValueError, match="Invalid transition format"):
            parse_transition("INVALID")
        with pytest.raises(ValueError, match="Invalid transition format"):
            parse_transition("A-B-C")
