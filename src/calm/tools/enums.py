"""Enum validation utilities for MCP tools."""

from calm.ghap.models import Domain, OutcomeStatus, Strategy

from .validation import ValidationError

# Valid domain values
VALID_DOMAINS = {d.value for d in Domain}

# Valid strategy values
VALID_STRATEGIES = {s.value for s in Strategy}

# Valid outcome status values
VALID_OUTCOME_STATUSES = {s.value for s in OutcomeStatus}

# Valid root cause categories
VALID_ROOT_CAUSE_CATEGORIES = {
    "wrong-assumption",
    "missing-knowledge",
    "oversight",
    "environment-issue",
    "misleading-symptom",
    "incomplete-fix",
    "wrong-scope",
    "test-isolation",
    "timing-issue",
}


def validate_domain(value: str) -> None:
    """Validate a domain value.

    Args:
        value: Domain string to validate

    Raises:
        ValidationError: If value is not a valid domain
    """
    if value not in VALID_DOMAINS:
        raise ValidationError(
            f"Invalid domain '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_DOMAINS))}"
        )


def validate_strategy(value: str) -> None:
    """Validate a strategy value.

    Args:
        value: Strategy string to validate

    Raises:
        ValidationError: If value is not a valid strategy
    """
    if value not in VALID_STRATEGIES:
        raise ValidationError(
            f"Invalid strategy '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_STRATEGIES))}"
        )


def validate_outcome_status(value: str) -> None:
    """Validate an outcome status value.

    Args:
        value: Outcome status string to validate

    Raises:
        ValidationError: If value is not a valid outcome status
    """
    if value not in VALID_OUTCOME_STATUSES:
        raise ValidationError(
            f"Invalid outcome status '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_OUTCOME_STATUSES))}"
        )


def validate_root_cause_category(value: str) -> None:
    """Validate a root cause category value.

    Args:
        value: Category string to validate

    Raises:
        ValidationError: If value is not a valid category
    """
    if value not in VALID_ROOT_CAUSE_CATEGORIES:
        raise ValidationError(
            f"Invalid root cause category '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_ROOT_CAUSE_CATEGORIES))}"
        )
