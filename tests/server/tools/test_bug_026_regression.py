"""Regression test for BUG-026: JSON schema enum values must match validation enums."""

from clams.server.tools import _get_all_tool_definitions
from clams.server.tools.enums import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)


def _get_tool_by_name(name: str) -> dict:
    """Get tool definition by name."""
    tools = _get_all_tool_definitions()
    for tool in tools:
        if tool.name == name:
            return tool.inputSchema
    raise ValueError(f"Tool '{name}' not found")


def _extract_enum_from_schema(schema: dict, *path: str) -> list | None:
    """Extract enum array from nested schema path."""
    current = schema
    for key in path:
        if key == "properties" and "properties" in current:
            current = current["properties"]
        elif key in current:
            current = current[key]
        else:
            return None
    return current.get("enum")


class TestDomainEnumConsistency:
    """Verify domain enum is consistent across schemas and validation."""

    def test_start_ghap_domain_matches_enums(self) -> None:
        """BUG-026: start_ghap domain enum should match DOMAINS."""
        schema = _get_tool_by_name("start_ghap")
        enum = _extract_enum_from_schema(schema, "properties", "domain")
        assert enum == DOMAINS, f"start_ghap domain enum mismatch: {enum} != {DOMAINS}"

    def test_list_ghap_entries_domain_matches_enums(self) -> None:
        """BUG-026: list_ghap_entries domain enum should match DOMAINS."""
        schema = _get_tool_by_name("list_ghap_entries")
        enum = _extract_enum_from_schema(schema, "properties", "domain")
        assert enum == DOMAINS, "list_ghap_entries domain enum mismatch"

    def test_search_experiences_domain_matches_enums(self) -> None:
        """BUG-026: search_experiences domain enum should match DOMAINS."""
        schema = _get_tool_by_name("search_experiences")
        enum = _extract_enum_from_schema(schema, "properties", "domain")
        assert enum == DOMAINS, "search_experiences domain enum mismatch"


class TestStrategyEnumConsistency:
    """Verify strategy enum is consistent across schemas and validation."""

    def test_start_ghap_strategy_matches_enums(self) -> None:
        """BUG-026: start_ghap strategy enum should match STRATEGIES."""
        schema = _get_tool_by_name("start_ghap")
        enum = _extract_enum_from_schema(schema, "properties", "strategy")
        assert enum == STRATEGIES, "start_ghap strategy enum mismatch"

    def test_update_ghap_strategy_matches_enums(self) -> None:
        """BUG-026: update_ghap strategy enum should match STRATEGIES."""
        schema = _get_tool_by_name("update_ghap")
        enum = _extract_enum_from_schema(schema, "properties", "strategy")
        assert enum == STRATEGIES, "update_ghap strategy enum mismatch"


class TestOutcomeEnumConsistency:
    """Verify outcome status enum is consistent."""

    def test_resolve_ghap_status_matches_enums(self) -> None:
        """BUG-026: resolve_ghap status enum should match OUTCOME_STATUS_VALUES."""
        schema = _get_tool_by_name("resolve_ghap")
        enum = _extract_enum_from_schema(schema, "properties", "status")
        assert enum == OUTCOME_STATUS_VALUES, "resolve_ghap status enum mismatch"

    def test_list_ghap_entries_outcome_matches_enums(self) -> None:
        """BUG-026: list_ghap_entries outcome enum should match OUTCOME_STATUS_VALUES."""
        schema = _get_tool_by_name("list_ghap_entries")
        enum = _extract_enum_from_schema(schema, "properties", "outcome")
        assert enum == OUTCOME_STATUS_VALUES, "list_ghap_entries outcome enum mismatch"

    def test_search_experiences_outcome_matches_enums(self) -> None:
        """BUG-026: search_experiences outcome enum should match OUTCOME_STATUS_VALUES."""
        schema = _get_tool_by_name("search_experiences")
        enum = _extract_enum_from_schema(schema, "properties", "outcome")
        assert enum == OUTCOME_STATUS_VALUES, "search_experiences outcome enum mismatch"


class TestRootCauseEnumConsistency:
    """Verify root cause category enum is consistent."""

    def test_resolve_ghap_root_cause_category_matches_enums(self) -> None:
        """BUG-026: resolve_ghap root_cause.category should match ROOT_CAUSE_CATEGORIES."""
        schema = _get_tool_by_name("resolve_ghap")
        root_cause = schema.get("properties", {}).get("root_cause", {})
        category = root_cause.get("properties", {}).get("category", {})
        enum = category.get("enum")
        assert enum == ROOT_CAUSE_CATEGORIES, "resolve_ghap root_cause.category mismatch"


class TestAxisEnumConsistency:
    """Verify axis enum is consistent across schemas and validation."""

    def test_get_clusters_axis_matches_enums(self) -> None:
        """BUG-026: get_clusters axis enum should match VALID_AXES."""
        schema = _get_tool_by_name("get_clusters")
        enum = _extract_enum_from_schema(schema, "properties", "axis")
        assert enum == VALID_AXES, "get_clusters axis enum mismatch"

    def test_store_value_axis_matches_enums(self) -> None:
        """BUG-026: store_value axis enum should match VALID_AXES."""
        schema = _get_tool_by_name("store_value")
        enum = _extract_enum_from_schema(schema, "properties", "axis")
        assert enum == VALID_AXES, "store_value axis enum mismatch"

    def test_list_values_axis_matches_enums(self) -> None:
        """BUG-026: list_values axis enum should match VALID_AXES."""
        schema = _get_tool_by_name("list_values")
        enum = _extract_enum_from_schema(schema, "properties", "axis")
        assert enum == VALID_AXES, "list_values axis enum mismatch"

    def test_search_experiences_axis_matches_enums(self) -> None:
        """BUG-026: search_experiences axis enum should match VALID_AXES."""
        schema = _get_tool_by_name("search_experiences")
        enum = _extract_enum_from_schema(schema, "properties", "axis")
        assert enum == VALID_AXES, "search_experiences axis enum mismatch"
