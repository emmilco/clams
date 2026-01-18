"""Cold-start tests for values/learning operations.

These tests verify that value operations handle the cold-start scenario
where no values or experiences exist yet.

Reference: BUG-043 - values collection was never created
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.server.tools.learning import get_learning_tools
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
def mock_experience_clusterer(
    mock_vector_store_cold_start: AsyncMock,
) -> AsyncMock:
    """Mock ExperienceClusterer for cold-start testing."""
    clusterer = AsyncMock()
    # Use mock vector store to avoid real Qdrant calls
    clusterer.vector_store = mock_vector_store_cold_start

    # count_experiences returns 0 on cold start
    clusterer.count_experiences.return_value = 0

    # cluster_axis returns empty list on cold start
    clusterer.cluster_axis.return_value = []

    return clusterer


@pytest.fixture
def mock_value_store() -> AsyncMock:
    """Mock ValueStore for cold-start testing."""
    store = AsyncMock()

    # list_values returns empty on cold start
    store.list_values.return_value = []

    # validate_value_candidate returns invalid for empty cluster
    mock_result = MagicMock()
    mock_result.valid = False
    mock_result.reason = "Not enough experiences"
    mock_result.similarity = None
    store.validate_value_candidate.return_value = mock_result

    return store


class TestStoreValueColdStart:
    """Tests for store_value on cold start."""

    @pytest.mark.cold_start
    async def test_store_value_insufficient_data(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """store_value on cold start returns error for insufficient data."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        store_value = tools["store_value"]

        # Mock store_value to raise ValueError for validation failure
        mock_value_store.store_value.side_effect = ValueError(
            "Value failed validation: Not enough experiences"
        )

        result = await store_value(
            text="Test value",
            cluster_id="full_0",
            axis="full",
        )

        # Should return error response, not raise exception
        assert "error" in result
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.cold_start
    async def test_store_value_no_exception(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """store_value should not raise unhandled exceptions on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        store_value = tools["store_value"]

        # Mock to raise ValueError (expected on cold start)
        mock_value_store.store_value.side_effect = ValueError(
            "Validation failed"
        )

        # Should return error dict, not raise
        result = await store_value(
            text="Test value statement",
            cluster_id="strategy_1",
            axis="strategy",
        )

        assert isinstance(result, dict)
        assert "error" in result


class TestListValuesColdStart:
    """Tests for list_values on cold start."""

    @pytest.mark.cold_start
    async def test_list_values_returns_empty_list(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """list_values on cold start returns empty list."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        result = await list_values()

        # Should return empty results, not error
        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_list_values_no_exception(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """list_values should not raise exception on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        # Should not raise
        result = await list_values(axis="full", limit=20)

        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_list_values_with_filters_cold_start(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """list_values with axis filter should return empty on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        result = await list_values(axis="strategy")

        assert "results" in result
        assert result["results"] == []


class TestGetClustersColdStart:
    """Tests for get_clusters on cold start."""

    @pytest.mark.cold_start
    async def test_get_clusters_insufficient_data(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """get_clusters on cold start returns error for insufficient data."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_clusters = tools["get_clusters"]

        result = await get_clusters(axis="full")

        # Should return error response with insufficient_data type
        assert "error" in result
        assert result["error"]["type"] == "insufficient_data"
        assert "20" in result["error"]["message"]  # Need at least 20 experiences

    @pytest.mark.cold_start
    async def test_get_clusters_returns_dict_with_clusters_key(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """get_clusters always returns dict with clusters key (may be error)."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_clusters = tools["get_clusters"]

        result = await get_clusters(axis="strategy")

        # Either clusters key or error key
        assert isinstance(result, dict)
        assert "clusters" in result or "error" in result

    @pytest.mark.cold_start
    async def test_get_clusters_no_exception(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """get_clusters should not raise exception on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_clusters = tools["get_clusters"]

        # Should not raise
        result = await get_clusters(axis="surprise")

        assert isinstance(result, dict)


class TestGetClusterMembersColdStart:
    """Tests for get_cluster_members on cold start."""

    @pytest.mark.cold_start
    async def test_get_cluster_members_returns_empty(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """get_cluster_members on cold start returns empty members list."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_cluster_members = tools["get_cluster_members"]

        result = await get_cluster_members(cluster_id="full_0")

        # Should return empty members, not error
        assert "members" in result
        assert result["members"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_get_cluster_members_no_exception(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """get_cluster_members should not raise exception on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        get_cluster_members = tools["get_cluster_members"]

        # Should not raise
        result = await get_cluster_members(cluster_id="strategy_1", limit=10)

        assert isinstance(result, dict)


class TestValidateValueColdStart:
    """Tests for validate_value on cold start."""

    @pytest.mark.cold_start
    async def test_validate_value_returns_invalid(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """validate_value on cold start returns invalid result."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        validate_value = tools["validate_value"]

        result = await validate_value(
            text="Test value statement",
            cluster_id="full_0",
        )

        # Should return validation result dict
        assert isinstance(result, dict)
        # On cold start, validation typically fails (no cluster data)
        assert "valid" in result or "error" in result

    @pytest.mark.cold_start
    async def test_validate_value_no_exception(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """validate_value should not raise exception on cold start."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        validate_value = tools["validate_value"]

        # Should not raise
        result = await validate_value(
            text="Another test value",
            cluster_id="strategy_2",
        )

        assert isinstance(result, dict)


class TestValuesCollectionCreation:
    """Tests verifying values collection behavior on cold start."""

    @pytest.mark.cold_start
    async def test_values_collection_not_exists_initially(
        self,
        fresh_cold_start_qdrant: QdrantVectorStore,
    ) -> None:
        """Verify values collection doesn't exist on cold start."""
        info = await fresh_cold_start_qdrant.get_collection_info("values")
        assert info is None, "values collection should not exist on cold start"

    @pytest.mark.cold_start
    async def test_list_values_handles_missing_collection(
        self,
        mock_experience_clusterer: AsyncMock,
        mock_value_store: AsyncMock,
    ) -> None:
        """list_values should gracefully handle missing values collection."""
        tools = get_learning_tools(mock_experience_clusterer, mock_value_store)
        list_values = tools["list_values"]

        # Should return empty, not 404
        result = await list_values()

        assert isinstance(result, dict)
        assert result.get("count", 0) == 0
