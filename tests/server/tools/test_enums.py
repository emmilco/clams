"""Tests for enum validation."""

import pytest

from clams.server.errors import ValidationError
from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
    validate_axis,
    validate_domain,
    validate_outcome_status,
    validate_root_cause_category,
    validate_strategy,
)


class TestDomains:
    """Tests for domain validation."""

    def test_valid_domains(self) -> None:
        """Test all valid domains pass validation."""
        for domain in DOMAINS:
            validate_domain(domain)  # Should not raise

    def test_invalid_domain_raises_error(self) -> None:
        """Test invalid domain raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid domain 'invalid'"):
            validate_domain("invalid")

    def test_error_message_includes_valid_options(self) -> None:
        """Test error message lists valid options."""
        with pytest.raises(ValidationError, match="debugging"):
            validate_domain("bad_domain")


class TestStrategies:
    """Tests for strategy validation."""

    def test_valid_strategies(self) -> None:
        """Test all valid strategies pass validation."""
        for strategy in STRATEGIES:
            validate_strategy(strategy)  # Should not raise

    def test_invalid_strategy_raises_error(self) -> None:
        """Test invalid strategy raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid strategy 'invalid'"):
            validate_strategy("invalid")

    def test_error_message_includes_valid_options(self) -> None:
        """Test error message lists valid options."""
        with pytest.raises(ValidationError, match="systematic-elimination"):
            validate_strategy("bad_strategy")


class TestAxes:
    """Tests for axis validation."""

    def test_valid_axes(self) -> None:
        """Test all valid axes pass validation."""
        for axis in VALID_AXES:
            validate_axis(axis)  # Should not raise

    def test_invalid_axis_raises_error(self) -> None:
        """Test invalid axis raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid axis 'invalid'"):
            validate_axis("invalid")

    def test_error_message_includes_valid_options(self) -> None:
        """Test error message lists valid options."""
        with pytest.raises(ValidationError, match="full"):
            validate_axis("bad_axis")

    def test_domain_is_not_a_valid_axis(self) -> None:
        """Test that domain is not a valid axis."""
        # Domain is metadata on experiences_full, not an axis
        with pytest.raises(ValidationError):
            validate_axis("debugging")


class TestOutcomeStatus:
    """Tests for outcome status validation."""

    def test_valid_outcome_statuses(self) -> None:
        """Test all valid outcome statuses pass validation."""
        for status in OUTCOME_STATUS_VALUES:
            validate_outcome_status(status)  # Should not raise

    def test_invalid_outcome_status_raises_error(self) -> None:
        """Test invalid outcome status raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid outcome status 'invalid'"):
            validate_outcome_status("invalid")

    def test_error_message_includes_valid_options(self) -> None:
        """Test error message lists valid options."""
        with pytest.raises(ValidationError, match="confirmed"):
            validate_outcome_status("bad_status")


class TestRootCauseCategories:
    """Tests for root cause category validation."""

    def test_valid_root_cause_categories(self) -> None:
        """Test all valid root cause categories pass validation."""
        for category in ROOT_CAUSE_CATEGORIES:
            validate_root_cause_category(category)  # Should not raise

    def test_invalid_root_cause_category_raises_error(self) -> None:
        """Test invalid root cause category raises ValidationError."""
        with pytest.raises(
            ValidationError, match="Invalid root_cause category 'invalid'"
        ):
            validate_root_cause_category("invalid")

    def test_error_message_includes_valid_options(self) -> None:
        """Test error message lists valid options."""
        with pytest.raises(ValidationError, match="wrong-assumption"):
            validate_root_cause_category("bad_category")
