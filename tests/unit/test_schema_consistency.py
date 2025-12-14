"""Schema Enum Consistency Tests.

R10-C: Verify JSON schema enum values match Python validation enum values.

This module tests that:
1. JSON schema enum values in tool definitions match Python validation enums
2. Schema does not advertise values that validation would reject
3. All enums are consistent: domain, strategy, category, outcome, axis, root_cause

Reference: BUG-026 - Advertised enums drifted from actual validation.
"""

from typing import Any

from clams.server.tools import _get_all_tool_definitions
from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)
from clams.server.tools.memory import VALID_CATEGORIES


def _get_tool_by_name(name: str) -> dict[str, Any]:
    """Get a tool definition by name.

    Args:
        name: Tool name to find

    Returns:
        Tool definition dict

    Raises:
        ValueError: If tool not found
    """
    tools = _get_all_tool_definitions()
    for tool in tools:
        if tool.name == name:
            return dict(tool.inputSchema)
    raise ValueError(f"Tool '{name}' not found in tool definitions")


def _extract_enum_values(schema: dict[str, Any], property_path: str) -> set[str]:
    """Extract enum values from a schema property.

    Args:
        schema: JSON schema dict
        property_path: Dot-separated path to property (e.g., "domain" or "root_cause.category")

    Returns:
        Set of enum values, or empty set if no enum defined

    Raises:
        KeyError: If property path not found
    """
    parts = property_path.split(".")
    current = schema.get("properties", {})

    for part in parts[:-1]:
        current = current.get(part, {}).get("properties", {})

    prop = current.get(parts[-1], {})
    return set(prop.get("enum", []))


