"""Regression test for BUG-030: GHAP tools return minimal responses.

This test verifies that start_ghap and resolve_ghap return only the minimal
fields (ok, id) instead of verbose full dictionaries, to reduce token usage.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from calm.ghap import (
    ObservationCollector,
    ObservationPersister,
)
from calm.tools.ghap import get_ghap_tools


@pytest.fixture
def temp_journal_path() -> Path:
    """Create a temporary journal path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def observation_collector(temp_journal_path: Path) -> ObservationCollector:
    """Create an ObservationCollector with temp path."""
    return ObservationCollector(str(temp_journal_path))


@pytest.fixture
def observation_persister() -> ObservationPersister:
    """Create a mock ObservationPersister."""
    vector_store = MagicMock()
    # Make scroll an async method that returns empty results
    vector_store.scroll = AsyncMock(return_value=[])

    # Create a mock embedding service
    embedding_service = MagicMock()
    embedding_service.embed = AsyncMock(return_value=[0.1] * 768)

    persister = ObservationPersister(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    # Mock the persist method to avoid actual persistence
    persister.persist = AsyncMock(return_value=None)
    return persister


@pytest.mark.asyncio
async def test_start_ghap_returns_minimal_response(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> None:
    """Test that start_ghap returns only 'ok' and 'id' fields."""
    tools = get_ghap_tools(observation_collector, observation_persister)
    start_ghap = tools["start_ghap"]

    result = await start_ghap(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix the bug",
        hypothesis="The issue is in the handler",
        action="Modify the return value",
        prediction="Token usage will decrease",
    )

    # Verify only the expected fields are present
    assert set(result.keys()) == {"ok", "id"}
    assert result["ok"] is True
    assert isinstance(result["id"], str)
    assert result["id"].startswith("ghap_")


@pytest.mark.asyncio
async def test_resolve_ghap_returns_minimal_response(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> None:
    """Test that resolve_ghap returns only 'ok' and 'id' fields."""
    tools = get_ghap_tools(observation_collector, observation_persister)
    start_ghap = tools["start_ghap"]
    resolve_ghap = tools["resolve_ghap"]

    # First start a GHAP entry
    start_result = await start_ghap(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix the bug",
        hypothesis="The issue is in the handler",
        action="Modify the return value",
        prediction="Token usage will decrease",
    )

    # Now resolve it
    result = await resolve_ghap(
        status="confirmed",
        result="Token usage decreased as predicted",
        lesson={
            "what_worked": "Returning minimal responses",
            "takeaway": "Less verbose responses reduce token costs",
        },
    )

    # Verify only the expected fields are present
    assert set(result.keys()) == {"ok", "id"}
    assert result["ok"] is True
    assert isinstance(result["id"], str)
    assert result["id"] == start_result["id"]


@pytest.mark.asyncio
async def test_update_ghap_response_unchanged(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> None:
    """Test that update_ghap response format is unchanged (already minimal)."""
    tools = get_ghap_tools(observation_collector, observation_persister)
    start_ghap = tools["start_ghap"]
    update_ghap = tools["update_ghap"]

    # First start a GHAP entry
    await start_ghap(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix the bug",
        hypothesis="The issue is in the handler",
        action="Modify the return value",
        prediction="Token usage will decrease",
    )

    # Update it
    result = await update_ghap(
        hypothesis="The issue is definitely in the handler return values",
    )

    # update_ghap already returns minimal response (success, iteration_count)
    assert set(result.keys()) == {"success", "iteration_count"}
    assert result["success"] is True
    assert result["iteration_count"] == 2  # After update, it's on iteration 2
