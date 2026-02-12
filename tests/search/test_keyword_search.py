"""Tests for keyword and hybrid search in the Searcher class."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import numpy as np
import pytest

from calm.embedding.base import EmbeddingService
from calm.search import (
    CodeResult,
    CommitResult,
    MemoryResult,
    ValueResult,
)
from calm.search.searcher import (
    VALID_SEARCH_MODES,
    CollectionNotFoundError,
    InvalidSearchModeError,
    Searcher,
    _keyword_match_score,
)
from calm.storage.base import VectorStore
from calm.storage.memory import MemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Mock embedding service returning fixed vectors."""
    service = AsyncMock(spec=EmbeddingService)
    service.embed.return_value = np.ones(384, dtype=np.float32)
    service.dimension = 384
    return service


@pytest.fixture
async def memory_store() -> MemoryStore:
    """In-memory vector store for integration-style tests."""
    store = MemoryStore()
    await store.create_collection("memories", dimension=384)
    await store.create_collection("code_units", dimension=384)
    await store.create_collection("commits", dimension=384)
    await store.create_collection("values", dimension=384)
    return store


@pytest.fixture
def searcher_with_memory_store(
    mock_embedding_service: AsyncMock, memory_store: MemoryStore
) -> Searcher:
    """Searcher backed by MemoryStore for keyword/hybrid tests."""
    return Searcher(mock_embedding_service, memory_store)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vec(dimension: int = 384) -> np.ndarray:
    """Return a random unit vector."""
    v = np.random.rand(dimension).astype(np.float32)
    return v / np.linalg.norm(v)


async def _seed_memories(store: MemoryStore) -> None:
    """Populate the memories collection with a few entries."""
    entries = [
        ("m1", "Use async/await for concurrency in Python"),
        ("m2", "Prefer dataclasses over plain dicts for structured data"),
        ("m3", "The _keyword_match_score function scores text relevance"),
    ]
    for mid, content in entries:
        await store.upsert(
            collection="memories",
            id=mid,
            vector=_vec(),
            payload={
                "content": content,
                "category": "preference",
                "importance": 0.7,
                "tags": [],
                "created_at": datetime.now(UTC).isoformat(),
                "verified_at": None,
                "verification_status": None,
            },
        )


async def _seed_code(store: MemoryStore) -> None:
    """Populate code_units with a few entries."""
    units = [
        (
            "c1",
            "def hello_world(): print('hello')",
            "hello_world",
            "Prints hello",
        ),
        ("c2", "class FooBar:\n    pass", "FooBar", None),
        (
            "c3",
            "def search_code(query): return results",
            "search_code",
            "Search indexed code semantically",
        ),
    ]
    for uid, code, qname, docstring in units:
        await store.upsert(
            collection="code_units",
            id=uid,
            vector=_vec(),
            payload={
                "project": "test",
                "file_path": "/src/test.py",
                "language": "python",
                "unit_type": "function",
                "qualified_name": qname,
                "code": code,
                "docstring": docstring,
                "line_start": 1,
                "line_end": 2,
            },
        )


async def _seed_commits(store: MemoryStore) -> None:
    """Populate commits collection."""
    commits = [
        ("k1", "abc111", "Fix BUG-042: null pointer in auth module"),
        ("k2", "abc222", "Add keyword search to Searcher class"),
        ("k3", "abc333", "Refactor storage layer for performance"),
    ]
    for cid, sha, message in commits:
        await store.upsert(
            collection="commits",
            id=cid,
            vector=_vec(),
            payload={
                "sha": sha,
                "message": message,
                "author": "alice",
                "author_email": "alice@example.com",
                "committed_at": datetime.now(UTC).isoformat(),
                "files_changed": ["src/main.py"],
            },
        )


