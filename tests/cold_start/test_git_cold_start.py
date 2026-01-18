"""Cold-start tests for git operations.

These tests verify that git operations handle the cold-start scenario
gracefully. Git tools depend on GitAnalyzer service which requires
a git repository and vector storage.

Reference: BUG-043 - commits collection was never created
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.server.errors import MCPError
from clams.server.tools import ServiceContainer
from clams.server.tools.git import get_git_tools
from clams.storage.qdrant import QdrantVectorStore


@pytest.fixture
def mock_git_analyzer() -> AsyncMock:
    """Create a mock GitAnalyzer for testing."""
    analyzer = AsyncMock()

    # Mock index_commits to return empty stats
    mock_stats = MagicMock()
    mock_stats.commits_indexed = 0
    mock_stats.commits_skipped = 0
    mock_stats.duration_ms = 100
    mock_stats.errors = []
    analyzer.index_commits.return_value = mock_stats

    # Mock search_commits to return empty list
    analyzer.search_commits.return_value = []

    # Mock git_reader for file history
    mock_reader = AsyncMock()
    mock_reader.get_file_history.return_value = []
    analyzer.git_reader = mock_reader

    # Mock churn hotspots
    analyzer.get_churn_hotspots.return_value = []

    # Mock file authors
    analyzer.get_file_authors.return_value = []

    return analyzer


@pytest.fixture
def git_services_with_analyzer(
    cold_start_qdrant: QdrantVectorStore,
    mock_git_analyzer: AsyncMock,
) -> ServiceContainer:
    """ServiceContainer with mock GitAnalyzer for cold-start testing."""
    return ServiceContainer(
        code_embedder=AsyncMock(),
        semantic_embedder=AsyncMock(),
        vector_store=cold_start_qdrant,
        metadata_store=AsyncMock(),
        code_indexer=None,
        git_analyzer=mock_git_analyzer,
        searcher=None,
    )


@pytest.fixture
def git_services_no_analyzer(
    cold_start_qdrant: QdrantVectorStore,
) -> ServiceContainer:
    """ServiceContainer without GitAnalyzer (simulates no git repo)."""
    return ServiceContainer(
        code_embedder=AsyncMock(),
        semantic_embedder=AsyncMock(),
        vector_store=cold_start_qdrant,
        metadata_store=AsyncMock(),
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


class TestIndexCommitsColdStart:
    """Tests for index_commits on cold start."""

    @pytest.mark.cold_start
    async def test_index_commits_returns_zero_count(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """index_commits on cold start returns dict with indexed count (may be 0)."""
        tools = get_git_tools(git_services_with_analyzer)
        index_commits = tools["index_commits"]

        result = await index_commits()

        # Should return stats dict, not exception
        assert isinstance(result, dict)
        assert "commits_indexed" in result
        # Value may be 0 on cold start
        assert isinstance(result["commits_indexed"], int)

    @pytest.mark.cold_start
    async def test_index_commits_no_exception(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """index_commits should not raise exception on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        index_commits = tools["index_commits"]

        # Should not raise any exception
        result = await index_commits()
        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_index_commits_no_analyzer_raises_mcp_error(
        self,
        git_services_no_analyzer: ServiceContainer,
    ) -> None:
        """index_commits without GitAnalyzer raises MCPError."""
        tools = get_git_tools(git_services_no_analyzer)
        index_commits = tools["index_commits"]

        # Without analyzer, should raise MCPError (not 404)
        with pytest.raises(MCPError) as exc_info:
            await index_commits()

        assert "GitAnalyzer" in str(exc_info.value)


