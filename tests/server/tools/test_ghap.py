"""Tests for GHAP tools."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from learning_memory_server.observation import (
    ObservationCollector,
    ObservationPersister,
)
from learning_memory_server.server.tools.ghap import get_ghap_tools


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
    return ObservationPersister(
        embedding_service=MagicMock(),
        vector_store=vector_store,
    )


@pytest.fixture
def tools(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> dict[str, Any]:
    """Get GHAP tools."""
    return get_ghap_tools(observation_collector, observation_persister)


class TestStartGhap:
    """Tests for start_ghap tool."""

    @pytest.mark.asyncio
    async def test_start_ghap_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful GHAP creation."""
        tool = tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix auth timeout bug",
            hypothesis="Slow network responses exceed 30s timeout",
            action="Increasing timeout to 60s",
            prediction="Auth failures stop",
        )

        assert "error" not in result
        assert result["id"] is not None
        assert result["domain"] == "debugging"
        assert result["strategy"] == "systematic-elimination"
        assert result["goal"] == "Fix auth timeout bug"
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_domain(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid domain."""
        tool = tools["start_ghap"]
        result = await tool(
            domain="invalid",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]
        assert "debugging" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_strategy(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid strategy."""
        tool = tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="invalid",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid strategy" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_start_ghap_empty_field(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for empty required field."""
        tool = tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "cannot be empty" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_start_ghap_field_too_long(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for field exceeding length limit."""
        tool = tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="x" * 1001,
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "1000 character limit" in result["error"]["message"]


class TestUpdateGhap:
    """Tests for update_ghap tool."""

    @pytest.mark.asyncio
    async def test_update_ghap_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful GHAP update."""
        # First start a GHAP
        start_tool = tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Initial hypothesis",
            action="Initial action",
            prediction="Initial prediction",
        )

        # Now update it
        update_tool = tools["update_ghap"]
        result = await update_tool(
            hypothesis="Updated hypothesis",
            action="Updated action",
        )

        assert "error" not in result
        assert result["success"] is True
        assert result["iteration_count"] == 2

    @pytest.mark.asyncio
    async def test_update_ghap_no_active_entry(
        self, tools: dict[str, Any]
    ) -> None:
        """Test error when no active GHAP entry exists."""
        tool = tools["update_ghap"]
        result = await tool(hypothesis="Test")

        assert "error" in result
        assert result["error"]["type"] == "not_found"
        assert "No active GHAP entry" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_update_ghap_field_too_long(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for field too long."""
        # First start a GHAP
        start_tool = tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Initial hypothesis",
            action="Initial action",
            prediction="Initial prediction",
        )

        # Try to update with too-long field
        update_tool = tools["update_ghap"]
        result = await update_tool(hypothesis="x" * 1001)

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "1000 character limit" in result["error"]["message"]


class TestResolveGhap:
    """Tests for resolve_ghap tool."""

    @pytest.mark.asyncio
    async def test_resolve_ghap_confirmed(
        self, tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """Test resolving GHAP as confirmed."""
        # Mock the persist method
        observation_persister.persist = AsyncMock()

        # First start a GHAP
        start_tool = tools["start_ghap"]
        start_result = await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Resolve it
        resolve_tool = tools["resolve_ghap"]
        result = await resolve_tool(
            status="confirmed",
            result="Test passed 3/3 runs",
            lesson={
                "what_worked": "Added proper fix",
                "takeaway": "Good lesson",
            },
        )

        assert "error" not in result
        assert result["id"] == start_result["id"]
        assert result["status"] == "confirmed"
        # Manual resolutions get "silver" tier; "gold" is for auto-captured resolutions
        assert result["confidence_tier"] == "silver"
        assert result["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolve_ghap_falsified(
        self, tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """Test resolving GHAP as falsified."""
        # Mock the persist method
        observation_persister.persist = AsyncMock()

        # First start a GHAP
        start_tool = tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Resolve as falsified
        resolve_tool = tools["resolve_ghap"]
        result = await resolve_tool(
            status="falsified",
            result="Didn't work",
            surprise="Unexpected behavior",
            root_cause={
                "category": "wrong-assumption",
                "description": "Wrong assumption about issue",
            },
        )

        assert "error" not in result
        assert result["status"] == "falsified"
        assert result["confidence_tier"] == "silver"

    @pytest.mark.asyncio
    async def test_resolve_ghap_falsified_missing_surprise(
        self, tools: dict[str, Any]
    ) -> None:
        """Test error when falsified without surprise."""
        # First start a GHAP
        start_tool = tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Try to resolve as falsified without surprise
        resolve_tool = tools["resolve_ghap"]
        result = await resolve_tool(
            status="falsified",
            result="Didn't work",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "surprise" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_resolve_ghap_invalid_status(
        self, tools: dict[str, Any]
    ) -> None:
        """Test error with invalid status."""
        # First start a GHAP
        start_tool = tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Try to resolve with invalid status
        resolve_tool = tools["resolve_ghap"]
        result = await resolve_tool(
            status="invalid",
            result="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid outcome status" in result["error"]["message"]


class TestGetActiveGhap:
    """Tests for get_active_ghap tool."""

    @pytest.mark.asyncio
    async def test_get_active_ghap_with_entry(
        self, tools: dict[str, Any]
    ) -> None:
        """Test getting active GHAP when one exists."""
        # First start a GHAP
        start_tool = tools["start_ghap"]
        start_result = await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Get active GHAP
        get_tool = tools["get_active_ghap"]
        result = await get_tool()

        assert "error" not in result
        assert result["has_active"] is True
        assert result["id"] == start_result["id"]
        assert result["domain"] == "debugging"

    @pytest.mark.asyncio
    async def test_get_active_ghap_no_entry(
        self, tools: dict[str, Any]
    ) -> None:
        """Test getting active GHAP when none exists."""
        tool = tools["get_active_ghap"]
        result = await tool()

        assert "error" not in result
        assert result["has_active"] is False
        assert result["id"] is None


class TestListGhapEntries:
    """Tests for list_ghap_entries tool."""

    @pytest.mark.asyncio
    async def test_list_ghap_entries_default(
        self, tools: dict[str, Any]
    ) -> None:
        """Test listing GHAP entries with default parameters."""
        tool = tools["list_ghap_entries"]
        result = await tool()

        assert "error" not in result
        assert "results" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_limit(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid limit."""
        tool = tools["list_ghap_entries"]
        result = await tool(limit=0)

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 100" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_domain(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid domain filter."""
        tool = tools["list_ghap_entries"]
        result = await tool(domain="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_date(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid date format."""
        tool = tools["list_ghap_entries"]
        result = await tool(since="not a date")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid date format" in result["error"]["message"]
