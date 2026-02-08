"""Regression test for BUG-029: GHAP start should error when active entry exists."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

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
    from unittest.mock import AsyncMock

    vector_store = MagicMock()
    persister = ObservationPersister(
        embedding_service=MagicMock(),
        vector_store=vector_store,
    )
    # Make persist method async
    persister.persist = AsyncMock()
    return persister


@pytest.fixture
def tools(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> dict[str, Any]:
    """Get GHAP tools."""
    return get_ghap_tools(observation_collector, observation_persister)


class TestBug029ActiveGhapError:
    """Test that start_ghap returns helpful error when active GHAP exists."""

    @pytest.mark.asyncio
    async def test_start_ghap_with_active_returns_helpful_error(
        self, tools: dict[str, Any]
    ) -> None:
        """Verify start_ghap returns helpful error when active GHAP exists.

        BUG-029: Previously, calling start_ghap with an active entry only
        logged a warning and continued, orphaning the previous entry. The fix
        returns a specific error with type 'active_ghap_exists' and a message
        that includes the active GHAP ID and suggests resolution actions.
        """
        start_ghap = tools["start_ghap"]

        # Setup: create an active GHAP
        result1 = await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix auth timeout bug",
            hypothesis="Slow network responses exceed 30s timeout",
            action="Increasing timeout to 60s",
            prediction="Auth failures stop",
        )
        assert "error" not in result1
        assert "id" in result1
        first_ghap_id = result1["id"]

        # Action: try to create another GHAP without resolving the first
        result2 = await start_ghap(
            domain="testing",
            strategy="trial-and-error",
            goal="Test performance",
            hypothesis="Database queries are slow",
            action="Adding indexes",
            prediction="Query time decreases",
        )

        # Assert: get helpful error, not internal_error
        assert "error" in result2
        assert result2["error"]["type"] == "active_ghap_exists"

        # Verify error message includes the active GHAP ID
        error_message = result2["error"]["message"]
        assert first_ghap_id in error_message

        # Verify error message suggests resolution action
        assert "resolve_ghap" in error_message or "Resolve" in error_message

    @pytest.mark.asyncio
    async def test_start_ghap_succeeds_after_resolve(
        self, tools: dict[str, Any]
    ) -> None:
        """Verify start_ghap succeeds after resolving active GHAP.

        This ensures the fix doesn't break the normal workflow where a GHAP
        is started, resolved, then another can be started.
        """
        start_ghap = tools["start_ghap"]
        resolve_ghap = tools["resolve_ghap"]

        # Create first GHAP
        result1 = await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix auth timeout bug",
            hypothesis="Slow network responses exceed 30s timeout",
            action="Increasing timeout to 60s",
            prediction="Auth failures stop",
        )
        assert "error" not in result1
        assert "id" in result1

        # Resolve it
        resolve_result = await resolve_ghap(
            status="confirmed",
            result="Timeout fix worked - auth failures stopped",
        )
        assert "error" not in resolve_result

        # Now start a new GHAP - should succeed
        result2 = await start_ghap(
            domain="testing",
            strategy="trial-and-error",
            goal="Test performance",
            hypothesis="Database queries are slow",
            action="Adding indexes",
            prediction="Query time decreases",
        )
        assert "error" not in result2
        assert "id" in result2
        # Verify it's a different GHAP
        assert result2["id"] != result1["id"]
