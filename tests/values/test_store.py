"""Unit tests for ValueStore with mocked dependencies."""

from unittest.mock import AsyncMock

import numpy as np
import pytest

from learning_memory_server.storage.base import SearchResult
from learning_memory_server.values import (
    ClusterInfo,
    ValueStore,
)


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service that returns fixed embeddings."""
    service = AsyncMock()
    # Return a normalized vector close to [1, 0]
    service.embed.return_value = np.array([0.95, 0.31], dtype=np.float32)
    service.dimension = 2
    return service


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_clusterer():
    """Mock clusterer with test clusters."""
    clusterer = AsyncMock()

    # Mock cluster_axis to return test clusters
    clusterer.cluster_axis.return_value = [
        ClusterInfo(
            cluster_id="full_0",
            axis="full",
            label=0,
            centroid=np.array([1.0, 0.0], dtype=np.float32),
            member_ids=["exp_1", "exp_2", "exp_3"],
            size=3,
            avg_weight=0.9,
        ),
        ClusterInfo(
            cluster_id="full_1",
            axis="full",
            label=1,
            centroid=np.array([0.0, 1.0], dtype=np.float32),
            member_ids=["exp_4", "exp_5"],
            size=2,
            avg_weight=0.8,
        ),
    ]
    return clusterer


@pytest.fixture
def value_store(mock_embedding_service, mock_vector_store, mock_clusterer):
    """Create a ValueStore with mocked dependencies."""
    return ValueStore(mock_embedding_service, mock_vector_store, mock_clusterer)


class TestGetClusters:
    """Tests for get_clusters method."""

    async def test_valid_axis(self, value_store, mock_clusterer):
        """Test getting clusters for valid axis."""
        clusters = await value_store.get_clusters("full")

        assert len(clusters) == 2
        assert clusters[0].cluster_id == "full_0"
        assert clusters[0].size == 3
        mock_clusterer.cluster_axis.assert_called_once_with("full")

    async def test_sorted_by_size_descending(self, value_store):
        """Test that clusters are sorted by size in descending order."""
        clusters = await value_store.get_clusters("full")

        # Should be sorted: size 3, then size 2
        assert clusters[0].size == 3
        assert clusters[1].size == 2

    async def test_invalid_axis(self, value_store):
        """Test that invalid axis raises ValueError."""
        with pytest.raises(ValueError, match="Invalid axis"):
            await value_store.get_clusters("invalid_axis")

    async def test_domain_not_valid_axis(self, value_store):
        """Test that 'domain' is not accepted as an axis."""
        with pytest.raises(ValueError, match="Invalid axis"):
            await value_store.get_clusters("domain")

    @pytest.mark.parametrize("axis", ["full", "strategy", "surprise", "root_cause"])
    async def test_all_valid_axes(self, value_store, axis):
        """Test all valid axes are accepted."""
        # Just verify no exception is raised
        await value_store.get_clusters(axis)


class TestGetClusterMembers:
    """Tests for get_cluster_members method."""

    async def test_get_members_success(self, value_store, mock_vector_store):
        """Test getting cluster members successfully."""
        # Mock vector store to return experiences
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"content": "test1", "confidence_weight": 0.9},
                vector=np.array([0.98, 0.2], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"content": "test2", "confidence_weight": 0.85},
                vector=np.array([0.96, 0.28], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"content": "test3", "confidence_weight": 0.95},
                vector=np.array([0.99, 0.14], dtype=np.float32),
            ),
        ]

        members = await value_store.get_cluster_members("full_0")

        assert len(members) == 3
        assert members[0].id == "exp_1"
        assert members[0].weight == 0.9
        assert members[1].weight == 0.85
        assert members[2].weight == 0.95
        assert isinstance(members[0].embedding, np.ndarray)

    async def test_invalid_cluster_id_format(self, value_store):
        """Test that malformed cluster_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cluster_id format"):
            await value_store.get_cluster_members("invalid")

    async def test_invalid_axis_in_cluster_id(self, value_store):
        """Test that invalid axis in cluster_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid axis in cluster_id"):
            await value_store.get_cluster_members("invalid_axis_0")

    async def test_cluster_not_found(self, value_store):
        """Test that non-existent cluster raises ValueError."""
        with pytest.raises(ValueError, match="Cluster not found"):
            await value_store.get_cluster_members("full_999")

    async def test_correct_collection_name(self, value_store, mock_vector_store):
        """Test that correct collection name is used."""
        mock_vector_store.get.return_value = SearchResult(
            id="exp_1",
            score=0.0,
            payload={"content": "test", "confidence_weight": 1.0},
            vector=np.array([1.0, 0.0], dtype=np.float32),
        )

        await value_store.get_cluster_members("full_0")

        # Check that get was called with correct collection
        calls = mock_vector_store.get.call_args_list
        for call in calls:
            assert call[1]["collection"] == "ghap_full"


class TestValidateValueCandidate:
    """Tests for validate_value_candidate method."""

    async def test_valid_candidate_close_to_centroid(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that candidate close to centroid passes validation."""
        # Mock embedding very close to centroid [1, 0]
        mock_embedding_service.embed.return_value = np.array(
            [0.99, 0.14], dtype=np.float32
        )

        # Mock cluster members
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.96, 0.28], dtype=np.float32),
            ),
        ]

        result = await value_store.validate_value_candidate(
            text="Test value", cluster_id="full_0"
        )

        assert result.valid is True
        assert result.similarity is not None
        assert result.similarity > 0.9
        assert result.candidate_distance is not None
        assert result.mean_distance is not None
        assert result.std_distance is not None
        assert result.threshold is not None

    async def test_invalid_candidate_far_from_centroid(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that candidate far from centroid fails validation."""
        # Mock embedding far from centroid [1, 0] - use opposite direction [0, 1]
        mock_embedding_service.embed.return_value = np.array(
            [0.0, 1.0], dtype=np.float32
        )

        # Mock cluster members close to centroid
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.99, 0.14], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
        ]

        result = await value_store.validate_value_candidate(
            text="Test value", cluster_id="full_0"
        )

        assert result.valid is False
        assert result.reason is not None
        assert "too far from centroid" in result.reason
        assert result.candidate_distance is not None
        assert result.threshold is not None

    async def test_empty_cluster(self, value_store, mock_clusterer, mock_vector_store):
        """Test validation with empty cluster."""
        # Create a cluster with no members
        mock_clusterer.cluster_axis.return_value = [
            ClusterInfo(
                cluster_id="full_0",
                axis="full",
                label=0,
                centroid=np.array([1.0, 0.0], dtype=np.float32),
                member_ids=[],
                size=0,
                avg_weight=0.0,
            )
        ]

        result = await value_store.validate_value_candidate(
            text="Test value", cluster_id="full_0"
        )

        assert result.valid is False
        assert result.reason == "Cluster has no members"

    async def test_validation_threshold_calculation(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that threshold is calculated as mean + 0.5 * std."""
        mock_embedding_service.embed.return_value = np.array(
            [0.9, 0.44], dtype=np.float32
        )

        # Mock members with known distances to centroid [1, 0]
        # These vectors have specific cosine distances
        # Note: full_0 has 3 members (exp_1, exp_2, exp_3)
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 1.0},
                vector=np.array([0.8, 0.6], dtype=np.float32),  # distance ~0.4
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 1.0},
                vector=np.array([0.6, 0.8], dtype=np.float32),  # distance ~0.6
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 1.0},
                vector=np.array([0.7, 0.71], dtype=np.float32),  # distance ~0.5
            ),
        ]

        result = await value_store.validate_value_candidate(
            text="Test value", cluster_id="full_0"
        )

        # Verify threshold = mean + 0.5 * std
        assert result.mean_distance is not None
        assert result.std_distance is not None
        assert result.threshold is not None
        expected_threshold = result.mean_distance + 0.5 * result.std_distance
        assert abs(result.threshold - expected_threshold) < 1e-6


