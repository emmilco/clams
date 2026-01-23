"""Cold-start tests for GHAP operations.

These tests verify that GHAP operations handle the cold-start scenario
where no GHAP entries exist yet.

Reference: BUG-016 - GHAP collections missing on first start
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.server.tools.ghap import get_ghap_tools
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
async def fresh_cold_start_qdrant() -> AsyncIterator[QdrantVectorStore]:
    """Create a fresh in-memory Qdrant instance for each test."""
    store = QdrantVectorStore(url=":memory:")
    yield store


@pytest.fixture
def mock_vector_store_cold_start() -> AsyncMock:
    """Mock vector store that simulates cold start (no collections)."""
    store = AsyncMock()
    # scroll returns empty list on cold start
    store.scroll.return_value = []
    return store


@pytest.fixture
def mock_observation_collector() -> AsyncMock:
    """Mock ObservationCollector for cold-start testing."""
    collector = AsyncMock()

    # get_current returns None (no active GHAP)
    collector.get_current.return_value = None

    # create_ghap returns a mock entry
    mock_entry = MagicMock()
    mock_entry.id = "ghap-test-123"
    mock_entry.iteration_count = 1
    collector.create_ghap.return_value = mock_entry

    return collector


@pytest.fixture
def mock_observation_persister(
    mock_vector_store_cold_start: AsyncMock,
) -> AsyncMock:
    """Mock ObservationPersister for cold-start testing."""
    persister = AsyncMock()
    # Use mock vector store to avoid real Qdrant calls
    persister._vector_store = mock_vector_store_cold_start
    persister.persist.return_value = None
    return persister


class TestStartGhapColdStart:
    """Tests for start_ghap on cold start."""

    @pytest.mark.cold_start
    async def test_start_ghap_returns_id(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """start_ghap on cold start returns dict with ghap_id key."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        start_ghap = tools["start_ghap"]

        result = await start_ghap(
            domain="debugging",
            strategy="root-cause-analysis",  # Valid strategy
            goal="Find the root cause",
            hypothesis="The bug is in the parser",
            action="Add logging to parser",
            prediction="Logs will show malformed input",
        )

        # Should return success with id
        assert "ok" in result or "id" in result
        if "ok" in result:
            assert result["ok"] is True

    @pytest.mark.cold_start
    async def test_start_ghap_no_exception(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """start_ghap should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        start_ghap = tools["start_ghap"]

        # Should not raise
        result = await start_ghap(
            domain="feature",
            strategy="research-first",  # Valid strategy
            goal="Add new endpoint",
            hypothesis="Endpoint will improve UX",
            action="Implement the endpoint",
            prediction="Tests will pass",
        )

        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_start_ghap_creates_entry(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """start_ghap should successfully create GHAP entry on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        start_ghap = tools["start_ghap"]

        result = await start_ghap(
            domain="refactoring",
            strategy="divide-and-conquer",  # Valid strategy
            goal="Simplify complex function",
            hypothesis="Breaking it up will help",
            action="Extract helper functions",
            prediction="Function becomes readable",
        )

        # Verify collector.create_ghap was called
        assert mock_observation_collector.create_ghap.called
        assert isinstance(result, dict)


class TestListGhapEntriesColdStart:
    """Tests for list_ghap_entries on cold start."""

    @pytest.mark.cold_start
    async def test_list_ghap_entries_returns_empty(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """list_ghap_entries on cold start returns empty list or dict with empty entries."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        result = await list_ghap_entries()

        # Should return empty results (collection may not exist yet)
        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_list_ghap_entries_no_exception(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """list_ghap_entries should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        # Should not raise
        result = await list_ghap_entries(
            limit=20,
            domain="debugging",
        )

        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_list_ghap_entries_with_filters_cold_start(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """list_ghap_entries with filters should return empty on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        result = await list_ghap_entries(
            domain="feature",
            outcome="confirmed",
            limit=10,
        )

        assert "results" in result
        assert result["results"] == []


class TestGetActiveGhapColdStart:
    """Tests for get_active_ghap on cold start."""

    @pytest.mark.cold_start
    async def test_get_active_ghap_returns_no_active(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """get_active_ghap on cold start returns indicator of no active GHAP."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        get_active_ghap = tools["get_active_ghap"]

        result = await get_active_ghap()

        # Should indicate no active GHAP
        assert isinstance(result, dict)
        assert result.get("has_active") is False
        assert result.get("id") is None

    @pytest.mark.cold_start
    async def test_get_active_ghap_no_exception(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """get_active_ghap should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        get_active_ghap = tools["get_active_ghap"]

        # Should not raise
        result = await get_active_ghap()

        assert isinstance(result, dict)


class TestUpdateGhapColdStart:
    """Tests for update_ghap on cold start."""

    @pytest.mark.cold_start
    async def test_update_ghap_returns_not_found(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """update_ghap on cold start returns not_found error (no active GHAP)."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        update_ghap = tools["update_ghap"]

        result = await update_ghap(hypothesis="Updated hypothesis")

        # Should return error since no active GHAP
        assert "error" in result
        assert result["error"]["type"] == "not_found"

    @pytest.mark.cold_start
    async def test_update_ghap_no_exception(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """update_ghap should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        update_ghap = tools["update_ghap"]

        # Should return error dict, not raise
        result = await update_ghap(action="New action")

        assert isinstance(result, dict)


class TestResolveGhapColdStart:
    """Tests for resolve_ghap on cold start."""

    @pytest.mark.cold_start
    async def test_resolve_ghap_returns_not_found(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """resolve_ghap on cold start returns not_found error (no active GHAP)."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        resolve_ghap = tools["resolve_ghap"]

        result = await resolve_ghap(
            status="confirmed",
            result="It worked as expected",
        )

        # Should return error since no active GHAP
        assert "error" in result
        assert result["error"]["type"] == "not_found"

    @pytest.mark.cold_start
    async def test_resolve_ghap_no_exception(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """resolve_ghap should not raise exception on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        resolve_ghap = tools["resolve_ghap"]

        # Should return error dict, not raise
        result = await resolve_ghap(
            status="abandoned",
            result="Approach was wrong",
        )

        assert isinstance(result, dict)


class TestGhapCollectionCreation:
    """Tests verifying GHAP collection behavior on cold start."""

    @pytest.mark.cold_start
    async def test_ghap_full_collection_not_exists_initially(
        self,
        fresh_cold_start_qdrant: QdrantVectorStore,
    ) -> None:
        """Verify ghap_full collection doesn't exist on cold start."""
        info = await fresh_cold_start_qdrant.get_collection_info("ghap_full")
        assert info is None, "ghap_full collection should not exist on cold start"

    @pytest.mark.cold_start
    async def test_list_ghap_handles_missing_collection(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """list_ghap_entries should gracefully handle missing ghap_full collection."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        # Should return empty, not 404
        result = await list_ghap_entries()

        assert isinstance(result, dict)
        assert result.get("count", 0) == 0
        assert "error" not in result or "404" not in str(result.get("error", ""))


class TestGhapWorkflowOnColdStart:
    """Tests verifying complete GHAP workflow on cold start."""

    @pytest.mark.cold_start
    async def test_full_ghap_workflow_cold_start(
        self,
        mock_observation_collector: AsyncMock,
        mock_observation_persister: AsyncMock,
    ) -> None:
        """Test starting and getting active GHAP on cold start."""
        tools = get_ghap_tools(mock_observation_collector, mock_observation_persister)

        # 1. Check no active GHAP
        active = await tools["get_active_ghap"]()
        assert active.get("has_active") is False

        # 2. Start a new GHAP (use valid strategy: systematic-elimination)
        start_result = await tools["start_ghap"](
            domain="debugging",
            strategy="systematic-elimination",  # Valid strategy
            goal="Find the bug",
            hypothesis="Bug is in recent changes",
            action="Review recent commits",
            prediction="Will find suspicious commit",
        )
        assert "id" in start_result or "ok" in start_result

        # 3. List GHAP entries (should be empty since mock doesn't persist)
        list_result = await tools["list_ghap_entries"]()
        assert isinstance(list_result, dict)
