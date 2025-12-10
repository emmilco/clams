"""Regression test for BUG-020: store_value returns internal server error.

Tests that store_value properly handles ValueError from ValueStore.store_value
and returns a validation_error response instead of internal_error.
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from clams.server.tools.learning import get_learning_tools
from clams.values import ValueStore
from clams.values.types import Value


@pytest.mark.asyncio
async def test_bug_020_regression_store_value_valueerror() -> None:
    """Test that store_value catches ValueError and returns validation_error.

    Regression test for BUG-020 where store_value returned internal_error
    when ValueStore.store_value raised ValueError for validation failures.
    """
    # Setup: Mock ValueStore that raises ValueError
    mock_value_store = MagicMock(spec=ValueStore)
    mock_value_store.store_value = AsyncMock(
        side_effect=ValueError("Value is too far from cluster centroid")
    )

    mock_experience_clusterer = MagicMock()

    tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
    store_value = tools["store_value"]

    # Action: call store_value (should trigger ValueError)
    result = await store_value(text="bad value", cluster_id="full_0", axis="full")

    # Assert: should return validation_error, NOT internal_error
    assert "error" in result, "Expected error response"
    assert result["error"]["type"] == "validation_error", (
        f"Expected validation_error, got {result['error']['type']}"
    )
    assert "too far from cluster centroid" in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_bug_020_store_value_success() -> None:
    """Test that store_value returns success when ValueStore succeeds."""
    # Setup: Mock ValueStore that succeeds with a proper Value object
    mock_value = Value(
        id="value_123",
        text="good value",
        cluster_id="full_0",
        axis="full",
        embedding=np.array([0.1] * 768, dtype=np.float32),
        cluster_size=10,
        created_at="2025-01-01T12:00:00Z",
    )
    mock_value_store = MagicMock(spec=ValueStore)
    mock_value_store.store_value = AsyncMock(return_value=mock_value)

    mock_experience_clusterer = MagicMock()

    tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
    store_value = tools["store_value"]

    # Action: call store_value
    result = await store_value(text="good value", cluster_id="full_0", axis="full")

    # Assert: should return success response
    assert "error" not in result, f"Unexpected error: {result}"
    assert result["id"] == "value_123"
