"""Input validation tests for learning tools.

Tests cover:
- get_clusters: axis
- get_cluster_members: cluster_id, limit
- validate_value: text, cluster_id
- store_value: text, cluster_id, axis
- list_values: axis, limit

This test module verifies that all validation constraints are enforced
with informative error messages.

References bugs:
- BUG-019: validate_value returns internal server error
- BUG-020: store_value returns internal server error
"""

from typing import Any

import pytest

from .helpers import assert_error_response


class TestGetClustersValidation:
    """Validation tests for get_clusters tool."""

    @pytest.mark.asyncio
    async def test_get_clusters_missing_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_clusters requires axis field."""
        tool = learning_tools["get_clusters"]
        with pytest.raises(TypeError, match="axis"):
            await tool()

    @pytest.mark.asyncio
    async def test_get_clusters_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_clusters rejects invalid axis."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis="invalid")
        assert_error_response(result, field_name="axis")

    @pytest.mark.asyncio
    async def test_get_clusters_invalid_axis_lists_valid_options(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that axis error lists valid options."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis="invalid")
        assert "full" in result["error"]["message"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("axis", ["full", "strategy", "surprise", "root_cause"])
    async def test_get_clusters_accepts_valid_axis(
        self, learning_tools: dict[str, Any], axis: str
    ) -> None:
        """Test that get_clusters accepts all valid axis values."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis=axis)
        # May return insufficient_data but not validation_error
        if "error" in result:
            assert result["error"]["type"] != "validation_error"


