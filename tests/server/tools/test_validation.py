"""Unit tests for validation helper functions.

Tests cover all helper functions scattered across calm.tools modules:
- validate_context_types (calm.tools.context)
- validate_importance_range (calm.tools.validation)
- validate_tags (calm.tools.validation)
- validate_uuid (calm.tools.validation)
- validate_language (calm.tools.code)
- validate_project_id (calm.tools.code)
- validate_limit_range (calm.tools.context)
- validate_text_length (calm.tools.ghap)
- validate_query_string (calm.tools.validation)
"""

import pytest

from calm.tools.code import (
    SUPPORTED_LANGUAGES,
    validate_language,
    validate_project_id,
)
from calm.tools.context import (
    validate_context_types,
    validate_limit_range,
)
from calm.tools.git import validate_author_name
from calm.tools.session import validate_frequency
from calm.tools.validation import (
    ValidationError,
    validate_importance_range,
    validate_query_string,
    validate_tags,
    validate_uuid,
)


class TestValidateContextTypes:
    """Tests for validate_context_types function."""

    def test_valid_single_type_values(self) -> None:
        """Single valid type 'values' should pass."""
        validate_context_types(["values"])  # Should not raise

    def test_valid_single_type_experiences(self) -> None:
        """Single valid type 'experiences' should pass."""
        validate_context_types(["experiences"])  # Should not raise

    def test_valid_both_types(self) -> None:
        """Both valid types should pass."""
        validate_context_types(["values", "experiences"])  # Should not raise

    def test_empty_list_allowed(self) -> None:
        """Empty list is allowed (no invalid types)."""
        validate_context_types([])  # Should not raise

    def test_invalid_type_raises(self) -> None:
        """Invalid context type should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid context types"):
            validate_context_types(["invalid"])

    def test_invalid_type_lists_valid_options(self) -> None:
        """Error message should list valid options."""
        with pytest.raises(ValidationError) as exc_info:
            validate_context_types(["wrong"])
        assert "values" in str(exc_info.value)
        assert "experiences" in str(exc_info.value)

    def test_mixed_valid_and_invalid(self) -> None:
        """Mix of valid and invalid types should raise for invalid ones."""
        with pytest.raises(ValidationError) as exc_info:
            validate_context_types(["values", "invalid", "experiences"])
        assert "invalid" in str(exc_info.value)


class TestValidateImportanceRange:
    """Tests for validate_importance_range function."""

    def test_valid_at_lower_boundary(self) -> None:
        """Importance 0.0 should pass."""
        validate_importance_range(0.0)  # Should not raise

    def test_valid_at_upper_boundary(self) -> None:
        """Importance 1.0 should pass."""
        validate_importance_range(1.0)  # Should not raise

    def test_valid_middle_value(self) -> None:
        """Importance 0.5 should pass."""
        validate_importance_range(0.5)  # Should not raise

    def test_below_range_raises(self) -> None:
        """Importance -0.1 should raise ValidationError."""
        with pytest.raises(ValidationError, match="out of range"):
            validate_importance_range(-0.1)

    def test_above_range_raises(self) -> None:
        """Importance 1.1 should raise ValidationError."""
        with pytest.raises(ValidationError, match="out of range"):
            validate_importance_range(1.1)

    def test_custom_param_name_in_error(self) -> None:
        """Custom parameter name should appear in error message."""
        with pytest.raises(ValidationError) as exc_info:
            validate_importance_range(1.5, "min_importance")
        assert "min_importance" in str(exc_info.value)


class TestValidateTags:
    """Tests for validate_tags function."""

    def test_none_allowed(self) -> None:
        """None tags should pass."""
        validate_tags(None)  # Should not raise

    def test_empty_list_allowed(self) -> None:
        """Empty list should pass."""
        validate_tags([])  # Should not raise

    def test_valid_tags(self) -> None:
        """Valid tags should pass."""
        validate_tags(["tag1", "tag2", "tag3"])  # Should not raise

    def test_tags_at_max_count(self) -> None:
        """Exactly 20 tags should pass."""
        validate_tags(["tag"] * 20)  # Should not raise

    def test_too_many_tags_raises(self) -> None:
        """More than 20 tags should raise ValidationError."""
        with pytest.raises(ValidationError, match="Too many tags"):
            validate_tags(["tag"] * 25)

    def test_too_many_tags_shows_count(self) -> None:
        """Error message should show actual count."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tags(["tag"] * 25)
        assert "25" in str(exc_info.value)
        assert "20" in str(exc_info.value)

    def test_tag_too_long_raises(self) -> None:
        """Tag longer than 50 chars should raise ValidationError."""
        with pytest.raises(ValidationError, match="too long"):
            validate_tags(["x" * 60])

    def test_custom_limits(self) -> None:
        """Custom max_count and max_length should be respected."""
        # Custom max_count=5
        with pytest.raises(ValidationError, match="Too many tags"):
            validate_tags(["tag"] * 10, max_count=5)

        # Custom max_length=10
        with pytest.raises(ValidationError, match="too long"):
            validate_tags(["x" * 20], max_length=10)


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_valid_uuid_v4(self) -> None:
        """Valid UUID v4 should pass."""
        validate_uuid("12345678-1234-5678-1234-567812345678")  # Should not raise

    def test_valid_uuid_lowercase(self) -> None:
        """Lowercase UUID should pass."""
        validate_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")  # Should not raise

    def test_valid_uuid_uppercase(self) -> None:
        """Uppercase UUID should pass."""
        validate_uuid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")  # Should not raise

    def test_invalid_uuid_raises(self) -> None:
        """Invalid UUID string should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("not-a-uuid")

    def test_invalid_uuid_shows_value(self) -> None:
        """Error message should show the invalid value."""
        with pytest.raises(ValidationError) as exc_info:
            validate_uuid("bad-id")
        assert "bad-id" in str(exc_info.value)

    def test_custom_param_name_in_error(self) -> None:
        """Custom parameter name should appear in error message."""
        with pytest.raises(ValidationError) as exc_info:
            validate_uuid("invalid", "memory_id")
        assert "memory_id" in str(exc_info.value)

    def test_empty_string_raises(self) -> None:
        """Empty string should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("")