class TestDomainEnumConsistency:
    """Test domain enum consistency across schema and validation."""

    def test_start_ghap_domain_enum_matches_validation(self) -> None:
        """JSON schema domain values in start_ghap must match validation enum."""
        schema = _get_tool_by_name("start_ghap")
        schema_values = _extract_enum_values(schema, "domain")
        enum_values = set(DOMAINS)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for start_ghap domain.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_list_ghap_entries_domain_filter_matches_validation(self) -> None:
        """JSON schema domain filter in list_ghap_entries must match validation enum."""
        schema = _get_tool_by_name("list_ghap_entries")
        schema_values = _extract_enum_values(schema, "domain")
        enum_values = set(DOMAINS)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for list_ghap_entries domain.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_search_experiences_domain_filter_matches_validation(self) -> None:
        """JSON schema domain filter in search_experiences must match validation enum."""
        schema = _get_tool_by_name("search_experiences")
        schema_values = _extract_enum_values(schema, "domain")
        enum_values = set(DOMAINS)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for search_experiences domain.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestStrategyEnumConsistency:
    """Test strategy enum consistency across schema and validation."""

    def test_start_ghap_strategy_enum_matches_validation(self) -> None:
        """JSON schema strategy values in start_ghap must match validation enum."""
        schema = _get_tool_by_name("start_ghap")
        schema_values = _extract_enum_values(schema, "strategy")
        enum_values = set(STRATEGIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for start_ghap strategy.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_update_ghap_strategy_enum_matches_validation(self) -> None:
        """JSON schema strategy values in update_ghap must match validation enum."""
        schema = _get_tool_by_name("update_ghap")
        schema_values = _extract_enum_values(schema, "strategy")
        enum_values = set(STRATEGIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for update_ghap strategy.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestMemoryCategoryEnumConsistency:
    """Test memory category enum consistency across schema and validation."""

    def test_store_memory_category_enum_matches_validation(self) -> None:
        """JSON schema category values in store_memory must match validation enum."""
        schema = _get_tool_by_name("store_memory")
        schema_values = _extract_enum_values(schema, "category")
        enum_values = set(VALID_CATEGORIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for store_memory category.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_retrieve_memories_category_enum_matches_validation(self) -> None:
        """JSON schema category values in retrieve_memories must match validation enum."""
        schema = _get_tool_by_name("retrieve_memories")
        schema_values = _extract_enum_values(schema, "category")
        enum_values = set(VALID_CATEGORIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for retrieve_memories category.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_list_memories_category_enum_matches_validation(self) -> None:
        """JSON schema category values in list_memories must match validation enum."""
        schema = _get_tool_by_name("list_memories")
        schema_values = _extract_enum_values(schema, "category")
        enum_values = set(VALID_CATEGORIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for list_memories category.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestOutcomeStatusEnumConsistency:
    """Test outcome status enum consistency across schema and validation."""

    def test_resolve_ghap_status_enum_matches_validation(self) -> None:
        """JSON schema status values in resolve_ghap must match validation enum."""
        schema = _get_tool_by_name("resolve_ghap")
        schema_values = _extract_enum_values(schema, "status")
        enum_values = set(OUTCOME_STATUS_VALUES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for resolve_ghap status.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_list_ghap_entries_outcome_enum_matches_validation(self) -> None:
        """JSON schema outcome values in list_ghap_entries must match validation enum."""
        schema = _get_tool_by_name("list_ghap_entries")
        schema_values = _extract_enum_values(schema, "outcome")
        enum_values = set(OUTCOME_STATUS_VALUES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for list_ghap_entries outcome.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_search_experiences_outcome_enum_matches_validation(self) -> None:
        """JSON schema outcome values in search_experiences must match validation enum."""
        schema = _get_tool_by_name("search_experiences")
        schema_values = _extract_enum_values(schema, "outcome")
        enum_values = set(OUTCOME_STATUS_VALUES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for search_experiences outcome.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestAxisEnumConsistency:
    """Test axis enum consistency across schema and validation."""

    def test_get_clusters_axis_enum_matches_validation(self) -> None:
        """JSON schema axis values in get_clusters must match validation enum."""
        schema = _get_tool_by_name("get_clusters")
        schema_values = _extract_enum_values(schema, "axis")
        enum_values = set(VALID_AXES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for get_clusters axis.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_store_value_axis_enum_matches_validation(self) -> None:
        """JSON schema axis values in store_value must match validation enum."""
        schema = _get_tool_by_name("store_value")
        schema_values = _extract_enum_values(schema, "axis")
        enum_values = set(VALID_AXES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for store_value axis.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_list_values_axis_enum_matches_validation(self) -> None:
        """JSON schema axis values in list_values must match validation enum."""
        schema = _get_tool_by_name("list_values")
        schema_values = _extract_enum_values(schema, "axis")
        enum_values = set(VALID_AXES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for list_values axis.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )

    def test_search_experiences_axis_enum_matches_validation(self) -> None:
        """JSON schema axis values in search_experiences must match validation enum."""
        schema = _get_tool_by_name("search_experiences")
        schema_values = _extract_enum_values(schema, "axis")
        enum_values = set(VALID_AXES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for search_experiences axis.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestRootCauseCategoryEnumConsistency:
    """Test root cause category enum consistency across schema and validation."""

    def test_resolve_ghap_root_cause_category_enum_matches_validation(self) -> None:
        """JSON schema root_cause.category values in resolve_ghap must match validation enum."""
        schema = _get_tool_by_name("resolve_ghap")
        # root_cause is a nested object with properties including category
        root_cause_prop = schema.get("properties", {}).get("root_cause", {})
        category_prop = root_cause_prop.get("properties", {}).get("category", {})
        schema_values = set(category_prop.get("enum", []))
        enum_values = set(ROOT_CAUSE_CATEGORIES)

        assert schema_values == enum_values, (
            f"Schema/enum mismatch for resolve_ghap root_cause.category.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Python enum values: {sorted(enum_values)}\n"
            f"Missing in schema: {enum_values - schema_values}\n"
            f"Extra in schema: {schema_values - enum_values}"
        )


class TestContextTypesEnumConsistency:
    """Test context_types enum consistency in assemble_context."""

    def test_assemble_context_context_types_enum(self) -> None:
        """JSON schema context_types values in assemble_context are valid."""
        schema = _get_tool_by_name("assemble_context")
        items_schema = schema.get("properties", {}).get("context_types", {}).get("items", {})
        schema_values = set(items_schema.get("enum", []))
        # context_types allows "values" and "experiences"
        expected_values = {"values", "experiences"}

        assert schema_values == expected_values, (
            f"Schema/enum mismatch for assemble_context context_types.\n"
            f"Schema values: {sorted(schema_values)}\n"
            f"Expected values: {sorted(expected_values)}"
        )


class TestAllEnumsHaveConsistencyTests:
    """Meta-test to ensure all tools with enums have consistency coverage."""

    def test_all_enum_properties_covered(self) -> None:
        """Verify all tool enum properties have consistency tests.

        This test scans all tool definitions and identifies properties with
        enum constraints, then verifies they're covered by consistency tests.
        """
        tools = _get_all_tool_definitions()
        enum_locations: list[tuple[str, str]] = []

        for tool in tools:
            schema = tool.inputSchema
            properties = schema.get("properties", {})

            for prop_name, prop_def in properties.items():
                # Check for direct enum
                if "enum" in prop_def:
                    enum_locations.append((tool.name, prop_name))

                # Check for nested enums (e.g., root_cause.category)
                if prop_def.get("type") == "object" and "properties" in prop_def:
                    for nested_name, nested_def in prop_def["properties"].items():
                        if "enum" in nested_def:
                            enum_locations.append((tool.name, f"{prop_name}.{nested_name}"))

                # Check for array items with enum
                if prop_def.get("type") == "array" and "items" in prop_def:
                    items = prop_def["items"]
                    if "enum" in items:
                        enum_locations.append((tool.name, f"{prop_name}[items]"))

        # Known enum locations that should have consistency tests
        expected_covered = {
            # Domain enums
            ("start_ghap", "domain"),
            ("list_ghap_entries", "domain"),
            ("search_experiences", "domain"),
            # Strategy enums
            ("start_ghap", "strategy"),
            ("update_ghap", "strategy"),
            # Category enums (memory)
            ("store_memory", "category"),
            ("retrieve_memories", "category"),
            ("list_memories", "category"),
            # Outcome/status enums
            ("resolve_ghap", "status"),
            ("list_ghap_entries", "outcome"),
            ("search_experiences", "outcome"),
            # Axis enums
            ("get_clusters", "axis"),
            ("store_value", "axis"),
            ("list_values", "axis"),
            ("search_experiences", "axis"),
            # Root cause category
            ("resolve_ghap", "root_cause.category"),
            # Context types
            ("assemble_context", "context_types[items]"),
        }

        # Check all found enums are covered
        found_set = set(enum_locations)
        uncovered = found_set - expected_covered

        assert not uncovered, (
            f"Found enum properties without consistency tests:\n"
            f"{sorted(uncovered)}\n\n"
            f"Please add consistency tests for these enums."
        )
