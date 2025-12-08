"""Domain and strategy enums with validation helpers."""

from clams.server.tools.errors import ValidationError

# Domain values
DOMAINS = [
    "debugging",
    "refactoring",
    "feature",
    "testing",
    "configuration",
    "documentation",
    "performance",
    "security",
    "integration",
]

# Strategy values
STRATEGIES = [
    "systematic-elimination",
    "trial-and-error",
    "research-first",
    "divide-and-conquer",
    "root-cause-analysis",
    "copy-from-similar",
    "check-assumptions",
    "read-the-error",
    "ask-user",
]

# Root cause categories
ROOT_CAUSE_CATEGORIES = [
    "wrong-assumption",
    "missing-knowledge",
    "oversight",
    "environment-issue",
    "misleading-symptom",
    "incomplete-fix",
    "wrong-scope",
    "test-isolation",
    "timing-issue",
]

# Experience axes (note: domain is NOT an axis, it's metadata on experiences_full)
VALID_AXES = ["full", "strategy", "surprise", "root_cause"]

# Outcome status values
OUTCOME_STATUS_VALUES = ["confirmed", "falsified", "abandoned"]


def validate_domain(domain: str) -> None:
    """Validate domain enum value.

    Args:
        domain: Domain value to validate

    Raises:
        ValidationError: If domain is invalid
    """
    if domain not in DOMAINS:
        raise ValidationError(
            f"Invalid domain '{domain}'. Valid options: {', '.join(DOMAINS)}"
        )


def validate_strategy(strategy: str) -> None:
    """Validate strategy enum value.

    Args:
        strategy: Strategy value to validate

    Raises:
        ValidationError: If strategy is invalid
    """
    if strategy not in STRATEGIES:
        raise ValidationError(
            f"Invalid strategy '{strategy}'. Valid options: {', '.join(STRATEGIES)}"
        )


def validate_axis(axis: str) -> None:
    """Validate clustering axis value.

    Args:
        axis: Axis value to validate

    Raises:
        ValidationError: If axis is invalid
    """
    if axis not in VALID_AXES:
        raise ValidationError(
            f"Invalid axis '{axis}'. Valid options: {', '.join(VALID_AXES)}"
        )


def validate_outcome_status(status: str) -> None:
    """Validate outcome status value.

    Args:
        status: Status value to validate

    Raises:
        ValidationError: If status is invalid
    """
    if status not in OUTCOME_STATUS_VALUES:
        raise ValidationError(
            f"Invalid outcome status '{status}'. "
            f"Valid options: {', '.join(OUTCOME_STATUS_VALUES)}"
        )


def validate_root_cause_category(category: str) -> None:
    """Validate root cause category value.

    Args:
        category: Category value to validate

    Raises:
        ValidationError: If category is invalid
    """
    if category not in ROOT_CAUSE_CATEGORIES:
        raise ValidationError(
            f"Invalid root_cause category '{category}'. "
            f"Valid options: {', '.join(ROOT_CAUSE_CATEGORIES)}"
        )
