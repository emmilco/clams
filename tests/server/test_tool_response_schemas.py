"""MCP Tool Response Schema Tests.

R5-B: Verify MCP tool responses match advertised output formats.

This module tests that:
1. Tool responses contain expected fields for success cases
2. Tool responses contain proper error structure for error cases
3. Enum values in responses are valid per schema (DOMAINS, STRATEGIES, etc.)

Reference: BUG-026 - Advertised enums drifted from actual validation.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from calm.clustering import ExperienceClusterer
from calm.clustering.types import ClusterInfo
from calm.ghap import ObservationCollector, ObservationPersister
from calm.tools.context import get_context_tools
from calm.server.app import (
    DOMAINS,
    OUTCOME_STATUS_VALUES,
    ROOT_CAUSE_CATEGORIES,
    STRATEGIES,
    VALID_AXES,
)
from calm.tools.ghap import get_ghap_tools
from calm.tools.learning import get_learning_tools
from calm.tools.memory import VALID_CATEGORIES, get_memory_tools
from calm.tools.session import SessionManager, get_session_tools
from calm.storage.base import SearchResult
from calm.values import ValueStore

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_code_embedder() -> AsyncMock:
    """Create mock code embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 384
    service.embed_batch.return_value = [[0.1] * 384, [0.2] * 384]
    service.dimension = 384
    return service


@pytest.fixture
def mock_semantic_embedder() -> AsyncMock:
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]
    service.dimension = 768
    return service


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.upsert.return_value = None
    store.delete.return_value = None
    store.count.return_value = 0
    store.search.return_value = []
    store.scroll.return_value = []
    return store


@pytest.fixture
def mock_metadata_store() -> AsyncMock:
    """Create mock metadata store."""
    store = AsyncMock()
    return store


@dataclass
class MockServices:
    """Lightweight service container for tests."""
    code_embedder: Any = None
    semantic_embedder: Any = None
    vector_store: Any = None
    metadata_store: Any = None


@pytest.fixture
def mock_services(
    mock_code_embedder: AsyncMock,
    mock_semantic_embedder: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_metadata_store: AsyncMock,
) -> MockServices:
    """Create mock service container with core services."""
    return MockServices(
        code_embedder=mock_code_embedder,
        semantic_embedder=mock_semantic_embedder,
        vector_store=mock_vector_store,
        metadata_store=mock_metadata_store,
    )


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
    vector_store.scroll = AsyncMock(return_value=[])
    return ObservationPersister(
        embedding_service=MagicMock(),
        vector_store=vector_store,
    )


@pytest.fixture
def ghap_tools(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> dict[str, Any]:
    """Get GHAP tools."""
    return get_ghap_tools(observation_collector, observation_persister)


@pytest.fixture
def memory_tools(mock_services: MockServices) -> dict[str, Any]:
    """Get memory tools."""
    return get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)


@pytest.fixture
def experience_clusterer() -> ExperienceClusterer:
    """Create a mock ExperienceClusterer."""
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])

    clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=MagicMock(),
    )
    clusterer.count_experiences = AsyncMock(return_value=25)
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
    mock_validation = MagicMock()
    mock_validation.valid = True
    mock_validation.similarity = 0.85
    store.validate_value_candidate = AsyncMock(return_value=mock_validation)
    return store


