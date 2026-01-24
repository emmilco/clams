"""Validation tests for search and pagination with production-like data.

These tests verify search operations handle realistic result set sizes
and score distributions correctly.

Reference: SPEC-034 Search/Pagination Scenarios 4-5
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from clams.embedding.mock import MockEmbedding
from clams.search.searcher import Searcher
from clams.storage.base import SearchResult
from tests.fixtures.data_profiles import MemoryProfile
from tests.fixtures.generators.memories import GeneratedMemory, generate_memories


class TestLargeResultSetPagination:
    """Scenario 4: Large Result Set Pagination.

    Verify pagination works correctly with 200+ items.
    """

    @pytest.fixture
    def large_memory_corpus(self) -> list[GeneratedMemory]:
        """Generate 250 memories for pagination testing."""
        profile = MemoryProfile(count=250)
        return generate_memories(profile, seed=42)

    @pytest.fixture
    def mock_vector_store(self, large_memory_corpus: list[GeneratedMemory]) -> AsyncMock:
        """Mock vector store that simulates pagination."""
        store = AsyncMock()

        # Store the corpus for pagination simulation
        store._corpus = large_memory_corpus

        async def search_impl(
            collection: str,
            query: object,
            limit: int,
            filters: dict[str, object] | None = None,
        ) -> list[SearchResult]:
            # Simulate search with pagination
            corpus = store._corpus

            # Apply filters if present
            if filters and "category" in filters:
                corpus = [m for m in corpus if m.category == filters["category"]]

            # Simulate relevance scoring (all items get some score)
            results = []
            now = datetime.now(UTC).isoformat()
            for i, mem in enumerate(corpus):
                # Score decreases with index (simulating relevance ranking)
                score = 0.95 - (i * 0.003)  # Scores from 0.95 down
                results.append(
                    SearchResult(
                        id=mem.id,
                        score=max(0.1, score),  # Floor at 0.1
                        payload={
                            "content": mem.content,
                            "category": mem.category,
                            "importance": mem.importance,
                            "tags": mem.tags,
                            "created_at": now,
                        },
                    )
                )

            # Return requested limit
            return results[:limit]

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher(self, mock_vector_store: AsyncMock) -> Searcher:
        """Create searcher with mock dependencies."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_vector_store)

    @pytest.mark.asyncio
    async def test_no_duplicates_within_page(
        self,
        searcher: Searcher,
    ) -> None:
        """Verify no duplicate results within a single page."""
        results_page = await searcher.search_memories("test query", limit=50)

        # No duplicates within page
        ids = [r.id for r in results_page]
        assert len(ids) == len(set(ids)), "Duplicates found within page"

    @pytest.mark.asyncio
    async def test_boundary_conditions(
        self,
        searcher: Searcher,
    ) -> None:
        """Test pagination boundary conditions."""
        # First page
        first_page = await searcher.search_memories("test", limit=20)
        assert len(first_page) == 20, "First page should be full"

        # Request more than available
        all_results = await searcher.search_memories("test", limit=300)
        assert len(all_results) <= 250, "Should not exceed corpus size"

        # Exact fit (if corpus is 250, request 250)
        exact_results = await searcher.search_memories("test", limit=250)
        assert len(exact_results) == 250

    @pytest.mark.asyncio
    async def test_results_ordered_by_score(
        self,
        searcher: Searcher,
    ) -> None:
        """Verify results are ordered by decreasing score."""
        results = await searcher.search_memories("test", limit=50)

        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not monotonically decreasing at index {i}: "
                f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )


class TestScoreDistributionHandling:
    """Scenario 5: Score Distribution Handling.

    Verify search handles long-tail score distributions correctly.
    """

    @pytest.fixture
    def mock_store_with_score_distribution(self) -> AsyncMock:
        """Mock store returning results with long-tail score distribution."""
        store = AsyncMock()

        async def search_with_distribution(
            collection: str,
            query: object,
            limit: int,
            filters: dict[str, object] | None = None,
        ) -> list[SearchResult]:
            # Generate 100 results with long-tail distribution
            # Few high scores, many moderate/low scores
            results = []
            now = datetime.now(UTC).isoformat()
            for i in range(100):
                if i < 5:
                    score = 0.95 - (i * 0.02)  # Top 5: 0.95, 0.93, 0.91, ...
                elif i < 20:
                    score = 0.80 - ((i - 5) * 0.02)  # Next 15: 0.80 down to 0.50
                else:
                    score = 0.45 - ((i - 20) * 0.005)  # Rest: 0.45 down to 0.05

                results.append(
                    SearchResult(
                        id=f"result_{i}",
                        score=max(0.05, score),
                        payload={
                            "content": f"Result content {i}",
                            "category": "fact",
                            "importance": 0.5,
                            "tags": [],
                            "created_at": now,
                        },
                    )
                )

            # Return requested limit
            return results[:limit]

        store.search = search_with_distribution
        return store

    @pytest.fixture
    def searcher_with_distribution(
        self, mock_store_with_score_distribution: AsyncMock
    ) -> Searcher:
        """Create searcher with score distribution mock."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store_with_score_distribution)

    @pytest.mark.asyncio
    async def test_ranking_is_stable(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify ranking is consistent across calls."""
        results1 = await searcher_with_distribution.search_memories("test", limit=20)
        results2 = await searcher_with_distribution.search_memories("test", limit=20)

        # Same query should return same ranking
        ids1 = [r.id for r in results1]
        ids2 = [r.id for r in results2]

        assert ids1 == ids2, "Ranking should be stable for same query"

    @pytest.mark.asyncio
    async def test_scores_are_monotonically_decreasing(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify results are ordered by decreasing score."""
        results = await searcher_with_distribution.search_memories("test", limit=50)

        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not monotonically decreasing: "
                f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )

    @pytest.mark.asyncio
    async def test_low_score_results_excluded_by_limit(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify limit parameter excludes low-scoring results."""
        results_10 = await searcher_with_distribution.search_memories("test", limit=10)
        results_50 = await searcher_with_distribution.search_memories("test", limit=50)

        # Top 10 should have higher average score than top 50
        avg_score_10 = sum(r.score for r in results_10) / len(results_10)
        avg_score_50 = sum(r.score for r in results_50) / len(results_50)

        assert avg_score_10 > avg_score_50, (
            f"Top 10 avg ({avg_score_10:.3f}) should exceed "
            f"top 50 avg ({avg_score_50:.3f})"
        )