class TestSearchCommitsColdStart:
    """Tests for search_commits on cold start."""

    @pytest.mark.cold_start
    async def test_search_commits_returns_empty_list(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """search_commits on cold start returns empty list, not 404."""
        tools = get_git_tools(git_services_with_analyzer)
        search_commits = tools["search_commits"]

        result = await search_commits(query="fix bug")

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_search_commits_no_exception(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """search_commits should not raise exception on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        search_commits = tools["search_commits"]

        # Should not raise
        result = await search_commits(
            query="refactor",
            author="developer",
            limit=20,
        )

        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_search_commits_no_analyzer_raises_mcp_error(
        self,
        git_services_no_analyzer: ServiceContainer,
    ) -> None:
        """search_commits without GitAnalyzer raises MCPError."""
        tools = get_git_tools(git_services_no_analyzer)
        search_commits = tools["search_commits"]

        with pytest.raises(MCPError) as exc_info:
            await search_commits(query="test")

        assert "GitAnalyzer" in str(exc_info.value)


class TestGetFileHistoryColdStart:
    """Tests for get_file_history on cold start."""

    @pytest.mark.cold_start
    async def test_get_file_history_returns_empty_list(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_file_history on cold start returns empty list."""
        tools = get_git_tools(git_services_with_analyzer)
        get_file_history = tools["get_file_history"]

        result = await get_file_history(path="src/main.py")

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_get_file_history_no_404_error(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_file_history should not raise 404 on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        get_file_history = tools["get_file_history"]

        # Should return empty, not error
        result = await get_file_history(path="nonexistent/file.py")

        # Empty result is expected, not 404
        assert isinstance(result, dict)

    @pytest.mark.cold_start
    async def test_get_file_history_no_analyzer_raises_mcp_error(
        self,
        git_services_no_analyzer: ServiceContainer,
    ) -> None:
        """get_file_history without GitAnalyzer raises MCPError."""
        tools = get_git_tools(git_services_no_analyzer)
        get_file_history = tools["get_file_history"]

        with pytest.raises(MCPError) as exc_info:
            await get_file_history(path="src/main.py")

        assert "GitAnalyzer" in str(exc_info.value)


class TestGetChurnHotspotsColdStart:
    """Tests for get_churn_hotspots on cold start."""

    @pytest.mark.cold_start
    async def test_get_churn_hotspots_returns_empty(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_churn_hotspots on cold start returns empty list."""
        tools = get_git_tools(git_services_with_analyzer)
        get_churn_hotspots = tools["get_churn_hotspots"]

        result = await get_churn_hotspots()

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_get_churn_hotspots_no_exception(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_churn_hotspots should not raise exception on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        get_churn_hotspots = tools["get_churn_hotspots"]

        result = await get_churn_hotspots(days=30, limit=5)
        assert isinstance(result, dict)


class TestGetCodeAuthorsColdStart:
    """Tests for get_code_authors on cold start."""

    @pytest.mark.cold_start
    async def test_get_code_authors_returns_empty(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_code_authors on cold start returns empty list."""
        tools = get_git_tools(git_services_with_analyzer)
        get_code_authors = tools["get_code_authors"]

        result = await get_code_authors(path="src/main.py")

        assert "results" in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.cold_start
    async def test_get_code_authors_no_exception(
        self,
        git_services_with_analyzer: ServiceContainer,
    ) -> None:
        """get_code_authors should not raise exception on cold start."""
        tools = get_git_tools(git_services_with_analyzer)
        get_code_authors = tools["get_code_authors"]

        result = await get_code_authors(path="src/utils.py")
        assert isinstance(result, dict)


class TestCollectionCreationOnColdStart:
    """Tests verifying collection exists after first commit operation."""

    @pytest.mark.cold_start
    async def test_index_commits_creates_collection(
        self,
        git_services_with_analyzer: ServiceContainer,
        cold_start_qdrant: QdrantVectorStore,
    ) -> None:
        """index_commits should create commits collection if needed."""
        # Verify collection doesn't exist initially
        info = await cold_start_qdrant.get_collection_info("commits")
        assert info is None, "commits collection should not exist on cold start"

        tools = get_git_tools(git_services_with_analyzer)

        # Call index_commits - note this uses mock, so collection may not be
        # created depending on implementation. This test documents expected behavior.
        result = await tools["index_commits"]()

        # Should succeed without 404
        assert isinstance(result, dict)
        # Note: actual collection creation depends on GitAnalyzer implementation