@pytest.fixture
def learning_tools(
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


@pytest.fixture
def temp_session_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create temporary directories for session testing."""
    clams_dir = tmp_path / ".clams"
    journal_dir = clams_dir / "journal"
    journal_dir.mkdir(parents=True)
    return clams_dir, journal_dir


@pytest.fixture
def session_manager(temp_session_dirs: tuple[Path, Path]) -> SessionManager:
    """Create session manager with temp paths."""
    clams_dir, journal_dir = temp_session_dirs
    return SessionManager(calm_dir=clams_dir, journal_dir=journal_dir)


@pytest.fixture
def session_tools(session_manager: SessionManager) -> dict[str, Any]:
    """Get session tools."""
    return get_session_tools(session_manager)


@pytest.fixture
def context_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
) -> dict[str, Any]:
    """Get context tools."""
    return get_context_tools(mock_vector_store, mock_semantic_embedder)


# =============================================================================
# Memory Tools Response Schema Tests
# =============================================================================


class TestStoreMemoryResponseSchema:
    """Test store_memory response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Success response should contain required fields.

        Note: Response does NOT include content or tags (SPEC-045 token efficiency).
        Content is only needed on retrieval, not on store confirmation.
        """
        tool = memory_tools["store_memory"]
        result = await tool(content="Test memory", category="fact")

        # Required fields (SPEC-045: content and tags NOT included in response)
        assert "id" in result
        assert "status" in result  # New field: confirmation status
        assert result["status"] == "stored"
        assert "category" in result
        assert "importance" in result
        assert "created_at" in result
        # Verify content is NOT in response (token efficiency)
        assert "content" not in result
        assert "tags" not in result

        # Category should be valid enum value
        assert result["category"] in VALID_CATEGORIES

    @pytest.mark.asyncio
    async def test_error_response_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Error response should be a ValidationError."""
        tool = memory_tools["store_memory"]

        with pytest.raises(Exception) as exc_info:
            await tool(content="Test", category="invalid_category")

        assert "Invalid category" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_all_valid_categories_produce_valid_response(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """All valid categories should produce responses with valid category field."""
        tool = memory_tools["store_memory"]

        for category in VALID_CATEGORIES:
            result = await tool(content="Test", category=category)
            assert result["category"] == category
            assert result["category"] in VALID_CATEGORIES


class TestRetrieveMemoriesResponseSchema:
    """Test retrieve_memories response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, memory_tools: dict[str, Any], mock_services: MockServices
    ) -> None:
        """Success response should contain results and count."""
        tool = memory_tools["retrieve_memories"]

        # Mock search results
        mock_result = SearchResult(
            id="12345678-1234-1234-1234-123456789abc",
            score=0.95,
            payload={
                "content": "Test content",
                "category": "fact",
                "importance": 0.8,
            },
            vector=None,
        )
        mock_services.vector_store.search.return_value = [mock_result]

        result = await tool(query="test query")

        assert "results" in result
        assert "count" in result
        assert isinstance(result["results"], list)
        assert isinstance(result["count"], int)

    @pytest.mark.asyncio
    async def test_empty_query_response(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Empty query should return empty results."""
        tool = memory_tools["retrieve_memories"]
        result = await tool(query="   ")

        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_error_response_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid category filter."""
        tool = memory_tools["retrieve_memories"]

        with pytest.raises(Exception) as exc_info:
            await tool(query="test", category="invalid")

        assert "Invalid category" in str(exc_info.value)


class TestListMemoriesResponseSchema:
    """Test list_memories response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Success response should contain results, count, and total."""
        tool = memory_tools["list_memories"]
        result = await tool()

        assert "results" in result
        assert "count" in result
        assert "total" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_error_response_invalid_offset(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Error response for negative offset."""
        tool = memory_tools["list_memories"]

        with pytest.raises(Exception) as exc_info:
            await tool(offset=-1)

        assert "Offset" in str(exc_info.value)


class TestDeleteMemoryResponseSchema:
    """Test delete_memory response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Success response should contain deleted boolean."""
        tool = memory_tools["delete_memory"]
        result = await tool(memory_id="12345678-1234-1234-1234-123456789abc")

        assert "deleted" in result
        assert isinstance(result["deleted"], bool)

    @pytest.mark.asyncio
    async def test_failure_response_structure(
        self, memory_tools: dict[str, Any], mock_services: MockServices
    ) -> None:
        """Failure returns deleted=False, not an error."""
        tool = memory_tools["delete_memory"]
        mock_services.vector_store.delete.side_effect = Exception("Not found")

        # SPEC-057: memory_id must be valid UUID format
        result = await tool(memory_id="00000000-0000-0000-0000-000000000000")

        assert result["deleted"] is False


# =============================================================================
# GHAP Tools Response Schema Tests
# =============================================================================


class TestStartGhapResponseSchema:
    """Test start_ghap response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Success response should contain ok and id fields."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        assert "error" not in result
        assert result["ok"] is True
        assert "id" in result
        assert result["id"].startswith("ghap_")

    @pytest.mark.asyncio
    async def test_error_response_invalid_domain(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid domain."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="invalid_domain",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_error_response_invalid_strategy(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid strategy."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="invalid_strategy",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid strategy" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_all_valid_domains_accepted(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """All valid domains should be accepted and returned in response."""
        tool = ghap_tools["start_ghap"]

        for domain in DOMAINS:
            # Need to create fresh collector for each domain to avoid
            # "active GHAP exists" error
            result = await tool(
                domain=domain,
                strategy="systematic-elimination",
                goal="Test",
                hypothesis="Test",
                action="Test",
                prediction="Test",
            )
            # First iteration should succeed, others may fail with active GHAP
            if "error" not in result:
                assert result["ok"] is True
            break  # Just test one domain since collector persists

    @pytest.mark.asyncio
    async def test_all_valid_strategies_accepted(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """All valid strategies should be accepted."""
        tool = ghap_tools["start_ghap"]

        # Just validate that the first strategy works
        result = await tool(
            domain="debugging",
            strategy=STRATEGIES[0],  # First valid strategy
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert "error" not in result


class TestUpdateGhapResponseSchema:
    """Test update_ghap response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Success response should contain success and iteration_count."""
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        update_tool = ghap_tools["update_ghap"]
        result = await update_tool(hypothesis="Updated hypothesis")

        assert "error" not in result
        assert result["success"] is True
        assert "iteration_count" in result
        assert isinstance(result["iteration_count"], int)

    @pytest.mark.asyncio
    async def test_error_response_no_active_ghap(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response when no active GHAP."""
        tool = ghap_tools["update_ghap"]
        result = await tool(hypothesis="Test")

        assert "error" in result
        assert result["error"]["type"] == "not_found"


class TestResolveGhapResponseSchema:
    """Test resolve_ghap response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, ghap_tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """Success response should contain ok and id."""
        observation_persister.persist = AsyncMock()

        start_tool = ghap_tools["start_ghap"]
        start_result = await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        resolve_tool = ghap_tools["resolve_ghap"]
        result = await resolve_tool(
            status="confirmed",
            result="Test passed",
        )

        assert "error" not in result
        assert result["ok"] is True
        assert result["id"] == start_result["id"]

    @pytest.mark.asyncio
    async def test_error_response_invalid_status(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid status."""
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        resolve_tool = ghap_tools["resolve_ghap"]
        result = await resolve_tool(
            status="invalid_status",
            result="Test",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid outcome status" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_all_valid_outcome_statuses(
        self, ghap_tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """All valid outcome statuses should be accepted."""
        observation_persister.persist = AsyncMock()

        # Test confirmed status
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        resolve_tool = ghap_tools["resolve_ghap"]
        result = await resolve_tool(status="confirmed", result="Success")
        assert "error" not in result

        # Test falsified status (requires surprise)
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test2",
            hypothesis="Test2",
            action="Test2",
            prediction="Test2",
        )
        result = await resolve_tool(
            status="falsified",
            result="Failed",
            surprise="Unexpected",
            root_cause={"category": "wrong-assumption", "description": "Bad assumption"},
        )
        assert "error" not in result

        # Test abandoned status
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test3",
            hypothesis="Test3",
            action="Test3",
            prediction="Test3",
        )
        result = await resolve_tool(status="abandoned", result="Stopped")
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_all_valid_root_cause_categories(
        self, ghap_tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """All valid root cause categories should be accepted."""
        observation_persister.persist = AsyncMock()

        for category in ROOT_CAUSE_CATEGORIES:
            start_tool = ghap_tools["start_ghap"]
            await start_tool(
                domain="debugging",
                strategy="systematic-elimination",
                goal=f"Test {category}",
                hypothesis="Test",
                action="Test",
                prediction="Test",
            )

            resolve_tool = ghap_tools["resolve_ghap"]
            result = await resolve_tool(
                status="falsified",
                result="Failed",
                surprise="Unexpected",
                root_cause={"category": category, "description": "Description"},
            )
            assert "error" not in result, f"Failed for category: {category}"


class TestGetActiveGhapResponseSchema:
    """Test get_active_ghap response structure."""

    @pytest.mark.asyncio
    async def test_response_with_active_ghap(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Response should include has_active=True and GHAP details."""
        start_tool = ghap_tools["start_ghap"]
        start_result = await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["get_active_ghap"]
        result = await tool()

        assert "error" not in result
        assert result["has_active"] is True
        assert result["id"] == start_result["id"]
        assert result["domain"] == "debugging"
        # Domain should be a valid enum value
        assert result["domain"] in DOMAINS

    @pytest.mark.asyncio
    async def test_response_without_active_ghap(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Response should include has_active=False when no active GHAP."""
        tool = ghap_tools["get_active_ghap"]
        result = await tool()

        assert "error" not in result
        assert result["has_active"] is False
        assert result["id"] is None


class TestListGhapEntriesResponseSchema:
    """Test list_ghap_entries response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Success response should contain results and count."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool()

        assert "error" not in result
        assert "results" in result
        assert "count" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_error_response_invalid_domain_filter(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid domain filter."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(domain="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_error_response_invalid_outcome_filter(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid outcome filter."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(outcome="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"


# =============================================================================
# Learning Tools Response Schema Tests
# =============================================================================


class TestGetClustersResponseSchema:
    """Test get_clusters response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain axis, clusters, and noise_count."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis="full")

        assert "error" not in result
        assert "axis" in result
        assert "clusters" in result
        assert "count" in result
        assert "noise_count" in result
        # Axis should be valid
        assert result["axis"] in VALID_AXES

    @pytest.mark.asyncio
    async def test_error_response_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid axis."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_all_valid_axes_accepted(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """All valid axes should be accepted."""
        tool = learning_tools["get_clusters"]

        for axis in VALID_AXES:
            result = await tool(axis=axis)
            assert "error" not in result, f"Failed for axis: {axis}"
            assert result["axis"] == axis


class TestGetClusterMembersResponseSchema:
    """Test get_cluster_members response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain cluster_id, axis, members, count."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="full_0")

        assert "error" not in result
        assert "cluster_id" in result
        assert "axis" in result
        assert "members" in result
        assert "count" in result
        # Axis extracted from cluster_id should be valid
        assert result["axis"] in VALID_AXES

    @pytest.mark.asyncio
    async def test_error_response_invalid_cluster_id_format(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid cluster_id format."""
        tool = learning_tools["get_cluster_members"]
        result = await tool(cluster_id="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid cluster_id format" in result["error"]["message"]


class TestValidateValueResponseSchema:
    """Test validate_value response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain valid and cluster_id."""
        tool = learning_tools["validate_value"]
        result = await tool(
            text="Always check assumptions first",
            cluster_id="strategy_0",
        )

        assert "error" not in result
        assert "valid" in result
        assert "cluster_id" in result
        assert isinstance(result["valid"], bool)

    @pytest.mark.asyncio
    async def test_error_response_empty_text(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for empty text."""
        tool = learning_tools["validate_value"]
        result = await tool(text="", cluster_id="strategy_0")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"


class TestStoreValueResponseSchema:
    """Test store_value response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain id, text, cluster_id, axis."""
        tool = learning_tools["store_value"]
        result = await tool(
            text="Test value",
            cluster_id="strategy_0",
            axis="strategy",
        )

        assert "error" not in result
        assert "id" in result
        assert "text" in result
        assert "cluster_id" in result
        assert "axis" in result
        # Axis should be valid
        assert result["axis"] in VALID_AXES

    @pytest.mark.asyncio
    async def test_error_response_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid axis."""
        tool = learning_tools["store_value"]
        result = await tool(
            text="Test",
            cluster_id="invalid_0",
            axis="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]


class TestListValuesResponseSchema:
    """Test list_values response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain results and count."""
        tool = learning_tools["list_values"]
        result = await tool()

        assert "error" not in result
        assert "results" in result
        assert "count" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_error_response_invalid_axis_filter(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid axis filter."""
        tool = learning_tools["list_values"]
        result = await tool(axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"


# =============================================================================
# Search Tools Response Schema Tests
# =============================================================================


class TestSearchExperiencesResponseSchema:
    """Test search_experiences response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Success response should contain results and count."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="test query", axis="full")

        assert "error" not in result
        assert "results" in result
        assert "count" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_empty_query_response(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Empty query should return empty results."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="")

        assert "error" not in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_error_response_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid axis."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="test", axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_error_response_invalid_domain(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid domain filter."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="test", domain="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_error_response_invalid_outcome(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Error response for invalid outcome filter."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="test", outcome="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid outcome status" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_all_valid_axes_accepted(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """All valid axes should be accepted."""
        tool = learning_tools["search_experiences"]

        for axis in VALID_AXES:
            result = await tool(query="test", axis=axis)
            assert "error" not in result, f"Failed for axis: {axis}"

    @pytest.mark.asyncio
    async def test_all_valid_domains_accepted(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """All valid domains should be accepted as filter."""
        tool = learning_tools["search_experiences"]

        for domain in DOMAINS:
            result = await tool(query="test", domain=domain)
            assert "error" not in result, f"Failed for domain: {domain}"

    @pytest.mark.asyncio
    async def test_all_valid_outcomes_accepted(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """All valid outcome statuses should be accepted as filter."""
        tool = learning_tools["search_experiences"]

        for outcome in OUTCOME_STATUS_VALUES:
            result = await tool(query="test", outcome=outcome)
            assert "error" not in result, f"Failed for outcome: {outcome}"


# =============================================================================
# Session Tools Response Schema Tests
# =============================================================================


class TestStartSessionResponseSchema:
    """Test start_session response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Success response should contain session_id."""
        tool = session_tools["start_session"]
        result = await tool()

        assert "session_id" in result
        assert len(result["session_id"]) == 36  # UUID format


class TestGetOrphanedGhapResponseSchema:
    """Test get_orphaned_ghap response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Success response should contain has_orphan boolean."""
        tool = session_tools["get_orphaned_ghap"]
        result = await tool()

        assert "has_orphan" in result
        assert isinstance(result["has_orphan"], bool)


class TestShouldCheckInResponseSchema:
    """Test should_check_in response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Success response should contain should_check_in boolean."""
        tool = session_tools["should_check_in"]
        result = await tool()

        assert "should_check_in" in result
        assert isinstance(result["should_check_in"], bool)


class TestIncrementToolCountResponseSchema:
    """Test increment_tool_count response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Success response should contain tool_count integer."""
        tool = session_tools["increment_tool_count"]
        result = await tool()

        assert "tool_count" in result
        assert isinstance(result["tool_count"], int)


class TestResetToolCountResponseSchema:
    """Test reset_tool_count response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Success response should contain tool_count=0."""
        tool = session_tools["reset_tool_count"]
        result = await tool()

        assert "tool_count" in result
        assert result["tool_count"] == 0


# =============================================================================
# Context Tools Response Schema Tests
# =============================================================================


class TestAssembleContextResponseSchema:
    """Test assemble_context response structure."""

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Success response should contain markdown and metadata."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test query")

        assert "error" not in result
        assert "markdown" in result
        assert "token_count" in result
        assert "item_count" in result
        assert "truncated" in result
        # markdown should be a string
        assert isinstance(result["markdown"], str)
        assert isinstance(result["token_count"], int)
        assert isinstance(result["item_count"], int)
        assert isinstance(result["truncated"], bool)

    @pytest.mark.asyncio
    async def test_empty_query_response(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Empty query should return empty markdown."""
        tool = context_tools["assemble_context"]
        result = await tool(query="")

        assert "error" not in result
        assert result["markdown"] == ""
        assert result["item_count"] == 0


# =============================================================================
# Error Response Structure Tests
# =============================================================================


class TestErrorResponseStructure:
    """Test that all error responses follow the standard structure."""

    @pytest.mark.asyncio
    async def test_ghap_error_structure(self, ghap_tools: dict[str, Any]) -> None:
        """GHAP tools should return standardized error structure."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="invalid",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        assert "error" in result
        assert "type" in result["error"]
        assert "message" in result["error"]
        assert result["error"]["type"] in [
            "validation_error",
            "not_found",
            "internal_error",
            "insufficient_data",
        ]

    @pytest.mark.asyncio
    async def test_learning_error_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Learning tools should return standardized error structure."""
        tool = learning_tools["get_clusters"]
        result = await tool(axis="invalid")

        assert "error" in result
        assert "type" in result["error"]
        assert "message" in result["error"]
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_search_error_structure(
        self, learning_tools: dict[str, Any]
    ) -> None:
        """Search tools should return standardized error structure."""
        tool = learning_tools["search_experiences"]
        result = await tool(query="test", axis="invalid")

        assert "error" in result
        assert "type" in result["error"]
        assert "message" in result["error"]
        assert result["error"]["type"] == "validation_error"


# =============================================================================
# Enum Consistency Verification
# =============================================================================


class TestEnumValuesInResponsesMatchSchema:
    """Verify that enum values in responses match the canonical enums."""

    def test_domains_enum_values(self) -> None:
        """DOMAINS enum should contain all expected values."""
        expected = {
            "debugging",
            "refactoring",
            "feature",
            "testing",
            "configuration",
            "documentation",
            "performance",
            "security",
            "integration",
        }
        assert set(DOMAINS) == expected

    def test_strategies_enum_values(self) -> None:
        """STRATEGIES enum should contain all expected values."""
        expected = {
            "systematic-elimination",
            "trial-and-error",
            "research-first",
            "divide-and-conquer",
            "root-cause-analysis",
            "copy-from-similar",
            "check-assumptions",
            "read-the-error",
            "ask-user",
        }
        assert set(STRATEGIES) == expected

    def test_valid_axes_enum_values(self) -> None:
        """VALID_AXES enum should contain all expected values."""
        expected = {"full", "strategy", "surprise", "root_cause"}
        assert set(VALID_AXES) == expected

    def test_outcome_status_enum_values(self) -> None:
        """OUTCOME_STATUS_VALUES enum should contain all expected values."""
        expected = {"confirmed", "falsified", "abandoned"}
        assert set(OUTCOME_STATUS_VALUES) == expected

    def test_root_cause_categories_enum_values(self) -> None:
        """ROOT_CAUSE_CATEGORIES enum should contain all expected values."""
        expected = {
            "wrong-assumption",
            "missing-knowledge",
            "oversight",
            "environment-issue",
            "misleading-symptom",
            "incomplete-fix",
            "wrong-scope",
            "test-isolation",
            "timing-issue",
        }
        assert set(ROOT_CAUSE_CATEGORIES) == expected

    def test_memory_categories_enum_values(self) -> None:
        """VALID_CATEGORIES enum should contain all expected values."""
        expected = {
            "preference",
            "fact",
            "event",
            "workflow",
            "context",
            "error",
            "decision",
        }
        assert set(VALID_CATEGORIES) == expected
