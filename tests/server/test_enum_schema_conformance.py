"""Schema conformance tests for enum validation.

Verifies that:
1. Python Enum classes in observation/models.py match validation constants in enums.py
2. Validation constants match enum values declared in MCP tool definitions (JSON schemas)

This creates a complete chain: Python Enum <-> Validation Constants <-> JSON Schema

Reference: BUG-026 - Advertised enums drifted from actual validation.

Location: tests/server/test_enum_schema_conformance.py
"""

from typing import Any

import pytest

from clams.observation.models import Domain, OutcomeStatus, Strategy
from clams.server.tools import _get_all_tool_definitions
from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)

# =============================================================================
# Helper Functions
# =============================================================================


def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """Get the inputSchema for a tool by name.

    Args:
        tool_name: Name of the tool to find

    Returns:
        The inputSchema dict for the tool

    Raises:
        ValueError: If tool not found
    """
    tools = _get_all_tool_definitions()
    for tool in tools:
        if tool.name == tool_name:
            return tool.inputSchema
    raise ValueError(f"Tool '{tool_name}' not found in tool definitions")


def extract_enum_from_property(schema: dict[str, Any], property_name: str) -> list[str] | None:
    """Extract enum values from a top-level property.

    Args:
        schema: Tool inputSchema
        property_name: Name of the property

    Returns:
        List of enum values, or None if not found
    """
    props = schema.get("properties", {})
    prop = props.get(property_name, {})
    return prop.get("enum")


def extract_enum_from_nested_property(
    schema: dict[str, Any], parent_property: str, child_property: str
) -> list[str] | None:
    """Extract enum values from a nested object property.

    Args:
        schema: Tool inputSchema
        parent_property: Name of the parent object property
        child_property: Name of the child property containing the enum

    Returns:
        List of enum values, or None if not found
    """
    props = schema.get("properties", {})
    parent = props.get(parent_property, {})
    parent_props = parent.get("properties", {})
    child = parent_props.get(child_property, {})
    return child.get("enum")


# =============================================================================
# Python Enum to Validation Constants Tests
# =============================================================================


class TestPythonEnumMatchesValidationConstants:
    """Verify Python Enum classes match validation constants.

    This ensures that the Domain, Strategy, and OutcomeStatus enums defined
    in clams.observation.models match the validation constants in
    clams.server.tools.enums. If they drift, the server will accept values
    that the models cannot represent (or vice versa).
    """

    def test_domain_enum_matches_domains_constant(self) -> None:
        """Python Domain enum values should match DOMAINS validation constant."""
        enum_values = [d.value for d in Domain]
        assert enum_values == list(DOMAINS), (
            f"Domain enum/constant mismatch:\n"
            f"  Domain enum values: {enum_values}\n"
            f"  DOMAINS constant: {list(DOMAINS)}\n"
            f"  Missing in enum: {set(DOMAINS) - set(enum_values)}\n"
            f"  Extra in enum: {set(enum_values) - set(DOMAINS)}"
        )

    def test_strategy_enum_matches_strategies_constant(self) -> None:
        """Python Strategy enum values should match STRATEGIES validation constant."""
        enum_values = [s.value for s in Strategy]
        assert enum_values == list(STRATEGIES), (
            f"Strategy enum/constant mismatch:\n"
            f"  Strategy enum values: {enum_values}\n"
            f"  STRATEGIES constant: {list(STRATEGIES)}\n"
            f"  Missing in enum: {set(STRATEGIES) - set(enum_values)}\n"
            f"  Extra in enum: {set(enum_values) - set(STRATEGIES)}"
        )

    def test_outcome_status_enum_matches_outcome_status_values_constant(self) -> None:
        """Python OutcomeStatus enum values should match OUTCOME_STATUS_VALUES constant."""
        enum_values = [o.value for o in OutcomeStatus]
        assert enum_values == list(OUTCOME_STATUS_VALUES), (
            f"OutcomeStatus enum/constant mismatch:\n"
            f"  OutcomeStatus enum values: {enum_values}\n"
            f"  OUTCOME_STATUS_VALUES constant: {list(OUTCOME_STATUS_VALUES)}\n"
            f"  Missing in enum: {set(OUTCOME_STATUS_VALUES) - set(enum_values)}\n"
            f"  Extra in enum: {set(enum_values) - set(OUTCOME_STATUS_VALUES)}"
        )


# =============================================================================
# Domain Enum Tests (Validation Constants to JSON Schema)
# =============================================================================


class TestDomainEnumConformance:
    """Verify domain enum matches DOMAINS in all tools that use it."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "start_ghap",
            "list_ghap_entries",
            "search_experiences",
        ],
    )
    def test_domain_enum_matches(self, tool_name: str) -> None:
        """Tool's domain enum should match DOMAINS from enums.py."""
        schema = get_tool_schema(tool_name)
        enum = extract_enum_from_property(schema, "domain")

        assert enum is not None, f"{tool_name} should have domain enum"
        assert list(enum) == list(DOMAINS), (
            f"{tool_name} domain enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (DOMAINS): {list(DOMAINS)}"
        )


