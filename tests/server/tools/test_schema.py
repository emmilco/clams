"""Tests for schema generation utilities."""

from collections.abc import Callable
from typing import Any

import pytest

from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)
from clams.server.tools.schema import (
    axis_schema,
    domain_schema,
    outcome_status_schema,
    root_cause_category_schema,
    root_cause_object_schema,
    strategy_schema,
)


class TestSchemaStructure:
    """Verify schema functions return valid JSON Schema properties."""

    @pytest.mark.parametrize(
        "schema_func",
        [
            domain_schema,
            strategy_schema,
            axis_schema,
            outcome_status_schema,
            root_cause_category_schema,
        ],
    )
    def test_returns_required_keys(
        self, schema_func: Callable[[], dict[str, Any]]
    ) -> None:
        """Schema should have type, description, and enum keys."""
        schema = schema_func()
        assert "type" in schema
        assert "description" in schema
        assert "enum" in schema

    @pytest.mark.parametrize(
        "schema_func",
        [
            domain_schema,
            strategy_schema,
            axis_schema,
            outcome_status_schema,
            root_cause_category_schema,
        ],
    )
    def test_type_is_string(
        self, schema_func: Callable[[], dict[str, Any]]
    ) -> None:
        """Schema type should be 'string' for all enum fields."""
        schema = schema_func()
        assert schema["type"] == "string"

    @pytest.mark.parametrize(
        "schema_func",
        [
            domain_schema,
            strategy_schema,
            axis_schema,
            outcome_status_schema,
            root_cause_category_schema,
        ],
    )
    def test_description_is_non_empty_string(
        self, schema_func: Callable[[], dict[str, Any]]
    ) -> None:
        """Schema description should be a non-empty string."""
        schema = schema_func()
        assert isinstance(schema["description"], str)
        assert len(schema["description"]) > 0

    @pytest.mark.parametrize(
        "schema_func",
        [
            domain_schema,
            strategy_schema,
            axis_schema,
            outcome_status_schema,
            root_cause_category_schema,
        ],
    )
    def test_enum_is_list(
        self, schema_func: Callable[[], dict[str, Any]]
    ) -> None:
        """Schema enum should be a list."""
        schema = schema_func()
        assert isinstance(schema["enum"], list)


class TestEnumValues:
    """Verify schema enum values match canonical enums."""

    def test_domain_schema_enum_matches_domains_list(self) -> None:
        """domain_schema enum should match DOMAINS."""
        schema = domain_schema()
        assert list(schema["enum"]) == list(DOMAINS)

    def test_strategy_schema_enum_matches_strategies_list(self) -> None:
        """strategy_schema enum should match STRATEGIES."""
        schema = strategy_schema()
        assert list(schema["enum"]) == list(STRATEGIES)

    def test_axis_schema_enum_matches_valid_axes_list(self) -> None:
        """axis_schema enum should match VALID_AXES."""
        schema = axis_schema()
        assert list(schema["enum"]) == list(VALID_AXES)

    def test_outcome_status_schema_enum_matches_outcome_status_values_list(
        self,
    ) -> None:
        """outcome_status_schema enum should match OUTCOME_STATUS_VALUES."""
        schema = outcome_status_schema()
        assert list(schema["enum"]) == list(OUTCOME_STATUS_VALUES)

    def test_root_cause_category_schema_enum_matches_categories_list(
        self,
    ) -> None:
        """root_cause_category_schema enum should match ROOT_CAUSE_CATEGORIES."""
        schema = root_cause_category_schema()
        assert list(schema["enum"]) == list(ROOT_CAUSE_CATEGORIES)


class TestSchemaParameters:
    """Test schema function parameters."""

    def test_axis_schema_without_default(self) -> None:
        """axis_schema without include_default should not have default key."""
        schema = axis_schema()
        assert "default" not in schema

    def test_axis_schema_with_default(self) -> None:
        """axis_schema with include_default=True should have default='full'."""
        schema = axis_schema(include_default=True)
        assert "default" in schema
        assert schema["default"] == "full"

    def test_axis_schema_include_default_false_explicit(self) -> None:
        """axis_schema with include_default=False should not have default key."""
        schema = axis_schema(include_default=False)
        assert "default" not in schema


class TestRootCauseObjectSchema:
    """Test nested object schema generation."""

    def test_root_cause_object_has_type_object(self) -> None:
        """root_cause_object_schema should have type 'object'."""
        schema = root_cause_object_schema()
        assert schema["type"] == "object"

    def test_root_cause_object_has_description(self) -> None:
        """root_cause_object_schema should have a description."""
        schema = root_cause_object_schema()
        assert "description" in schema
        assert isinstance(schema["description"], str)
        assert len(schema["description"]) > 0

    def test_root_cause_object_has_properties(self) -> None:
        """root_cause_object_schema should have properties dict."""
        schema = root_cause_object_schema()
        assert "properties" in schema
        assert "category" in schema["properties"]
        assert "description" in schema["properties"]

    def test_root_cause_object_category_uses_root_cause_category_schema(
        self,
    ) -> None:
        """root_cause.category should use root_cause_category_schema enum."""
        schema = root_cause_object_schema()
        category = schema["properties"]["category"]
        assert list(category["enum"]) == list(ROOT_CAUSE_CATEGORIES)

    def test_root_cause_object_description_is_string_type(self) -> None:
        """root_cause.description should be type string."""
        schema = root_cause_object_schema()
        description_prop = schema["properties"]["description"]
        assert description_prop["type"] == "string"


class TestImportSafety:
    """Verify schema module imports safely."""

    def test_import_has_no_side_effects(self) -> None:
        """Importing schema module should not cause side effects."""
        # If we got here, the import at module level succeeded
        # This test documents the expectation that imports are safe
        from clams.server.tools import schema

        assert hasattr(schema, "domain_schema")
        assert hasattr(schema, "strategy_schema")
        assert hasattr(schema, "axis_schema")
        assert hasattr(schema, "outcome_status_schema")
        assert hasattr(schema, "root_cause_category_schema")
        assert hasattr(schema, "root_cause_object_schema")

    def test_module_exports_all_expected_functions(self) -> None:
        """Module __all__ should include all expected functions."""
        from clams.server.tools import schema

        expected = [
            "axis_schema",
            "domain_schema",
            "outcome_status_schema",
            "root_cause_category_schema",
            "root_cause_object_schema",
            "strategy_schema",
        ]
        assert sorted(schema.__all__) == sorted(expected)


class TestSchemaImmutability:
    """Test that schema functions return independent dictionaries."""

    def test_domain_schema_returns_new_dict_each_call(self) -> None:
        """domain_schema should return a new dict on each call."""
        schema1 = domain_schema()
        schema2 = domain_schema()
        assert schema1 is not schema2

    def test_axis_schema_returns_new_dict_each_call(self) -> None:
        """axis_schema should return a new dict on each call."""
        schema1 = axis_schema()
        schema2 = axis_schema()
        assert schema1 is not schema2

    def test_root_cause_object_schema_returns_new_dict_each_call(self) -> None:
        """root_cause_object_schema should return a new dict on each call."""
        schema1 = root_cause_object_schema()
        schema2 = root_cause_object_schema()
        assert schema1 is not schema2

    def test_mutating_returned_schema_does_not_affect_future_calls(
        self,
    ) -> None:
        """Mutating a returned schema should not affect subsequent calls."""
        schema1 = domain_schema()
        original_type = schema1["type"]
        schema1["type"] = "mutated"

        schema2 = domain_schema()
        assert schema2["type"] == original_type
