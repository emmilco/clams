"""Tests for CALM tools."""

import pytest

from calm.embedding import MockEmbeddingService
from calm.storage import MemoryStore


class TestCodeTools:
    """Test code tools."""

    @pytest.fixture
    async def setup(self) -> tuple[MemoryStore, MockEmbeddingService]:
        """Set up test fixtures."""
        store = MemoryStore()
        embedder = MockEmbeddingService(dimension=384)
        return store, embedder

    @pytest.mark.asyncio
    async def test_index_codebase_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test index_codebase returns placeholder response."""
        from calm.tools.code import get_code_tools

        store, embedder = setup
        tools = get_code_tools(store, embedder)

        result = await tools["index_codebase"](
            directory="/tmp", project="test-project"
        )

        assert result["status"] == "not_available"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_search_code_empty_query(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test search_code handles empty query."""
        from calm.tools.code import get_code_tools

        store, embedder = setup
        tools = get_code_tools(store, embedder)

        result = await tools["search_code"](query="")

        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_code_no_results(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test search_code returns empty when no indexed code."""
        from calm.tools.code import get_code_tools

        store, embedder = setup
        tools = get_code_tools(store, embedder)

        result = await tools["search_code"](query="test query")

        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_find_similar_code_empty_snippet(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test find_similar_code handles empty snippet."""
        from calm.tools.code import get_code_tools

        store, embedder = setup
        tools = get_code_tools(store, embedder)

        result = await tools["find_similar_code"](snippet="")

        assert result["results"] == []
        assert result["count"] == 0


class TestGitTools:
    """Test git tools."""

    @pytest.fixture
    async def setup(self) -> tuple[MemoryStore, MockEmbeddingService]:
        """Set up test fixtures."""
        store = MemoryStore()
        embedder = MockEmbeddingService(dimension=384)
        return store, embedder

    @pytest.mark.asyncio
    async def test_index_commits_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test index_commits raises error when git_analyzer not available."""
        from calm.tools.git import get_git_tools
        from calm.tools.errors import MCPError

        store, embedder = setup
        tools = get_git_tools(store, embedder)

        with pytest.raises(MCPError, match="Git commit indexing not available"):
            await tools["index_commits"]()

    @pytest.mark.asyncio
    async def test_search_commits_empty_query(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test search_commits raises error when git_analyzer not available."""
        from calm.tools.git import get_git_tools
        from calm.tools.errors import MCPError

        store, embedder = setup
        tools = get_git_tools(store, embedder)

        with pytest.raises(MCPError, match="Git commit search not available"):
            await tools["search_commits"](query="")

    @pytest.mark.asyncio
    async def test_get_file_history_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test get_file_history raises error when git_analyzer not available."""
        from calm.tools.git import get_git_tools
        from calm.tools.errors import MCPError

        store, embedder = setup
        tools = get_git_tools(store, embedder)

        with pytest.raises(MCPError, match="Git file history not available"):
            await tools["get_file_history"](path="test.py")

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test get_churn_hotspots raises error when git_analyzer not available."""
        from calm.tools.git import get_git_tools
        from calm.tools.errors import MCPError

        store, embedder = setup
        tools = get_git_tools(store, embedder)

        with pytest.raises(MCPError, match="Git churn analysis not available"):
            await tools["get_churn_hotspots"]()

    @pytest.mark.asyncio
    async def test_get_code_authors_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test get_code_authors raises error when git_analyzer not available."""
        from calm.tools.git import get_git_tools
        from calm.tools.errors import MCPError

        store, embedder = setup
        tools = get_git_tools(store, embedder)

        with pytest.raises(MCPError, match="Git author analysis not available"):
            await tools["get_code_authors"](path="test.py")


class TestLearningTools:
    """Test learning tools."""

    @pytest.fixture
    async def setup(self) -> tuple[MemoryStore, MockEmbeddingService]:
        """Set up test fixtures."""
        store = MemoryStore()
        embedder = MockEmbeddingService(dimension=384)
        return store, embedder

    @pytest.mark.asyncio
    async def test_search_experiences_empty_query(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test search_experiences handles empty query."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["search_experiences"](query="")

        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_axis(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test search_experiences validates axis."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["search_experiences"](query="test", axis="invalid")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_get_clusters_placeholder(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test get_clusters returns placeholder response."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["get_clusters"](axis="full")

        assert result["status"] == "not_available"

    @pytest.mark.asyncio
    async def test_validate_value_empty_text(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test validate_value validates text."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["validate_value"](text="", cluster_id="full_0")

        assert "error" in result
        assert result["error"]["type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_store_value(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test store_value stores a value."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["store_value"](
            text="Test value statement",
            cluster_id="full_0",
            axis="full",
        )

        assert "id" in result
        assert result["text"] == "Test value statement"
        assert result["axis"] == "full"

    @pytest.mark.asyncio
    async def test_list_values_empty(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test list_values returns empty when no values."""
        from calm.tools.learning import get_learning_tools

        store, embedder = setup
        tools = get_learning_tools(store, embedder)

        result = await tools["list_values"]()

        assert result["results"] == []
        assert result["count"] == 0


class TestContextTools:
    """Test context tools."""

    @pytest.fixture
    async def setup(self) -> tuple[MemoryStore, MockEmbeddingService]:
        """Set up test fixtures."""
        store = MemoryStore()
        embedder = MockEmbeddingService(dimension=384)
        return store, embedder

    @pytest.mark.asyncio
    async def test_assemble_context_empty_query(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test assemble_context handles empty query."""
        from calm.tools.context import get_context_tools

        store, embedder = setup
        tools = get_context_tools(store, embedder)

        result = await tools["assemble_context"](query="")

        assert result["markdown"] == ""
        assert result["token_count"] == 0
        assert result["item_count"] == 0
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_assemble_context_invalid_context_types(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test assemble_context validates context_types."""
        from calm.tools.context import get_context_tools
        from calm.tools.validation import ValidationError

        store, embedder = setup
        tools = get_context_tools(store, embedder)

        with pytest.raises(ValidationError):
            await tools["assemble_context"](
                query="test", context_types=["invalid_type"]
            )

    @pytest.mark.asyncio
    async def test_assemble_context_no_results(
        self, setup: tuple[MemoryStore, MockEmbeddingService]
    ) -> None:
        """Test assemble_context when no results found."""
        from calm.tools.context import get_context_tools

        store, embedder = setup
        tools = get_context_tools(store, embedder)

        result = await tools["assemble_context"](query="test query")

        # Should return empty markdown since no values or experiences
        assert result["markdown"] == ""
        assert result["item_count"] == 0