class TestStoreValue:
    """Tests for store_value method."""

    async def test_store_valid_value(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test storing a valid value."""
        # Mock validation will pass
        mock_embedding_service.embed.return_value = np.array(
            [0.99, 0.14], dtype=np.float32
        )
        mock_vector_store.get.side_effect = [
            # For validation
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.96, 0.28], dtype=np.float32),
            ),
        ]

        value = await value_store.store_value(
            text="Test principle", cluster_id="full_0", axis="full"
        )

        assert value.id.startswith("value_full_0_")
        assert value.text == "Test principle"
        assert value.cluster_id == "full_0"
        assert value.axis == "full"
        assert value.cluster_size == 3
        assert isinstance(value.created_at, str)
        assert "validation" in value.metadata or value.metadata != {}

        # Verify upsert was called
        mock_vector_store.upsert.assert_called_once()
        call_args = mock_vector_store.upsert.call_args
        assert call_args[1]["collection"] == "values"
        assert call_args[1]["id"].startswith("value_full_0_")
        assert call_args[1]["payload"]["text"] == "Test principle"

    async def test_store_invalid_value_raises_error(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that storing invalid value raises ValueError."""
        # Mock embedding far from centroid to fail validation
        mock_embedding_service.embed.return_value = np.array(
            [0.0, 1.0], dtype=np.float32
        )
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.99, 0.14], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
        ]

        with pytest.raises(ValueError, match="Value failed validation"):
            await value_store.store_value(
                text="Bad principle", cluster_id="full_0", axis="full"
            )

        # Verify upsert was NOT called
        mock_vector_store.upsert.assert_not_called()

    async def test_value_id_format(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that value ID has correct format."""
        mock_embedding_service.embed.return_value = np.array(
            [0.99, 0.14], dtype=np.float32
        )
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.96, 0.28], dtype=np.float32),
            ),
        ]

        value = await value_store.store_value(
            text="Test principle", cluster_id="full_0", axis="full"
        )

        # ID format: value_{axis}_{cluster_label}_{uuid8}
        parts = value.id.split("_")
        assert parts[0] == "value"
        assert parts[1] == "full"
        assert parts[2] == "0"
        assert len(parts[3]) == 8  # 8-char UUID hex

    async def test_stored_payload_structure(
        self, value_store, mock_embedding_service, mock_vector_store
    ):
        """Test that stored payload has correct structure."""
        mock_embedding_service.embed.return_value = np.array(
            [0.99, 0.14], dtype=np.float32
        )
        mock_vector_store.get.side_effect = [
            SearchResult(
                id="exp_1",
                score=0.0,
                payload={"confidence_weight": 0.9},
                vector=np.array([0.98, 0.20], dtype=np.float32),
            ),
            SearchResult(
                id="exp_2",
                score=0.0,
                payload={"confidence_weight": 0.85},
                vector=np.array([0.97, 0.24], dtype=np.float32),
            ),
            SearchResult(
                id="exp_3",
                score=0.0,
                payload={"confidence_weight": 0.95},
                vector=np.array([0.96, 0.28], dtype=np.float32),
            ),
        ]

        await value_store.store_value(
            text="Test principle", cluster_id="full_0", axis="full"
        )

        # Check upsert was called with correct payload structure
        call_args = mock_vector_store.upsert.call_args
        payload = call_args[1]["payload"]

        assert payload["text"] == "Test principle"
        assert payload["cluster_id"] == "full_0"
        assert payload["axis"] == "full"
        assert payload["cluster_label"] == 0
        assert payload["cluster_size"] == 3
        assert "created_at" in payload
        assert "validation" in payload
        assert "candidate_distance" in payload["validation"]
        assert "mean_distance" in payload["validation"]
        assert "threshold" in payload["validation"]
        assert "similarity" in payload["validation"]


class TestListValues:
    """Tests for list_values method."""

    async def test_list_all_values(self, value_store, mock_vector_store):
        """Test listing all values without filter."""
        # Mock scroll to return values
        mock_vector_store.scroll.return_value = [
            SearchResult(
                id="value_full_0_abc123",
                score=0.0,
                payload={
                    "text": "Value 1",
                    "cluster_id": "full_0",
                    "axis": "full",
                    "cluster_size": 3,
                    "created_at": "2024-01-01T10:00:00+00:00",
                    "validation": {"similarity": 0.95},
                },
                vector=np.array([1.0, 0.0], dtype=np.float32),
            ),
            SearchResult(
                id="value_strategy_1_def456",
                score=0.0,
                payload={
                    "text": "Value 2",
                    "cluster_id": "strategy_1",
                    "axis": "strategy",
                    "cluster_size": 5,
                    "created_at": "2024-01-01T11:00:00+00:00",
                    "validation": {"similarity": 0.90},
                },
                vector=np.array([0.0, 1.0], dtype=np.float32),
            ),
        ]

        values = await value_store.list_values()

        assert len(values) == 2
        # Should be sorted by created_at descending (newest first)
        assert values[0].text == "Value 2"
        assert values[1].text == "Value 1"
        mock_vector_store.scroll.assert_called_once()

    async def test_list_values_filtered_by_axis(self, value_store, mock_vector_store):
        """Test listing values filtered by axis."""
        mock_vector_store.scroll.return_value = [
            SearchResult(
                id="value_full_0_abc123",
                score=0.0,
                payload={
                    "text": "Full value",
                    "cluster_id": "full_0",
                    "axis": "full",
                    "cluster_size": 3,
                    "created_at": "2024-01-01T10:00:00+00:00",
                    "validation": {},
                },
                vector=np.array([1.0, 0.0], dtype=np.float32),
            )
        ]

        values = await value_store.list_values(axis="full")

        assert len(values) == 1
        assert values[0].axis == "full"

        # Verify scroll was called with axis filter
        call_args = mock_vector_store.scroll.call_args
        assert call_args[1]["filters"] == {"axis": "full"}

    async def test_list_values_invalid_axis(self, value_store):
        """Test that invalid axis raises ValueError."""
        with pytest.raises(ValueError, match="Invalid axis"):
            await value_store.list_values(axis="invalid_axis")

    async def test_list_values_sorted_by_recency(self, value_store, mock_vector_store):
        """Test that values are sorted by created_at descending."""
        mock_vector_store.scroll.return_value = [
            SearchResult(
                id="value_1",
                score=0.0,
                payload={
                    "text": "Oldest",
                    "cluster_id": "full_0",
                    "axis": "full",
                    "cluster_size": 3,
                    "created_at": "2024-01-01T08:00:00+00:00",
                    "validation": {},
                },
                vector=np.array([1.0, 0.0], dtype=np.float32),
            ),
            SearchResult(
                id="value_2",
                score=0.0,
                payload={
                    "text": "Newest",
                    "cluster_id": "full_1",
                    "axis": "full",
                    "cluster_size": 2,
                    "created_at": "2024-01-01T12:00:00+00:00",
                    "validation": {},
                },
                vector=np.array([0.0, 1.0], dtype=np.float32),
            ),
            SearchResult(
                id="value_3",
                score=0.0,
                payload={
                    "text": "Middle",
                    "cluster_id": "full_2",
                    "axis": "full",
                    "cluster_size": 4,
                    "created_at": "2024-01-01T10:00:00+00:00",
                    "validation": {},
                },
                vector=np.array([0.5, 0.5], dtype=np.float32),
            ),
        ]

        values = await value_store.list_values()

        # Should be sorted newest to oldest
        assert values[0].text == "Newest"
        assert values[1].text == "Middle"
        assert values[2].text == "Oldest"


class TestGetCluster:
    """Tests for _get_cluster internal method."""

    async def test_get_cluster_success(self, value_store):
        """Test getting a cluster by ID."""
        cluster = await value_store._get_cluster("full_0")

        assert cluster.cluster_id == "full_0"
        assert cluster.axis == "full"
        assert cluster.label == 0

    async def test_get_cluster_invalid_format(self, value_store):
        """Test that invalid cluster_id format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cluster_id format"):
            await value_store._get_cluster("invalid")

    async def test_get_cluster_not_found(self, value_store):
        """Test that non-existent cluster raises ValueError."""
        with pytest.raises(ValueError, match="Cluster not found"):
            await value_store._get_cluster("full_999")
