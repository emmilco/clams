"""Regression tests for BUG-083: Consistent error handling across all MCP tools.

Verifies that ALL tool categories return structured error dicts
{"error": {"type": "...", "message": "..."}} instead of raising exceptions.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from calm.embedding import MockEmbeddingService
from calm.ghap import ObservationCollector, ObservationPersister
from calm.storage import MemoryStore
from calm.tools.code import get_code_tools
from calm.tools.context import get_context_tools
from calm.tools.ghap import get_ghap_tools
from calm.tools.git import get_git_tools
from calm.tools.journal import get_journal_tools
from calm.tools.learning import get_learning_tools
from calm.tools.memory import get_memory_tools
from calm.tools.session import SessionManager, get_session_tools

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def vector_store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def embedder() -> MockEmbeddingService:
    return MockEmbeddingService(dimension=384)


@pytest.fixture
def memory_tools(
    vector_store: MemoryStore, embedder: MockEmbeddingService
) -> dict[str, Any]:
    return get_memory_tools(vector_store, embedder)


@pytest.fixture
def code_tools(
    vector_store: MemoryStore, embedder: MockEmbeddingService
) -> dict[str, Any]:
    return get_code_tools(vector_store, embedder)


@pytest.fixture
def git_tools(
    vector_store: MemoryStore, embedder: MockEmbeddingService
) -> dict[str, Any]:
    return get_git_tools(vector_store, embedder)


@pytest.fixture
def ghap_tools(tmp_path: Path) -> dict[str, Any]:
    collector = ObservationCollector(str(tmp_path))
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])
    persister = ObservationPersister(
        embedding_service=MagicMock(),
        vector_store=vector_store,
    )
    return get_ghap_tools(collector, persister)


@pytest.fixture
def learning_tools(
    vector_store: MemoryStore, embedder: MockEmbeddingService
) -> dict[str, Any]:
    return get_learning_tools(vector_store, embedder)


@pytest.fixture
def context_tools(
    vector_store: MemoryStore, embedder: MockEmbeddingService
) -> dict[str, Any]:
    return get_context_tools(vector_store, embedder)


@pytest.fixture
def session_tools(tmp_path: Path) -> dict[str, Any]:
    mgr = SessionManager(
        calm_dir=tmp_path / ".calm",
        journal_dir=tmp_path / ".calm" / "journal",
    )
    return get_session_tools(mgr)


@pytest.fixture
def journal_tools(tmp_path: Path) -> dict[str, Any]:
    return get_journal_tools(db_path=tmp_path / "test.db")


# =========================================================================
# Helper
# =========================================================================


def assert_error_dict(result: dict[str, Any], error_type: str | None = None) -> None:
    """Assert result is a structured error dict with type and message."""
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "error" in result, f"Expected 'error' key in result: {result}"
    assert isinstance(result["error"], dict), (
        f"Expected error to be dict, got {type(result['error'])}"
    )
    assert "type" in result["error"], (
        f"Expected 'type' in error dict: {result['error']}"
    )
    assert "message" in result["error"], (
        f"Expected 'message' in error dict: {result['error']}"
    )
    assert isinstance(result["error"]["type"], str)
    assert isinstance(result["error"]["message"], str)
    if error_type:
        assert result["error"]["type"] == error_type, (
            f"Expected error type '{error_type}', got '{result['error']['type']}'"
        )


# =========================================================================
# BUG-083 Regression: ALL tools return consistent error dicts
# =========================================================================


class TestMemoryToolsReturnErrorDicts:
    """Memory tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_store_memory_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        result = await memory_tools["store_memory"](
            content="test", category="INVALID"
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_retrieve_memories_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        result = await memory_tools["retrieve_memories"](
            query="test", category="INVALID"
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_list_memories_invalid_offset(
        self, memory_tools: dict[str, Any]
    ) -> None:
        result = await memory_tools["list_memories"](offset=-1)
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_delete_memory_invalid_uuid(
        self, memory_tools: dict[str, Any]
    ) -> None:
        result = await memory_tools["delete_memory"](memory_id="not-a-uuid")
        assert_error_dict(result, "validation_error")


class TestCodeToolsReturnErrorDicts:
    """Code tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_index_codebase_missing_directory(
        self, code_tools: dict[str, Any]
    ) -> None:
        result = await code_tools["index_codebase"](
            directory="/nonexistent/path", project="test"
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_search_code_invalid_limit(
        self, code_tools: dict[str, Any]
    ) -> None:
        result = await code_tools["search_code"](query="test", limit=999)
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_find_similar_code_invalid_limit(
        self, code_tools: dict[str, Any]
    ) -> None:
        result = await code_tools["find_similar_code"](snippet="x", limit=-1)
        assert_error_dict(result, "validation_error")


class TestGitToolsReturnErrorDicts:
    """Git tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_index_commits_not_available(
        self, git_tools: dict[str, Any]
    ) -> None:
        result = await git_tools["index_commits"]()
        assert_error_dict(result, "not_available")

    @pytest.mark.asyncio
    async def test_search_commits_not_available(
        self, git_tools: dict[str, Any]
    ) -> None:
        result = await git_tools["search_commits"](query="test")
        assert_error_dict(result, "not_available")

    @pytest.mark.asyncio
    async def test_get_file_history_not_available(
        self, git_tools: dict[str, Any]
    ) -> None:
        result = await git_tools["get_file_history"](path="test.py")
        assert_error_dict(result, "not_available")

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_not_available(
        self, git_tools: dict[str, Any]
    ) -> None:
        result = await git_tools["get_churn_hotspots"]()
        assert_error_dict(result, "not_available")

    @pytest.mark.asyncio
    async def test_get_code_authors_not_available(
        self, git_tools: dict[str, Any]
    ) -> None:
        result = await git_tools["get_code_authors"](path="test.py")
        assert_error_dict(result, "not_available")


class TestGhapToolsReturnErrorDicts:
    """GHAP tools must return error dicts (already did before fix)."""

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_domain(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        result = await ghap_tools["start_ghap"](
            domain="INVALID",
            strategy="systematic-elimination",
            goal="g", hypothesis="h", action="a", prediction="p",
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_update_ghap_no_active(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        result = await ghap_tools["update_ghap"](hypothesis="test")
        assert_error_dict(result, "not_found")


class TestLearningToolsReturnErrorDicts:
    """Learning tools must return error dicts (already did before fix)."""

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        result = await learning_tools["search_experiences"](
            query="test", axis="INVALID"
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_get_clusters_invalid_axis(
        self, learning_tools: dict[str, Any]
    ) -> None:
        result = await learning_tools["get_clusters"](axis="INVALID")
        assert_error_dict(result, "validation_error")


class TestContextToolsReturnErrorDicts:
    """Context tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_assemble_context_invalid_types(
        self, context_tools: dict[str, Any]
    ) -> None:
        result = await context_tools["assemble_context"](
            query="test", context_types=["INVALID"]
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_assemble_context_invalid_limit(
        self, context_tools: dict[str, Any]
    ) -> None:
        result = await context_tools["assemble_context"](
            query="test", limit=999
        )
        assert_error_dict(result, "validation_error")


class TestSessionToolsReturnErrorDicts:
    """Session tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_should_check_in_invalid_frequency(
        self, session_tools: dict[str, Any]
    ) -> None:
        result = await session_tools["should_check_in"](frequency=0)
        assert_error_dict(result, "validation_error")


class TestJournalToolsReturnErrorDicts:
    """Journal tools must return error dicts, not raise exceptions."""

    @pytest.mark.asyncio
    async def test_store_journal_entry_empty_summary(
        self, journal_tools: dict[str, Any]
    ) -> None:
        result = await journal_tools["store_journal_entry"](
            summary="", working_directory="/tmp"
        )
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_list_journal_entries_invalid_limit(
        self, journal_tools: dict[str, Any]
    ) -> None:
        result = await journal_tools["list_journal_entries"](limit=0)
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_get_journal_entry_invalid_uuid(
        self, journal_tools: dict[str, Any]
    ) -> None:
        result = await journal_tools["get_journal_entry"](entry_id="bad-uuid")
        assert_error_dict(result, "validation_error")

    @pytest.mark.asyncio
    async def test_mark_entries_reflected_empty_ids(
        self, journal_tools: dict[str, Any]
    ) -> None:
        result = await journal_tools["mark_entries_reflected"](entry_ids=[])
        assert_error_dict(result, "validation_error")


class TestAllToolCategoriesConsistent:
    """Cross-category test: error shape is identical across all tool types."""

    @pytest.mark.asyncio
    async def test_error_shape_matches_across_categories(
        self,
        memory_tools: dict[str, Any],
        code_tools: dict[str, Any],
        git_tools: dict[str, Any],
        ghap_tools: dict[str, Any],
        learning_tools: dict[str, Any],
        context_tools: dict[str, Any],
        session_tools: dict[str, Any],
        journal_tools: dict[str, Any],
    ) -> None:
        """Every tool category returns the same error dict shape."""
        results = [
            await memory_tools["store_memory"](content="x", category="BAD"),
            await code_tools["search_code"](query="x", limit=999),
            await git_tools["index_commits"](),
            await ghap_tools["start_ghap"](
                domain="BAD", strategy="systematic-elimination",
                goal="g", hypothesis="h", action="a", prediction="p",
            ),
            await learning_tools["search_experiences"](query="x", axis="BAD"),
            await context_tools["assemble_context"](
                query="x", context_types=["BAD"],
            ),
            await session_tools["should_check_in"](frequency=0),
            await journal_tools["store_journal_entry"](
                summary="", working_directory="/tmp",
            ),
        ]

        for i, result in enumerate(results):
            assert isinstance(result, dict), f"Result {i} is not a dict"
            assert "error" in result, f"Result {i} missing 'error' key: {result}"
            err = result["error"]
            assert isinstance(err, dict), f"Result {i} error is not a dict"
            assert "type" in err, f"Result {i} error missing 'type': {err}"
            assert "message" in err, f"Result {i} error missing 'message': {err}"
            assert isinstance(err["type"], str), f"Result {i} type is not str"
            assert isinstance(err["message"], str), f"Result {i} message is not str"