# =============================================================================
# Strategy Enum Tests
# =============================================================================


class TestStrategyEnumConformance:
    """Verify strategy enum matches STRATEGIES in all tools that use it."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "start_ghap",
            "update_ghap",
        ],
    )
    def test_strategy_enum_matches(self, tool_name: str) -> None:
        """Tool's strategy enum should match STRATEGIES from enums.py."""
        schema = get_tool_schema(tool_name)
        enum = extract_enum_from_property(schema, "strategy")

        assert enum is not None, f"{tool_name} should have strategy enum"
        assert list(enum) == list(STRATEGIES), (
            f"{tool_name} strategy enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (STRATEGIES): {list(STRATEGIES)}"
        )


# =============================================================================
# Outcome Status Enum Tests
# =============================================================================


class TestOutcomeStatusEnumConformance:
    """Verify outcome status enum matches OUTCOME_STATUS_VALUES."""

    def test_resolve_ghap_status_enum_matches(self) -> None:
        """resolve_ghap status enum should match OUTCOME_STATUS_VALUES."""
        schema = get_tool_schema("resolve_ghap")
        enum = extract_enum_from_property(schema, "status")

        assert enum is not None, "resolve_ghap should have status enum"
        assert list(enum) == list(OUTCOME_STATUS_VALUES), (
            f"resolve_ghap status enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (OUTCOME_STATUS_VALUES): {list(OUTCOME_STATUS_VALUES)}"
        )

    @pytest.mark.parametrize(
        "tool_name",
        [
            "list_ghap_entries",
            "search_experiences",
        ],
    )
    def test_outcome_enum_matches(self, tool_name: str) -> None:
        """Tool's outcome enum should match OUTCOME_STATUS_VALUES."""
        schema = get_tool_schema(tool_name)
        enum = extract_enum_from_property(schema, "outcome")

        assert enum is not None, f"{tool_name} should have outcome enum"
        assert list(enum) == list(OUTCOME_STATUS_VALUES), (
            f"{tool_name} outcome enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (OUTCOME_STATUS_VALUES): {list(OUTCOME_STATUS_VALUES)}"
        )


# =============================================================================
# Axis Enum Tests
# =============================================================================


class TestAxisEnumConformance:
    """Verify axis enum matches VALID_AXES in all tools that use it."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "get_clusters",
            "store_value",
            "list_values",
            "search_experiences",
        ],
    )
    def test_axis_enum_matches(self, tool_name: str) -> None:
        """Tool's axis enum should match VALID_AXES from enums.py."""
        schema = get_tool_schema(tool_name)
        enum = extract_enum_from_property(schema, "axis")

        assert enum is not None, f"{tool_name} should have axis enum"
        assert list(enum) == list(VALID_AXES), (
            f"{tool_name} axis enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (VALID_AXES): {list(VALID_AXES)}"
        )


# =============================================================================
# Root Cause Category Enum Tests
# =============================================================================


class TestRootCauseCategoryEnumConformance:
    """Verify root_cause.category enum matches ROOT_CAUSE_CATEGORIES."""

    def test_resolve_ghap_root_cause_category_enum_matches(self) -> None:
        """resolve_ghap root_cause.category should match ROOT_CAUSE_CATEGORIES."""
        schema = get_tool_schema("resolve_ghap")
        enum = extract_enum_from_nested_property(schema, "root_cause", "category")

        assert enum is not None, "resolve_ghap should have root_cause.category enum"
        assert list(enum) == list(ROOT_CAUSE_CATEGORIES), (
            f"resolve_ghap root_cause.category enum mismatch:\n"
            f"  Schema: {enum}\n"
            f"  Expected (ROOT_CAUSE_CATEGORIES): {list(ROOT_CAUSE_CATEGORIES)}"
        )


# =============================================================================
# Cluster ID Format Tests
# =============================================================================


class TestClusterIdFormat:
    """Verify get_cluster_members documents the axis prefix format.

    The cluster_id parameter follows format 'axis_label' (e.g., 'full_0').
    This test verifies the description documents this format correctly.
    """

    def test_get_cluster_members_documents_axis_prefix_format(self) -> None:
        """get_cluster_members cluster_id description should document axis format."""
        schema = get_tool_schema("get_cluster_members")
        props = schema.get("properties", {})
        cluster_id_prop = props.get("cluster_id", {})
        description = cluster_id_prop.get("description", "")

        # Verify description mentions the axis prefix format
        assert "axis" in description.lower(), (
            "get_cluster_members cluster_id should document axis prefix format.\n"
            f"  Got description: {description}"
        )
        # Verify description includes format example with underscore separator
        assert "_" in description, (
            "get_cluster_members cluster_id should include format example (e.g., 'full_0').\n"
            f"  Got description: {description}"
        )
