# SPEC-017 Technical Proposal: Schema Conformance Tests for Enum Validation

## Problem Statement

BUG-026 demonstrated that advertised enum values in MCP tool definitions can drift from actual validation in the codebase. While the current implementation in `src/clams/server/tools/__init__.py` uses the enum constants directly from `enums.py` (e.g., `"enum": DOMAINS`), which is good design, we need tests to:

1. Verify this pattern is maintained and not accidentally replaced with hardcoded values
2. Catch any missing tools that should declare enum constraints
3. Document the expected behavior for future maintainers
4. Run in CI to prevent regression

A regression test file exists at `tests/server/tools/test_bug_026_regression.py`, but per the spec requirements, we need a dedicated conformance test file at the specified location with comprehensive coverage of all tools.

## Proposed Solution

### Test File Location

Create `tests/server/test_enum_schema_conformance.py` as specified in acceptance criteria.

### Test Structure

The test file will be organized by enum type, with tests for each tool that uses that enum. The structure follows the existing pattern in `test_bug_026_regression.py` but with improvements:

1. **Parameterized tests** - Use pytest parameterization to reduce boilerplate and make it easy to add new tools
2. **Helper functions** - Reusable utilities for extracting enums from schemas
3. **Comprehensive coverage** - Test ALL tools listed in the spec
4. **Clear error messages** - Include both expected and actual values in assertions

### Test Code Outline

```python
"""Schema conformance tests for enum validation.

Verifies that enum values declared in MCP tool definitions match the canonical
enum definitions in enums.py. This prevents drift between advertised API schema
and actual validation (BUG-026).

Location: tests/server/test_enum_schema_conformance.py
"""

import pytest

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


def get_tool_schema(tool_name: str) -> dict:
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


def extract_enum_from_property(schema: dict, property_name: str) -> list | None:
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
    schema: dict, parent_property: str, child_property: str
) -> list | None:
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
# Domain Enum Tests
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
            f"  Expected (DOMAINS): {DOMAINS}"
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
            f"  Expected (STRATEGIES): {STRATEGIES}"
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
            f"  Expected (OUTCOME_STATUS_VALUES): {OUTCOME_STATUS_VALUES}"
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
            f"  Expected (OUTCOME_STATUS_VALUES): {OUTCOME_STATUS_VALUES}"
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
            f"  Expected (VALID_AXES): {VALID_AXES}"
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
            f"  Expected (ROOT_CAUSE_CATEGORIES): {ROOT_CAUSE_CATEGORIES}"
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
            "get_cluster_members cluster_id should document axis prefix format"
        )
        # Verify description includes example format
        assert "_" in description, (
            "get_cluster_members cluster_id should include format example (e.g., 'full_0')"
        )
```

### Key Design Decisions

1. **Parameterized tests**: Using `@pytest.mark.parametrize` reduces boilerplate and makes it trivial to add new tools to the test suite.

2. **Helper functions**: The `get_tool_schema`, `extract_enum_from_property`, and `extract_enum_from_nested_property` helpers make tests readable and maintainable.

3. **Explicit type conversion**: Using `list(enum) == list(EXPECTED)` ensures we compare values rather than object identity, which is important since the schema may contain the same list object or a copy.

4. **Clear error messages**: Each assertion includes the actual and expected values formatted for easy debugging.

5. **Cluster ID special case**: The `get_cluster_members` tool doesn't have an enum for `cluster_id` (it's a string), but the spec mentions it contains an axis prefix. We test that the description documents this format rather than asserting on enum values.

### Relationship to Existing Tests

The new file `tests/server/test_enum_schema_conformance.py` supersedes the coverage in `tests/server/tools/test_bug_026_regression.py` for schema conformance. The existing regression test can remain as-is (it provides BUG-026-specific documentation) or be consolidated into the new file.

Recommendation: Keep `test_bug_026_regression.py` as historical documentation of the bug but ensure `test_enum_schema_conformance.py` is the authoritative source for schema conformance testing.

### Out of Scope

As stated in the spec:
- Testing that validation functions reject invalid enums (covered by `tests/server/tools/test_enums.py`)
- Testing MCP tool response schemas (covered by SPEC-021)

## Files to Create/Modify

| File | Action |
|------|--------|
| `tests/server/test_enum_schema_conformance.py` | Create |
| `tests/server/__init__.py` | Verify exists (no change expected) |

## Testing the Tests

After implementation, verify the tests work correctly by:

1. Run the new test file: `pytest tests/server/test_enum_schema_conformance.py -v`
2. Temporarily modify an enum in `__init__.py` to use hardcoded values and verify tests fail
3. Restore the original and verify tests pass

## CI Integration

No additional CI configuration needed - the tests will automatically run as part of the existing pytest suite.