class TestValidateLanguage:
    """Tests for validate_language function."""

    def test_none_allowed(self) -> None:
        """None language should pass."""
        validate_language(None)  # Should not raise

    def test_valid_language_lowercase(self) -> None:
        """Lowercase valid language should pass."""
        validate_language("python")  # Should not raise

    def test_all_supported_languages(self) -> None:
        """All supported languages should pass."""
        for lang in SUPPORTED_LANGUAGES:
            validate_language(lang)  # Should not raise

    def test_invalid_language_raises(self) -> None:
        """Unsupported language should raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsupported language"):
            validate_language("brainfuck")

    def test_invalid_language_lists_supported(self) -> None:
        """Error message should list supported languages."""
        with pytest.raises(ValidationError) as exc_info:
            validate_language("invalid")
        assert "python" in str(exc_info.value)
        assert "typescript" in str(exc_info.value)


class TestValidateProjectId:
    """Tests for validate_project_id function."""

    def test_valid_alphanumeric(self) -> None:
        """Alphanumeric project ID should pass."""
        validate_project_id("myproject123")  # Should not raise

    def test_valid_with_dashes(self) -> None:
        """Project ID with dashes should pass."""
        validate_project_id("my-project")  # Should not raise

    def test_valid_with_underscores(self) -> None:
        """Project ID with underscores should pass."""
        validate_project_id("my_project")  # Should not raise

    def test_valid_mixed(self) -> None:
        """Project ID with mixed characters should pass."""
        validate_project_id("My-Project_123")  # Should not raise

    def test_valid_at_max_length(self) -> None:
        """Project ID at exactly 100 chars should pass."""
        validate_project_id("x" * 100)  # Should not raise

    def test_empty_raises(self) -> None:
        """Empty project ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_project_id("")

    def test_too_long_raises(self) -> None:
        """Project ID over 100 chars should raise ValidationError."""
        with pytest.raises(ValidationError, match="too long"):
            validate_project_id("x" * 101)

    def test_spaces_raises(self) -> None:
        """Project ID with spaces should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            validate_project_id("has spaces")

    def test_special_chars_raises(self) -> None:
        """Project ID with special characters should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            validate_project_id("has@special!")

    def test_starts_with_dash_raises(self) -> None:
        """Project ID starting with dash should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            validate_project_id("-starts-with-dash")

    def test_starts_with_underscore_raises(self) -> None:
        """Project ID starting with underscore should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            validate_project_id("_starts_with_underscore")


