"""Unit tests for Searcher class."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import numpy as np
import pytest

from calm.embedding.base import EmbeddingService
from calm.search import (
    CodeResult,
    CollectionName,
    CommitResult,
    ExperienceResult,
    InvalidAxisError,
    MemoryResult,
    ValueResult,
)
from calm.search.searcher import (
    CollectionNotFoundError,
    EmbeddingError,
    InvalidSearchModeError,
    Searcher,
)
from calm.storage.base import SearchResult, VectorStore


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Mock embedding service with fixed vectors."""
    service = AsyncMock(spec=EmbeddingService)
    service.embed.return_value = np.random.rand(768).astype(np.float32)
    service.dimension = 768
    return service


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock vector store with test data."""
    store = AsyncMock(spec=VectorStore)
    store.search.return_value = []
    return store


@pytest.fixture
def searcher(
    mock_embedding_service: AsyncMock, mock_vector_store: AsyncMock
) -> Searcher:
    """Create searcher with mocked dependencies."""
    return Searcher(mock_embedding_service, mock_vector_store)


class TestSearchMemories:
    """Tests for search_memories method."""

    async def test_calls_embed_with_query(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding service is called with query text."""
        await searcher.search_memories("test query")
        mock_embedding_service.embed.assert_called_once_with("test query")

    async def test_calls_vector_store_with_correct_collection(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify vector store is called with memories collection."""
        await searcher.search_memories("test query")
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["collection"] == CollectionName.MEMORIES

    async def test_applies_category_filter(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify category filter is applied correctly."""
        await searcher.search_memories("test", category="preference")
        call_filters = mock_vector_store.search.call_args[1]["filters"]
        assert call_filters == {"category": "preference"}

    async def test_empty_query_returns_empty_list(self, searcher: Searcher):
        """Verify empty query returns empty list."""
        results = await searcher.search_memories("")
        assert results == []

        results = await searcher.search_memories("   ")
        assert results == []

    async def test_invalid_search_mode_raises_error(self, searcher: Searcher):
        """Verify invalid search mode raises InvalidSearchModeError."""
        with pytest.raises(InvalidSearchModeError) as exc_info:
            await searcher.search_memories("test", search_mode="invalid_mode")
        assert "invalid_mode" in str(exc_info.value).lower()
        assert "semantic" in str(exc_info.value).lower()

    async def test_embedding_failure_raises_embedding_error(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding failure raises EmbeddingError."""
        mock_embedding_service.embed.side_effect = Exception("Model failed")
        with pytest.raises(EmbeddingError) as exc_info:
            await searcher.search_memories("test")
        assert "Model failed" in str(exc_info.value)

    async def test_collection_not_found_raises_error(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify collection not found raises CollectionNotFoundError."""
        mock_vector_store.search.side_effect = Exception(
            "Collection not found"
        )
        with pytest.raises(CollectionNotFoundError) as exc_info:
            await searcher.search_memories("test")
        assert "memories" in str(exc_info.value).lower()

    async def test_maps_results_correctly(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify results are mapped to MemoryResult correctly."""
        mock_vector_store.search.return_value = [
            SearchResult(
                id="mem_123",
                score=0.95,
                payload={
                    "category": "preference",
                    "content": "Use async/await",
                    "tags": ["python", "async"],
                    "created_at": "2024-01-01T12:00:00Z",
                    "verified_at": None,
                    "verification_status": None,
                },
            )
        ]
        results = await searcher.search_memories("test")
        assert len(results) == 1
        assert isinstance(results[0], MemoryResult)
        assert results[0].id == "mem_123"
        assert results[0].score == 0.95
        assert results[0].category == "preference"
        assert results[0].content == "Use async/await"
        assert results[0].tags == ["python", "async"]


class TestSearchCode:
    """Tests for search_code method."""

    async def test_calls_embed_with_query(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding service is called with query text."""
        await searcher.search_code("test query")
        mock_embedding_service.embed.assert_called_once_with("test query")

    async def test_calls_vector_store_with_correct_collection(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify vector store is called with code collection."""
        await searcher.search_code("test query")
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["collection"] == CollectionName.CODE_UNITS

    async def test_applies_multiple_filters(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify multiple filters are applied correctly."""
        await searcher.search_code(
            "auth", project="clams", language="python", unit_type="function"
        )
        call_filters = mock_vector_store.search.call_args[1]["filters"]
        assert call_filters == {
            "project": "clams",
            "language": "python",
            "unit_type": "function",
        }

    async def test_maps_results_correctly(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify results are mapped to CodeResult correctly."""
        mock_vector_store.search.return_value = [
            SearchResult(
                id="code_123",
                score=0.92,
                payload={
                    "project": "clams",
                    "file_path": "/src/auth.py",
                    "language": "python",
                    "unit_type": "function",
                    "qualified_name": "auth.login",
                    "code": "def login(): pass",
                    "docstring": "Login function",
                    "line_start": 10,
                    "line_end": 12,
                },
            )
        ]
        results = await searcher.search_code("test")
        assert len(results) == 1
        assert isinstance(results[0], CodeResult)
        assert results[0].id == "code_123"
        assert results[0].score == 0.92
        assert results[0].project == "clams"
        assert results[0].file_path == "/src/auth.py"


class TestSearchExperiences:
    """Tests for search_experiences method."""

    async def test_calls_embed_with_query(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding service is called with query text."""
        await searcher.search_experiences("test query")
        mock_embedding_service.embed.assert_called_once_with("test query")

    async def test_selects_correct_collection_for_axis(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify axis maps to correct collection."""
        await searcher.search_experiences("test", axis="strategy")
        call_args = mock_vector_store.search.call_args
        assert (
            call_args[1]["collection"]
            == CollectionName.EXPERIENCES_STRATEGY
        )

        mock_vector_store.reset_mock()
        await searcher.search_experiences("test", axis="surprise")
        call_args = mock_vector_store.search.call_args
        assert (
            call_args[1]["collection"]
            == CollectionName.EXPERIENCES_SURPRISE
        )

    async def test_invalid_axis_raises_error(self, searcher: Searcher):
        """Verify invalid axis raises InvalidAxisError."""
        with pytest.raises(InvalidAxisError) as exc_info:
            await searcher.search_experiences("test", axis="invalid")
        assert "invalid" in str(exc_info.value).lower()
        assert "full" in str(exc_info.value)

    async def test_applies_domain_and_outcome_filters(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify domain and outcome filters are applied correctly."""
        await searcher.search_experiences(
            "test", domain="debugging", outcome="confirmed"
        )
        call_filters = mock_vector_store.search.call_args[1]["filters"]
        assert call_filters == {
            "domain": "debugging",
            "outcome_status": "confirmed",
        }

    async def test_maps_results_with_nested_dataclasses(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify results are mapped to ExperienceResult with nested objects."""
        mock_vector_store.search.return_value = [
            SearchResult(
                id="exp_123",
                score=0.88,
                payload={
                    "ghap_id": "ghap_001",
                    "axis": "full",
                    "domain": "debugging",
                    "strategy": "hypothesis testing",
                    "goal": "fix bug",
                    "hypothesis": "null pointer",
                    "action": "add check",
                    "prediction": "no crash",
                    "outcome_status": "confirmed",
                    "outcome_result": "bug fixed",
                    "surprise": "unexpected edge case",
                    "root_cause": {
                        "category": "logic_error",
                        "description": "missing null check",
                    },
                    "lesson": {
                        "what_worked": "defensive programming",
                        "takeaway": "always check nulls",
                    },
                    "confidence_tier": "high",
                    "iteration_count": 1,
                    "created_at": "2024-01-01T12:00:00Z",
                },
            )
        ]
        results = await searcher.search_experiences("test")
        assert len(results) == 1
        assert isinstance(results[0], ExperienceResult)
        assert results[0].id == "exp_123"
        assert results[0].score == 0.88
        assert results[0].domain == "debugging"
        assert results[0].root_cause is not None
        assert results[0].root_cause.category == "logic_error"
        assert results[0].lesson is not None
        assert results[0].lesson.what_worked == "defensive programming"


class TestSearchValues:
    """Tests for search_values method."""

    async def test_calls_embed_with_query(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding service is called with query text."""
        await searcher.search_values("test query")
        mock_embedding_service.embed.assert_called_once_with("test query")

    async def test_calls_vector_store_with_correct_collection(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify vector store is called with values collection."""
        await searcher.search_values("test query")
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["collection"] == CollectionName.VALUES

    async def test_default_limit_is_5(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify default limit is 5 for values."""
        await searcher.search_values("test")
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["limit"] == 5

    async def test_maps_results_correctly(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify results are mapped to ValueResult correctly."""
        mock_vector_store.search.return_value = [
            SearchResult(
                id="val_123",
                score=0.91,
                payload={
                    "axis": "strategy",
                    "cluster_id": "cluster_001",
                    "text": "Test early",
                    "member_count": 10,
                    "avg_confidence": 0.85,
                    "created_at": "2024-01-01T12:00:00Z",
                },
            )
        ]
        results = await searcher.search_values("test")
        assert len(results) == 1
        assert isinstance(results[0], ValueResult)
        assert results[0].id == "val_123"
        assert results[0].score == 0.91
        assert results[0].axis == "strategy"


class TestSearchCommits:
    """Tests for search_commits method."""

    async def test_calls_embed_with_query(
        self, searcher: Searcher, mock_embedding_service: AsyncMock
    ):
        """Verify embedding service is called with query text."""
        await searcher.search_commits("test query")
        mock_embedding_service.embed.assert_called_once_with("test query")

    async def test_calls_vector_store_with_correct_collection(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify vector store is called with commits collection."""
        await searcher.search_commits("test query")
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["collection"] == CollectionName.COMMITS

    async def test_applies_author_and_date_filters(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify author and date filters are applied correctly."""
        since = datetime(2024, 1, 1, tzinfo=UTC)
        await searcher.search_commits("test", author="alice", since=since)
        call_filters = mock_vector_store.search.call_args[1]["filters"]
        assert call_filters == {
            "author": "alice",
            "committed_at": {"$gte": since.timestamp()},
        }

    async def test_maps_results_correctly(
        self, searcher: Searcher, mock_vector_store: AsyncMock
    ):
        """Verify results are mapped to CommitResult correctly."""
        mock_vector_store.search.return_value = [
            SearchResult(
                id="commit_123",
                score=0.87,
                payload={
                    "sha": "abc123",
                    "message": "Fix bug",
                    "author": "alice",
                    "author_email": "alice@example.com",
                    "committed_at": "2024-01-01T12:00:00Z",
                    "files_changed": ["src/auth.py", "tests/test_auth.py"],
                },
            )
        ]
        results = await searcher.search_commits("test")
        assert len(results) == 1
        assert isinstance(results[0], CommitResult)
        assert results[0].id == "commit_123"
        assert results[0].score == 0.87
        assert results[0].sha == "abc123"
        assert results[0].files_changed == [
            "src/auth.py",
            "tests/test_auth.py",
        ]


class TestCollectionName:
    """Tests for CollectionName class."""

    def test_experience_axis_mapping(self):
        """Verify experience axis mapping works correctly."""
        assert (
            CollectionName.get_experience_collection("full")
            == CollectionName.EXPERIENCES_FULL
        )
        assert (
            CollectionName.get_experience_collection("strategy")
            == CollectionName.EXPERIENCES_STRATEGY
        )
        assert (
            CollectionName.get_experience_collection("surprise")
            == CollectionName.EXPERIENCES_SURPRISE
        )
        assert (
            CollectionName.get_experience_collection("root_cause")
            == CollectionName.EXPERIENCES_ROOT_CAUSE
        )

    def test_invalid_axis_raises_error(self):
        """Verify invalid axis raises InvalidAxisError with helpful message."""
        with pytest.raises(InvalidAxisError) as exc_info:
            CollectionName.get_experience_collection("invalid")
        error_msg = str(exc_info.value)
        assert "invalid" in error_msg
        assert "full" in error_msg
        assert "strategy" in error_msg