class TestGetClusterMembersValidation:
    """Validation tests for get_cluster_members tool."""

    @pytest.mark.asyncio
    async def test_get_cluster_members_missing_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members requires cluster_id field."""
        tool = learning_tools["get_cluster_members"]
        with pytest.raises(TypeError, match="cluster_id"):
            await tool()

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_cluster_id_format(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members rejects invalid cluster_id format."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="invalid")
        assert_error_response(result, message_contains="Invalid cluster_id format")

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_cluster_id_format_shows_expected(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that cluster_id format error shows expected format."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="invalid")
        assert "axis_label" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_axis_in_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members rejects invalid axis in cluster_id."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="invalid_0")
        assert_error_response(result)

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_label_in_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members rejects non-integer label."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_abc")
        assert_error_response(result, message_contains="Label must be an integer")

    @pytest.mark.asyncio
    async def test_get_cluster_members_limit_below_range(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members rejects limit < 1."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_0", limit=0)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_get_cluster_members_limit_above_range(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members rejects limit > 100."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_0", limit=101)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_get_cluster_members_limit_at_boundary_lower(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members accepts limit = 1."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_0", limit=1)
        # Should not fail validation
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

    @pytest.mark.asyncio
    async def test_get_cluster_members_limit_at_boundary_upper(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that get_cluster_members accepts limit = 100."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_0", limit=100)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"


class TestValidateValueValidation:
    """Validation tests for validate_value tool.

    BUG-019: validate_value was returning internal server error for
    validation failures. Tests ensure proper validation_error response.
    """

    @pytest.mark.asyncio
    async def test_validate_value_missing_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value requires text field."""
        tool = learning_tools["validate_value"]
        with pytest.raises(TypeError, match="text"):
            await tool(cluster_id="strategy_0")

    @pytest.mark.asyncio
    async def test_validate_value_missing_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value requires cluster_id field."""
        tool = learning_tools["validate_value"]
        with pytest.raises(TypeError, match="cluster_id"):
            await tool(text="Test value")

    @pytest.mark.asyncio
    async def test_validate_value_empty_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value rejects empty text.

        BUG-019 regression: Should return validation_error, not internal_error.
        """
        tool = learning_tools["validate_value"]
        result = await tool(text="", cluster_id="strategy_0")
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_validate_value_whitespace_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value rejects whitespace-only text."""
        tool = learning_tools["validate_value"]
        result = await tool(text="   ", cluster_id="strategy_0")
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_validate_value_text_too_long(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value rejects text exceeding 500 chars."""
        tool = learning_tools["validate_value"]
        result = await tool(text="x" * 501, cluster_id="strategy_0")
        assert_error_response(result, message_contains="500 character limit")

    @pytest.mark.asyncio
    async def test_validate_value_invalid_cluster_id_format(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value rejects invalid cluster_id format."""
        tool = learning_tools["validate_value"]
        result = await tool(text="Test value", cluster_id="invalid")
        assert_error_response(result, message_contains="Invalid cluster_id format")

    @pytest.mark.asyncio
    async def test_validate_value_invalid_axis_in_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that validate_value rejects invalid axis in cluster_id."""
        tool = learning_tools["validate_value"]
        result = await tool(text="Test value", cluster_id="invalid_0")
        assert_error_response(result)


class TestStoreValueValidation:
    """Validation tests for store_value tool.

    BUG-020: store_value was returning internal server error for
    validation failures. Tests ensure proper validation_error response.
    """

    @pytest.mark.asyncio
    async def test_store_value_missing_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value requires text field."""
        tool = learning_tools["store_value"]
        with pytest.raises(TypeError, match="text"):
            await tool(cluster_id="strategy_0", axis="strategy")

    @pytest.mark.asyncio
    async def test_store_value_missing_cluster_id(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value requires cluster_id field."""
        tool = learning_tools["store_value"]
        with pytest.raises(TypeError, match="cluster_id"):
            await tool(text="Test value", axis="strategy")

    @pytest.mark.asyncio
    async def test_store_value_missing_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value requires axis field."""
        tool = learning_tools["store_value"]
        with pytest.raises(TypeError, match="axis"):
            await tool(text="Test value", cluster_id="strategy_0")

    @pytest.mark.asyncio
    async def test_store_value_empty_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value rejects empty text.

        BUG-020 regression: Should return validation_error, not internal_error.
        """
        tool = learning_tools["store_value"]
        result = await tool(text="", cluster_id="strategy_0", axis="strategy")
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_store_value_whitespace_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value rejects whitespace-only text."""
        tool = learning_tools["store_value"]
        result = await tool(text="   ", cluster_id="strategy_0", axis="strategy")
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_store_value_text_too_long(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value rejects text exceeding 500 chars."""
        tool = learning_tools["store_value"]
        result = await tool(
            text="x" * 501,
            cluster_id="strategy_0",
            axis="strategy",
        )
        assert_error_response(result, message_contains="500 character limit")

    @pytest.mark.asyncio
    async def test_store_value_invalid_cluster_id_format(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value rejects invalid cluster_id format."""
        tool = learning_tools["store_value"]
        result = await tool(
            text="Test value",
            cluster_id="invalid",
            axis="strategy",
        )
        assert_error_response(result, message_contains="Invalid cluster_id format")

    @pytest.mark.asyncio
    async def test_store_value_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that store_value rejects invalid axis."""
        tool = learning_tools["store_value"]
        result = await tool(
            text="Test value",
            cluster_id="invalid_0",
            axis="invalid",
        )
        assert_error_response(result, field_name="axis")


class TestListValuesValidation:
    """Validation tests for list_values tool."""

    @pytest.mark.asyncio
    async def test_list_values_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that list_values rejects invalid axis."""
        tool = learning_tools["list_values"]
        result = await tool(axis="invalid")
        assert_error_response(result)

    @pytest.mark.asyncio
    async def test_list_values_limit_below_range(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that list_values rejects limit < 1."""
        tool = learning_tools["list_values"]
        result = await tool(limit=0)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_list_values_limit_above_range(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that list_values rejects limit > 100."""
        tool = learning_tools["list_values"]
        result = await tool(limit=101)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_list_values_limit_at_boundary_lower(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that list_values accepts limit = 1."""
        tool = learning_tools["list_values"]
        result = await tool(limit=1)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

    @pytest.mark.asyncio
    async def test_list_values_limit_at_boundary_upper(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Test that list_values accepts limit = 100."""
        tool = learning_tools["list_values"]
        result = await tool(limit=100)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("axis", ["full", "strategy", "surprise", "root_cause"])
    async def test_list_values_accepts_valid_axis(
        self, learning_tools: dict[str, Any], axis: str
    ) -> None:
        """Test that list_values accepts all valid axis values."""
        tool = learning_tools["list_values"]
        result = await tool(axis=axis)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"
