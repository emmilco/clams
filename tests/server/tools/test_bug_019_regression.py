"""Regression test for BUG-019: validate_value returns internal server error.

Tests that validate_value correctly omits similarity field when it's None,
rather than including it and causing JSON serialization issues.
"""

import pytest

from clams.server.tools.learning import get_learning_tools
from clams.values import ValueStore
from clams.values.types import ValidationResult
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_bug_019_regression_validate_value_none_similarity() -> None:
    """Test that validate_value omits similarity when None.

    Regression test for BUG-019 where validate_value returned internal_error
    because it tried to include similarity=None in the response.
    """
    # Setup: Mock ValueStore that returns ValidationResult with similarity=None
    mock_value_store = MagicMock(spec=ValueStore)
    mock_value_store.validate_value_candidate = AsyncMock(
        return_value=ValidationResult(valid=False, similarity=None)
    )

    mock_experience_clusterer = MagicMock()

    tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
    validate_value = tools["validate_value"]

    # Action: call validate_value
    result = await validate_value(text="test value", cluster_id="full_0")

    # Assert: should return valid response without similarity field
    assert "error" not in result, f"Unexpected error: {result}"
    assert result["valid"] is False
    assert result["cluster_id"] == "full_0"
    # Similarity should NOT be present when None
    assert "similarity" not in result, (
        "similarity should be omitted when None to avoid JSON serialization issues"
    )


@pytest.mark.asyncio
async def test_bug_019_validate_value_with_similarity() -> None:
    """Test that validate_value includes similarity when present."""
    # Setup: Mock ValueStore that returns ValidationResult with actual similarity
    mock_value_store = MagicMock(spec=ValueStore)
    mock_value_store.validate_value_candidate = AsyncMock(
        return_value=ValidationResult(valid=True, similarity=0.85)
    )

    mock_experience_clusterer = MagicMock()

    tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
    validate_value = tools["validate_value"]

    # Action: call validate_value
    result = await validate_value(text="test value", cluster_id="full_0")

    # Assert: should return valid response WITH similarity field
    assert "error" not in result, f"Unexpected error: {result}"
    assert result["valid"] is True
    assert result["cluster_id"] == "full_0"
    assert result["similarity"] == 0.85
