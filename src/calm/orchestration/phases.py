"""Phase definitions and transition validation for CALM orchestration.

This module defines the phase models for features and bugs,
and provides validation for phase transitions.
"""

from typing import Literal

# Feature phase type
FeaturePhase = Literal[
    "SPEC", "DESIGN", "IMPLEMENT", "CODE_REVIEW", "TEST", "INTEGRATE", "VERIFY", "DONE"
]

# Bug phase type
BugPhase = Literal[
    "REPORTED", "INVESTIGATED", "FIXED", "REVIEWED", "TESTED", "MERGED", "DONE"
]

# Task type
TaskType = Literal["feature", "bug"]

# Feature phases in order
FEATURE_PHASES: list[str] = [
    "SPEC",
    "DESIGN",
    "IMPLEMENT",
    "CODE_REVIEW",
    "TEST",
    "INTEGRATE",
    "VERIFY",
    "DONE",
]

# Bug phases in order
BUG_PHASES: list[str] = [
    "REPORTED",
    "INVESTIGATED",
    "FIXED",
    "REVIEWED",
    "TESTED",
    "MERGED",
    "DONE",
]

# Valid feature transitions (from -> to)
FEATURE_TRANSITIONS: dict[str, list[str]] = {
    "SPEC": ["DESIGN"],
    "DESIGN": ["IMPLEMENT"],
    "IMPLEMENT": ["CODE_REVIEW"],
    "CODE_REVIEW": ["TEST"],
    "TEST": ["INTEGRATE"],
    "INTEGRATE": ["VERIFY"],
    "VERIFY": ["DONE"],
    "DONE": [],
}

# Valid bug transitions (from -> to)
BUG_TRANSITIONS: dict[str, list[str]] = {
    "REPORTED": ["INVESTIGATED"],
    "INVESTIGATED": ["FIXED"],
    "FIXED": ["REVIEWED"],
    "REVIEWED": ["TESTED"],
    "TESTED": ["MERGED"],
    "MERGED": ["DONE"],
    "DONE": [],
}


def get_initial_phase(task_type: str) -> str:
    """Get the initial phase for a task type.

    Args:
        task_type: Either 'feature' or 'bug'

    Returns:
        The initial phase for the task type

    Raises:
        ValueError: If task_type is invalid
    """
    if task_type == "feature":
        return "SPEC"
    elif task_type == "bug":
        return "REPORTED"
    else:
        raise ValueError(f"Invalid task type: {task_type}")


def get_phases(task_type: str) -> list[str]:
    """Get the phases for a task type.

    Args:
        task_type: Either 'feature' or 'bug'

    Returns:
        List of phases for the task type

    Raises:
        ValueError: If task_type is invalid
    """
    if task_type == "feature":
        return FEATURE_PHASES
    elif task_type == "bug":
        return BUG_PHASES
    else:
        raise ValueError(f"Invalid task type: {task_type}")


def get_transitions(task_type: str) -> dict[str, list[str]]:
    """Get the valid transitions for a task type.

    Args:
        task_type: Either 'feature' or 'bug'

    Returns:
        Dict of valid transitions for the task type

    Raises:
        ValueError: If task_type is invalid
    """
    if task_type == "feature":
        return FEATURE_TRANSITIONS
    elif task_type == "bug":
        return BUG_TRANSITIONS
    else:
        raise ValueError(f"Invalid task type: {task_type}")


def is_valid_transition(task_type: str, from_phase: str, to_phase: str) -> bool:
    """Check if a phase transition is valid.

    Args:
        task_type: Either 'feature' or 'bug'
        from_phase: Current phase
        to_phase: Target phase

    Returns:
        True if the transition is valid, False otherwise
    """
    transitions = get_transitions(task_type)
    valid_targets = transitions.get(from_phase, [])
    return to_phase in valid_targets


def get_next_phases(task_type: str, current_phase: str) -> list[str]:
    """Get the valid next phases from a current phase.

    Args:
        task_type: Either 'feature' or 'bug'
        current_phase: Current phase

    Returns:
        List of valid next phases
    """
    transitions = get_transitions(task_type)
    return transitions.get(current_phase, [])


def get_transition_name(from_phase: str, to_phase: str) -> str:
    """Get the transition name for a phase transition.

    Args:
        from_phase: Starting phase
        to_phase: Target phase

    Returns:
        Transition name in format "FROM-TO"
    """
    return f"{from_phase}-{to_phase}"


def parse_transition(transition: str) -> tuple[str, str]:
    """Parse a transition name into from and to phases.

    Args:
        transition: Transition name in format "FROM-TO"

    Returns:
        Tuple of (from_phase, to_phase)

    Raises:
        ValueError: If transition format is invalid
    """
    parts = transition.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid transition format: {transition}")
    return parts[0], parts[1]