async def _seed_values(store: MemoryStore) -> None:
    """Populate values collection."""
    vals = [
        ("v1", "Always write regression tests for bugs"),
        ("v2", "Use hypothesis-driven debugging"),
    ]
    for vid, text in vals:
        await store.upsert(
            collection="values",
            id=vid,
            vector=_vec(),
            payload={
                "axis": "full",
                "cluster_id": "full_0",
                "text": text,
                "member_count": 5,
                "avg_confidence": 0.8,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )


# ---------------------------------------------------------------------------
# Unit tests: _keyword_match_score
# ---------------------------------------------------------------------------


class TestKeywordMatchScore:
    """Tests for the _keyword_match_score helper."""

    def test_exact_match_returns_1(self):
        score = _keyword_match_score(
            "hello", {"content": "hello"}, ["content"]
        )
        assert score == 1.0

    def test_exact_match_case_insensitive(self):
        score = _keyword_match_score(
            "Hello World", {"content": "hello world"}, ["content"]
        )
        assert score == 1.0

    def test_substring_match_scores_high(self):
        score = _keyword_match_score(
            "async", {"content": "Use async/await for concurrency"}, ["content"]
        )
        assert score >= 0.6

    def test_term_match_scores_lower(self):
        score = _keyword_match_score(
            "async python", {"content": "Use async for concurrency"}, ["content"]
        )
        # "async" matches but "python" does not: partial term match
        assert 0.0 < score < 0.6

    def test_no_match_returns_zero(self):
        score = _keyword_match_score(
            "nonexistent", {"content": "nothing here"}, ["content"]
        )
        assert score == 0.0

    def test_multiple_fields_returns_best(self):
        payload = {
            "code": "def foo(): pass",
            "qualified_name": "async_handler",
            "docstring": "Handle async requests",
        }
        score = _keyword_match_score(
            "async_handler", payload, ["code", "qualified_name", "docstring"]
        )
        # exact match on qualified_name
        assert score == 1.0

    def test_missing_field_skipped(self):
        score = _keyword_match_score(
            "test", {"content": "test data"}, ["missing_field", "content"]
        )
        assert score > 0.0

    def test_none_field_value_skipped(self):
        score = _keyword_match_score(
            "test", {"docstring": None, "code": "test code"}, ["docstring", "code"]
        )
        assert score > 0.0

    def test_non_string_field_skipped(self):
        score = _keyword_match_score(
            "42", {"count": 42, "content": "42 items"}, ["count", "content"]
        )
        assert score > 0.0


# ---------------------------------------------------------------------------
# Integration tests: keyword search via Searcher
# ---------------------------------------------------------------------------


class TestKeywordSearchMemories:
    """Keyword search on the memories collection."""

    async def test_finds_exact_content_match(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "async/await", search_mode="keyword"
        )
        assert len(results) >= 1
        assert isinstance(results[0], MemoryResult)
        assert "async/await" in results[0].content.lower()

    async def test_keyword_search_no_embedding_call(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
        mock_embedding_service: AsyncMock,
    ):
        """Keyword search should not call the embedding service."""
        await _seed_memories(memory_store)
        await searcher_with_memory_store.search_memories(
            "dataclasses", search_mode="keyword"
        )
        mock_embedding_service.embed.assert_not_called()

    async def test_keyword_returns_empty_for_no_match(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "zzz_nonexistent_zzz", search_mode="keyword"
        )
        assert results == []

    async def test_keyword_with_category_filter(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_memories(memory_store)
        # All seeded entries are "preference" category
        results = await searcher_with_memory_store.search_memories(
            "async", category="preference", search_mode="keyword"
        )
        assert len(results) >= 1

        # Non-existent category should return nothing
        results = await searcher_with_memory_store.search_memories(
            "async", category="fact", search_mode="keyword"
        )
        assert results == []

    async def test_empty_query_returns_empty(
        self,
        searcher_with_memory_store: Searcher,
    ):
        results = await searcher_with_memory_store.search_memories(
            "", search_mode="keyword"
        )
        assert results == []

        results = await searcher_with_memory_store.search_memories(
            "   ", search_mode="keyword"
        )
        assert results == []


class TestKeywordSearchCode:
    """Keyword search on the code_units collection."""

    async def test_finds_function_name(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_code(memory_store)
        results = await searcher_with_memory_store.search_code(
            "hello_world", search_mode="keyword"
        )
        assert len(results) >= 1
        assert isinstance(results[0], CodeResult)
        assert results[0].qualified_name == "hello_world"

    async def test_finds_code_substring(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_code(memory_store)
        results = await searcher_with_memory_store.search_code(
            "search_code", search_mode="keyword"
        )
        assert len(results) >= 1

    async def test_finds_in_docstring(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_code(memory_store)
        results = await searcher_with_memory_store.search_code(
            "semantically", search_mode="keyword"
        )
        assert len(results) >= 1


class TestKeywordSearchCommits:
    """Keyword search on the commits collection."""

    async def test_finds_commit_message(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_commits(memory_store)
        results = await searcher_with_memory_store.search_commits(
            "BUG-042", search_mode="keyword"
        )
        assert len(results) >= 1
        assert isinstance(results[0], CommitResult)
        assert "BUG-042" in results[0].message

    async def test_keyword_no_match(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_commits(memory_store)
        results = await searcher_with_memory_store.search_commits(
            "zzz_nonexistent_zzz", search_mode="keyword"
        )
        assert results == []


class TestKeywordSearchValues:
    """Keyword search on the values collection."""

    async def test_finds_value_text(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_values(memory_store)
        results = await searcher_with_memory_store.search_values(
            "regression tests", search_mode="keyword"
        )
        assert len(results) >= 1
        assert isinstance(results[0], ValueResult)


# ---------------------------------------------------------------------------
# Integration tests: hybrid search
# ---------------------------------------------------------------------------


class TestHybridSearch:
    """Tests for hybrid (semantic + keyword boost) mode."""

    async def test_hybrid_returns_results(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "async/await", search_mode="hybrid"
        )
        assert len(results) >= 1
        assert isinstance(results[0], MemoryResult)

    async def test_hybrid_calls_embedding_service(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
        mock_embedding_service: AsyncMock,
    ):
        """Hybrid mode needs embedding for the semantic half."""
        await _seed_memories(memory_store)
        await searcher_with_memory_store.search_memories(
            "dataclasses", search_mode="hybrid"
        )
        mock_embedding_service.embed.assert_called()

    async def test_hybrid_boosts_keyword_matches(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        """Results that match both semantic and keyword should score higher."""
        await _seed_memories(memory_store)
        # "async/await" should match via keyword and also appear in semantic
        hybrid_results = await searcher_with_memory_store.search_memories(
            "async/await", search_mode="hybrid"
        )
        # Verify at least one result has async/await content
        matching = [r for r in hybrid_results if "async/await" in r.content.lower()]
        assert len(matching) >= 1

    async def test_hybrid_code_search(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_code(memory_store)
        results = await searcher_with_memory_store.search_code(
            "hello_world", search_mode="hybrid"
        )
        assert len(results) >= 1
        assert isinstance(results[0], CodeResult)


# ---------------------------------------------------------------------------
# Semantic mode backward compatibility
# ---------------------------------------------------------------------------


class TestSemanticModeBackwardCompat:
    """Semantic mode (default) still works as before."""

    async def test_default_mode_is_semantic(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
        mock_embedding_service: AsyncMock,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "async"
        )
        # Semantic mode should call embed
        mock_embedding_service.embed.assert_called_once_with("async")
        # Should return MemoryResult instances (all 3 seeded items with
        # the mock embedder will have the same vector so all have equal scores)
        assert all(isinstance(r, MemoryResult) for r in results)

    async def test_explicit_semantic_mode(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
        mock_embedding_service: AsyncMock,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "test", search_mode="semantic"
        )
        mock_embedding_service.embed.assert_called_once_with("test")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestSearchModeValidation:
    """Test that invalid search modes are rejected consistently."""

    async def test_invalid_mode_memories(
        self, searcher_with_memory_store: Searcher
    ):
        with pytest.raises(InvalidSearchModeError):
            await searcher_with_memory_store.search_memories(
                "test", search_mode="bad"
            )

    async def test_invalid_mode_code(
        self, searcher_with_memory_store: Searcher
    ):
        with pytest.raises(InvalidSearchModeError):
            await searcher_with_memory_store.search_code(
                "test", search_mode="bad"
            )

    async def test_invalid_mode_commits(
        self, searcher_with_memory_store: Searcher
    ):
        with pytest.raises(InvalidSearchModeError):
            await searcher_with_memory_store.search_commits(
                "test", search_mode="bad"
            )

    async def test_invalid_mode_values(
        self, searcher_with_memory_store: Searcher
    ):
        with pytest.raises(InvalidSearchModeError):
            await searcher_with_memory_store.search_values(
                "test", search_mode="bad"
            )

    async def test_invalid_mode_experiences(
        self, searcher_with_memory_store: Searcher
    ):
        with pytest.raises(InvalidSearchModeError):
            await searcher_with_memory_store.search_experiences(
                "test", search_mode="bad"
            )

    def test_valid_modes_constant(self):
        assert "semantic" in VALID_SEARCH_MODES
        assert "keyword" in VALID_SEARCH_MODES
        assert "hybrid" in VALID_SEARCH_MODES
        assert len(VALID_SEARCH_MODES) == 3


# ---------------------------------------------------------------------------
# Collection not found handling in keyword mode
# ---------------------------------------------------------------------------


class TestKeywordCollectionNotFound:
    """Keyword search on non-existent collection raises appropriate error."""

    async def test_keyword_missing_collection_with_mock(
        self, mock_embedding_service: AsyncMock
    ):
        """Mock vector store that raises 'collection not found' pattern."""
        store = AsyncMock(spec=VectorStore)
        store.scroll.side_effect = Exception("Collection not found")
        searcher = Searcher(mock_embedding_service, store)
        with pytest.raises(CollectionNotFoundError):
            await searcher.search_memories("test", search_mode="keyword")

    async def test_keyword_missing_collection_raises(
        self, mock_embedding_service: AsyncMock
    ):
        """MemoryStore raises ValueError for missing collections."""
        store = MemoryStore()  # no collections created
        searcher = Searcher(mock_embedding_service, store)
        with pytest.raises(ValueError):
            await searcher.search_memories("test", search_mode="keyword")

    async def test_hybrid_missing_collection(
        self, mock_embedding_service: AsyncMock
    ):
        store = MemoryStore()
        searcher = Searcher(mock_embedding_service, store)
        with pytest.raises(Exception):
            # hybrid does semantic first, which will fail on missing collection
            await searcher.search_memories("test", search_mode="hybrid")


# ---------------------------------------------------------------------------
# Limit enforcement
# ---------------------------------------------------------------------------


class TestKeywordSearchLimit:
    """Keyword search respects the limit parameter."""

    async def test_respects_limit(
        self,
        searcher_with_memory_store: Searcher,
        memory_store: MemoryStore,
    ):
        await _seed_memories(memory_store)
        results = await searcher_with_memory_store.search_memories(
            "async", search_mode="keyword", limit=1
        )
        assert len(results) <= 1
