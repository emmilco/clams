"""Regression test for BUG-043: Qdrant collections not auto-created on first use.

This test verifies that the `memories`, `commits`, and `values` collections
are automatically created when first accessed, preventing 404 errors.
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

import clams.server.tools.memory as memory_module
from clams.server.tools import ServiceContainer
from clams.server.tools.memory import get_memory_tools


@pytest.fixture
def fresh_vector_store() -> AsyncMock:
    """Vector store with no collections (fresh start)."""
    store = AsyncMock()
    store.create_collection = AsyncMock()
    store.upsert = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=[])
    store.count = AsyncMock(return_value=0)
    store.delete = AsyncMock()
    return store


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Mock embedding service."""
    embedder = MagicMock()
    embedder.dimension = 768
    embedder.embed = AsyncMock(return_value=[0.0] * 768)
    embedder.embed_batch = AsyncMock(return_value=[[0.0] * 768])
    return embedder


@pytest.fixture
def mock_services(fresh_vector_store: AsyncMock, mock_embedder: MagicMock) -> ServiceContainer:
    """Create ServiceContainer with fresh vector store."""
    return ServiceContainer(
        code_embedder=mock_embedder,
        semantic_embedder=mock_embedder,
        vector_store=fresh_vector_store,
        metadata_store=AsyncMock(),
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


class TestBug043MemoriesCollection:
    """Tests for auto-creation of memories collection."""

    @pytest.fixture(autouse=True)
    def reset_module_state(self) -> None:
        """Reset module-level state between tests."""
        # Reset the module-level flag before each test
        memory_module._memories_collection_ensured = False
        yield
        # Reset again after test
        memory_module._memories_collection_ensured = False

    @pytest.mark.asyncio
    async def test_store_memory_creates_collection(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that store_memory creates collection if it doesn't exist.

        Regression test for BUG-043: Collections should be auto-created on first use.
        """
        tools = get_memory_tools(mock_services)

        # Action: store a memory (should auto-create collection)
        result = await tools["store_memory"](
            content="Test memory content",
            category="fact",
        )

        # Assert: collection was created before upsert
        fresh_vector_store.create_collection.assert_called_once_with(
            name="memories",
            dimension=768,
            distance="cosine",
        )

        # Assert: memory was stored
        fresh_vector_store.upsert.assert_called_once()
        assert "id" in result
        # Note: store_memory no longer returns content in response (token efficiency)
        # See SPEC-045 for rationale - content is only needed on retrieval
        assert result["status"] == "stored"

    @pytest.mark.asyncio
    async def test_retrieve_memories_creates_collection(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that retrieve_memories creates collection if it doesn't exist."""
        tools = get_memory_tools(mock_services)

        # Action: retrieve memories (should auto-create collection)
        result = await tools["retrieve_memories"](query="test query", limit=10)

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="memories",
            dimension=768,
            distance="cosine",
        )

        # Assert: search returned results (empty list since no memories)
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_list_memories_creates_collection(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that list_memories creates collection if it doesn't exist."""
        tools = get_memory_tools(mock_services)

        # Action: list memories (should auto-create collection)
        result = await tools["list_memories"](limit=10)

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="memories",
            dimension=768,
            distance="cosine",
        )

        # Assert: list returned empty results
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_collection_created_only_once(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that collection is created only once (cached)."""
        tools = get_memory_tools(mock_services)

        # Call multiple operations
        await tools["store_memory"](content="Test 1", category="fact")
        await tools["store_memory"](content="Test 2", category="fact")
        await tools["retrieve_memories"](query="test", limit=10)
        await tools["list_memories"](limit=10)

        # Assert: create_collection was called only once
        assert fresh_vector_store.create_collection.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_already_exists_error(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that 'already exists' errors are handled gracefully."""
        # Simulate collection already exists error
        fresh_vector_store.create_collection.side_effect = Exception(
            "Collection 'memories' already exists"
        )

        tools = get_memory_tools(mock_services)

        # Should not raise, should continue normally
        result = await tools["store_memory"](
            content="Test memory",
            category="fact",
        )

        # Assert: memory was still stored
        fresh_vector_store.upsert.assert_called_once()
        # Note: store_memory no longer returns content (SPEC-045 token efficiency)
        assert result["status"] == "stored"

    @pytest.mark.asyncio
    async def test_handles_409_error(
        self,
        mock_services: ServiceContainer,
        fresh_vector_store: AsyncMock,
    ) -> None:
        """Test that 409 conflict errors are handled gracefully."""
        # Simulate 409 error (Qdrant conflict)
        fresh_vector_store.create_collection.side_effect = Exception(
            "409: Conflict - collection exists"
        )

        tools = get_memory_tools(mock_services)

        # Should not raise, should continue normally
        await tools["store_memory"](
            content="Test memory",
            category="fact",
        )

        # Assert: memory was still stored
        fresh_vector_store.upsert.assert_called_once()


class TestBug043CommitsCollection:
    """Tests for auto-creation of commits collection."""

    @pytest.mark.asyncio
    async def test_index_commits_creates_collection(
        self,
        fresh_vector_store: AsyncMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test that index_commits creates collection if it doesn't exist."""
        from clams.git import GitAnalyzer

        # Create mocks
        mock_git_reader = MagicMock()
        mock_git_reader.get_repo_root.return_value = "/test/repo"

        mock_metadata_store = AsyncMock()
        mock_metadata_store.get_git_index_state = AsyncMock(return_value=None)

        # Create analyzer
        analyzer = GitAnalyzer(
            git_reader=mock_git_reader,
            embedding_service=mock_embedder,
            vector_store=fresh_vector_store,
            metadata_store=mock_metadata_store,
        )

        # Mock get_commits to return empty list (no commits to index)
        mock_git_reader.get_commits = AsyncMock(return_value=[])

        # Action: index commits (should auto-create collection)
        await analyzer.index_commits()

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="commits",
            dimension=768,
            distance="cosine",
        )

    @pytest.mark.asyncio
    async def test_search_commits_creates_collection(
        self,
        fresh_vector_store: AsyncMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test that search_commits creates collection if it doesn't exist."""
        from clams.git import GitAnalyzer

        # Create mocks
        mock_git_reader = MagicMock()
        mock_git_reader.get_repo_root.return_value = "/test/repo"

        mock_metadata_store = AsyncMock()

        # Create analyzer
        analyzer = GitAnalyzer(
            git_reader=mock_git_reader,
            embedding_service=mock_embedder,
            vector_store=fresh_vector_store,
            metadata_store=mock_metadata_store,
        )

        # Mock search to return empty results
        fresh_vector_store.search = AsyncMock(return_value=[])

        # Action: search commits (should auto-create collection)
        results = await analyzer.search_commits(query="test query", limit=10)

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="commits",
            dimension=768,
            distance="cosine",
        )

        # Assert: search completed
        assert results == []


class TestBug043ValuesCollection:
    """Tests for auto-creation of values collection."""

    @pytest.mark.asyncio
    async def test_store_value_creates_collection(
        self,
        fresh_vector_store: AsyncMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test that store_value creates collection if it doesn't exist."""
        from clams.values import ClusterInfo, ValueStore

        # Create mock clusterer
        mock_clusterer = AsyncMock()
        mock_clusterer.count_experiences = AsyncMock(return_value=25)
        mock_clusterer.cluster_axis = AsyncMock(
            return_value=[
                ClusterInfo(
                    cluster_id="full_0",
                    axis="full",
                    label=0,
                    centroid=np.array([1.0, 0.0], dtype=np.float32),
                    member_ids=["exp_1", "exp_2", "exp_3"],
                    size=3,
                    avg_weight=0.9,
                ),
            ]
        )

        # Mock get to return cluster members
        fresh_vector_store.get = AsyncMock(
            side_effect=[
                MagicMock(
                    id="exp_1",
                    payload={"confidence_weight": 0.9},
                    vector=np.array([0.99, 0.14], dtype=np.float32),
                ),
                MagicMock(
                    id="exp_2",
                    payload={"confidence_weight": 0.85},
                    vector=np.array([0.98, 0.20], dtype=np.float32),
                ),
                MagicMock(
                    id="exp_3",
                    payload={"confidence_weight": 0.95},
                    vector=np.array([0.97, 0.24], dtype=np.float32),
                ),
            ]
        )

        # Mock embedder to return close vector (passes validation)
        mock_embedder.embed = AsyncMock(
            return_value=np.array([0.99, 0.14], dtype=np.float32)
        )

        # Create value store
        value_store = ValueStore(
            embedding_service=mock_embedder,
            vector_store=fresh_vector_store,
            clusterer=mock_clusterer,
        )

        # Action: store value (should auto-create collection)
        value = await value_store.store_value(
            text="Test value",
            cluster_id="full_0",
            axis="full",
        )

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="values",
            dimension=768,
            distance="cosine",
        )

        # Assert: value was stored
        fresh_vector_store.upsert.assert_called_once()
        assert value.text == "Test value"

    @pytest.mark.asyncio
    async def test_list_values_creates_collection(
        self,
        fresh_vector_store: AsyncMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test that list_values creates collection if it doesn't exist."""
        from clams.values import ValueStore

        # Create mock clusterer
        mock_clusterer = AsyncMock()

        # Create value store
        value_store = ValueStore(
            embedding_service=mock_embedder,
            vector_store=fresh_vector_store,
            clusterer=mock_clusterer,
        )

        # Mock scroll to return empty list
        fresh_vector_store.scroll = AsyncMock(return_value=[])

        # Action: list values (should auto-create collection)
        values = await value_store.list_values()

        # Assert: collection was created
        fresh_vector_store.create_collection.assert_called_once_with(
            name="values",
            dimension=768,
            distance="cosine",
        )

        # Assert: list completed
        assert values == []