class TestValidateLimitRange:
    """Tests for validate_limit_range function."""

    def test_valid_at_min(self) -> None:
        """Value at minimum should pass."""
        validate_limit_range(1, min_val=1, max_val=100)  # Should not raise

    def test_valid_at_max(self) -> None:
        """Value at maximum should pass."""
        validate_limit_range(100, min_val=1, max_val=100)  # Should not raise

    def test_valid_middle(self) -> None:
        """Value in middle should pass."""
        validate_limit_range(50, min_val=1, max_val=100)  # Should not raise

    def test_below_min_raises(self) -> None:
        """Value below minimum should raise ValidationError."""
        with pytest.raises(ValidationError, match="out of range"):
            validate_limit_range(0, min_val=1, max_val=100)

    def test_above_max_raises(self) -> None:
        """Value above maximum should raise ValidationError."""
        with pytest.raises(ValidationError, match="out of range"):
            validate_limit_range(101, min_val=1, max_val=100)

    def test_custom_param_name_in_error(self) -> None:
        """Custom parameter name should appear in error message."""
        with pytest.raises(ValidationError) as exc_info:
            validate_limit_range(0, min_val=1, max_val=100, param_name="max_tokens")
        assert "Max_tokens" in str(exc_info.value)

    def test_error_shows_range(self) -> None:
        """Error message should show the valid range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_limit_range(0, min_val=1, max_val=50)
        assert "1" in str(exc_info.value)
        assert "50" in str(exc_info.value)


class TestValidateQueryString:
    """Tests for validate_query_string function."""

    def test_valid_short_query(self) -> None:
        """Short query should pass."""
        validate_query_string("test query")  # Should not raise

    def test_valid_at_max_length(self) -> None:
        """Query at exactly max length should pass."""
        validate_query_string("x" * 10_000)  # Should not raise

    def test_empty_query_allowed(self) -> None:
        """Empty query should pass (empty handling is tool's job)."""
        validate_query_string("")  # Should not raise

    def test_whitespace_only_allowed(self) -> None:
        """Whitespace-only query should pass (empty handling is tool's job)."""
        validate_query_string("   ")  # Should not raise

    def test_too_long_raises(self) -> None:
        """Query exceeding max length should raise ValidationError."""
        with pytest.raises(ValidationError, match="too long"):
            validate_query_string("x" * 10_001)

    def test_too_long_shows_length(self) -> None:
        """Error message should show actual length."""
        with pytest.raises(ValidationError) as exc_info:
            validate_query_string("x" * 10_001)
        assert "10001" in str(exc_info.value)
        assert "10000" in str(exc_info.value)

    def test_custom_max_length(self) -> None:
        """Custom max_length should be respected."""
        # Should pass at custom max
        validate_query_string("x" * 500, max_length=500)
        # Should fail above custom max
        with pytest.raises(ValidationError, match="too long"):
            validate_query_string("x" * 501, max_length=500)

    def test_custom_param_name_in_error(self) -> None:
        """Custom parameter name should appear in error message."""
        with pytest.raises(ValidationError) as exc_info:
            validate_query_string("x" * 100, max_length=50, field_name="search_query")
        assert "search_query" in str(exc_info.value)


class TestValidateFrequency:
    """Tests for validate_frequency function."""

    def test_valid_default_range(self) -> None:
        """Value in default range should pass."""
        validate_frequency(10)  # Should not raise
        validate_frequency(1)  # Should not raise
        validate_frequency(1000)  # Should not raise

    def test_valid_middle_value(self) -> None:
        """Middle value should pass."""
        validate_frequency(500)  # Should not raise

    def test_zero_raises(self) -> None:
        """Zero should raise ValidationError."""
        with pytest.raises(ValidationError):
            validate_frequency(0)

    def test_negative_raises(self) -> None:
        """Negative value should raise ValidationError."""
        with pytest.raises(ValidationError):
            validate_frequency(-1)

    def test_too_large_raises(self) -> None:
        """Value above max should raise ValidationError."""
        with pytest.raises(ValidationError):
            validate_frequency(1001)


class TestValidateAuthorName:
    """Tests for validate_author_name function."""

    def test_none_allowed(self) -> None:
        """None should pass."""
        validate_author_name(None)  # Should not raise

    def test_valid_author(self) -> None:
        """Valid author name should pass."""
        validate_author_name("John Doe")  # Should not raise

    def test_valid_at_max_length(self) -> None:
        """Author name at max length should pass."""
        validate_author_name("x" * 200)  # Should not raise

    def test_empty_string_allowed(self) -> None:
        """Empty string is allowed (tool decides behavior)."""
        validate_author_name("")  # Should not raise

    def test_too_long_raises(self) -> None:
        """Author name exceeding max length should raise ValidationError."""
        with pytest.raises(ValidationError, match="too long"):
            validate_author_name("x" * 201)

    def test_too_long_shows_length(self) -> None:
        """Error message should show actual length."""
        with pytest.raises(ValidationError) as exc_info:
            validate_author_name("x" * 250)
        assert "250" in str(exc_info.value)
        assert "200" in str(exc_info.value)

    def test_custom_max_length(self) -> None:
        """Custom max_length should be respected."""
        # Should pass at custom max
        validate_author_name("x" * 50, max_length=50)
        # Should fail above custom max
        with pytest.raises(ValidationError, match="too long"):
            validate_author_name("x" * 51, max_length=50)
