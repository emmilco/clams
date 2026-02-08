"""Tests for learning tools."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from calm.clustering import ExperienceClusterer
from calm.clustering.types import ClusterInfo
from calm.tools.learning import get_learning_tools
from calm.values import ValueStore


@pytest.fixture
def experience_clusterer() -> ExperienceClusterer:
    """Create a mock ExperienceClusterer."""
    vector_store = MagicMock()
    # Make scroll an async method that returns empty results
    vector_store.scroll = AsyncMock(return_value=[])

    clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=MagicMock(),
    )
    # Mock the count_experiences method
    clusterer.count_experiences = AsyncMock(return_value=25)
    # Mock the cluster_axis method with ClusterInfo objects
    clusterer.cluster_axis = AsyncMock(
        return_value=[
            ClusterInfo(
                label=0,
                centroid=np.array([1.0, 2.0, 3.0], dtype=np.float32),
                member_ids=["id1", "id2"],
                size=10,
                avg_weight=0.8,
            ),
            ClusterInfo(
                label=1,
                centroid=np.array([4.0, 5.0, 6.0], dtype=np.float32),
                member_ids=["id3", "id4"],
                size=8,
                avg_weight=0.7,
            ),
            ClusterInfo(
                label=-1,
                centroid=np.array([0.0, 0.0, 0.0], dtype=np.float32),
                member_ids=["id5"],
                size=7,
                avg_weight=0.5,
            ),
        ]
    )
    return clusterer


@pytest.fixture
def value_store() -> ValueStore:
    """Create a mock ValueStore."""
    from calm.values.types import ClusterInfo as ValuesClusterInfo

    vector_store = MagicMock()
    # Make scroll an async method that returns empty results
    vector_store.scroll = AsyncMock(return_value=[])

    store = ValueStore(
        embedding_service=MagicMock(),
        vector_store=vector_store,
        clusterer=MagicMock(),
    )
    # Mock the get_clusters method to return values.types.ClusterInfo
    store.get_clusters = AsyncMock(
        return_value=[
            ValuesClusterInfo(
                cluster_id="full_0",
                axis="full",
                label=0,
                centroid=np.array([1.0, 2.0, 3.0], dtype=np.float32),
                member_ids=["id1", "id2"],
                size=10,
                avg_weight=0.8,
            ),
            ValuesClusterInfo(
                cluster_id="full_1",
                axis="full",
                label=1,
                centroid=np.array([4.0, 5.0, 6.0], dtype=np.float32),
                member_ids=["id3", "id4"],
                size=8,
                avg_weight=0.7,
            ),
            ValuesClusterInfo(
                cluster_id="full_-1",
                axis="full",
                label=-1,
                centroid=np.array([0.0, 0.0, 0.0], dtype=np.float32),
                member_ids=["id5"],
                size=7,
                avg_weight=0.5,
            ),
        ]
    )
    # Mock the validate_value_candidate method
    mock_validation = MagicMock()
    mock_validation.valid = True
    mock_validation.similarity = 0.85
    store.validate_value_candidate = AsyncMock(return_value=mock_validation)
    return store


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_semantic_embedder() -> AsyncMock:
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.dimension = 768
    return service


@pytest.fixture
def tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
    experience_clusterer: ExperienceClusterer,
    value_store: ValueStore,
) -> dict[str, Any]:
    """Get learning tools."""
    return get_learning_tools(
        mock_vector_store, mock_semantic_embedder,
        experience_clusterer=experience_clusterer,
        value_store=value_store,
    )


class TestGetClusters:
    """Tests for get_clusters tool."""

    @pytest.mark.asyncio
    async def test_get_clusters_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful cluster retrieval."""
        tool = tools["get_clusters"]
        result = await tool(axis="full")

        assert "error" not in result
        assert result["axis"] == "full"
        assert len(result["clusters"]) == 3  # Includes noise cluster
        assert result["noise_count"] == 1  # Count of noise clusters (label=-1)
        # Should be sorted by size descending
        assert result["clusters"][0]["size"] == 10
        assert result["clusters"][1]["size"] == 8
        assert result["clusters"][2]["size"] == 7

    @pytest.mark.asyncio
    async def test_get_clusters_invalid_axis(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid axis."""
        tool = tools["get_clusters"]
        result = await tool(axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_clusters_insufficient_data(
        self,
        tools: dict[str, Any],
        value_store: ValueStore,
    ) -> None:
        """Test error when not enough experiences exist."""
        # Mock value_store.get_clusters to raise ValueError
        value_store.get_clusters = AsyncMock(
            side_effect=ValueError("Not enough experiences for clustering. Found 15, need at least 20.")
        )

        tool = tools["get_clusters"]
        result = await tool(axis="full")

        assert "status" in result
        assert result["status"] == "error"
        assert "Not enough experiences" in result["message"]


class TestGetClusterMembers:
    """Tests for get_cluster_members tool."""

    @pytest.mark.asyncio
    async def test_get_cluster_members_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful cluster member retrieval."""
        tool = tools["get_cluster_members"]
        result = await tool(cluster_id="full_0")

        assert "error" not in result
        assert result["cluster_id"] == "full_0"
        assert result["axis"] == "full"
        assert "members" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_format(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid cluster_id format."""
        tool = tools["get_cluster_members"]
        result = await tool(cluster_id="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid cluster_id format" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_axis(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid axis in cluster_id."""
        tool = tools["get_cluster_members"]
        result = await tool(cluster_id="invalid_0")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_get_cluster_members_invalid_limit(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid limit."""
        tool = tools["get_cluster_members"]
        result = await tool(cluster_id="full_0", limit=0)

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 100" in result["error"]["message"]


class TestValidateValue:
    """Tests for validate_value tool."""

    @pytest.mark.asyncio
    async def test_validate_value_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful value validation."""
        tool = tools["validate_value"]
        result = await tool(
            text="Always check assumptions first",
            cluster_id="strategy_0",
        )

        assert "error" not in result
        assert "valid" in result
        assert "similarity" in result

    @pytest.mark.asyncio
    async def test_validate_value_empty_text(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for empty text."""
        tool = tools["validate_value"]
        result = await tool(
            text="",
            cluster_id="strategy_0",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "cannot be empty" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_validate_value_text_too_long(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for text exceeding limit."""
        tool = tools["validate_value"]
        result = await tool(
            text="x" * 501,
            cluster_id="strategy_0",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "500 character limit" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_validate_value_invalid_cluster_id(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid cluster_id."""
        tool = tools["validate_value"]
        result = await tool(
            text="Test value",
            cluster_id="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"


class TestStoreValue:
    """Tests for store_value tool."""

    @pytest.mark.asyncio
    async def test_store_value_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful value storage."""
        tool = tools["store_value"]
        result = await tool(
            text="Always check assumptions first",
            cluster_id="strategy_0",
            axis="strategy",
        )

        assert "error" not in result
        assert result["id"] is not None
        assert "text" in result  # Text is returned from stored value
        assert result["axis"] == "strategy"
        assert result["cluster_id"] == "strategy_0"

    @pytest.mark.asyncio
    async def test_store_value_empty_text(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for empty text."""
        tool = tools["store_value"]
        result = await tool(
            text="",
            cluster_id="strategy_0",
            axis="strategy",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "cannot be empty" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_store_value_invalid_axis(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid axis."""
        tool = tools["store_value"]
        result = await tool(
            text="Test value",
            cluster_id="invalid_0",
            axis="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]


class TestListValues:
    """Tests for list_values tool."""

    @pytest.mark.asyncio
    async def test_list_values_default(
        self, tools: dict[str, Any]
    ) -> None:
        """Test listing values with default parameters."""
        tool = tools["list_values"]
        result = await tool()

        assert "error" not in result
        assert "results" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_list_values_with_axis_filter(
        self, tools: dict[str, Any]
    ) -> None:
        """Test listing values with axis filter."""
        tool = tools["list_values"]
        result = await tool(axis="strategy")

        assert "error" not in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_list_values_invalid_axis(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid axis."""
        tool = tools["list_values"]
        result = await tool(axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_list_values_invalid_limit(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid limit."""
        tool = tools["list_values"]
        result = await tool(limit=101)

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 100" in result["error"]["message"]
