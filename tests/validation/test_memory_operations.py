"""Validation tests for memory operations with production-like data.

Reference: SPEC-034 Memory Operations Scenarios 6-7
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from clams.embedding.mock import MockEmbedding
from clams.search.searcher import Searcher
from clams.storage.base import SearchResult
from tests.fixtures.data_profiles import MEMORY_PRODUCTION, MemoryProfile
from tests.fixtures.generators.memories import GeneratedMemory, generate_memories


class TestCategorySkewHandling:
    """Scenario 6: Category Skew Handling.

    Verify search handles skewed category distributions correctly.
    """

    @pytest.fixture
    def skewed_category_corpus(self) -> list[GeneratedMemory]:
        """Generate corpus with 80% in one category."""
        profile = MemoryProfile(
            count=100,
            category_distribution={"fact": 0.8, "preference": 0.1, "workflow": 0.1},
        )
        return generate_memories(profile, seed=42)

    @pytest.fixture
    def mock_store(self, skewed_category_corpus: list[GeneratedMemory]) -> AsyncMock:
        """Mock store with skewed category corpus."""
        store = AsyncMock()
        corpus = skewed_category_corpus

        async def search_impl(
            collection: str,
            query: object,
            limit: int,
            filters: dict[str, object] | None = None,
        ) -> list[SearchResult]:
            results_corpus = list(corpus)

            # Apply category filter
            if filters and "category" in filters:
                results_corpus = [
                    m for m in results_corpus if m.category == filters["category"]
                ]

            results = []
            now = datetime.now(UTC).isoformat()
            for i, mem in enumerate(results_corpus[:limit]):
                results.append(
                    SearchResult(
                        id=mem.id,
                        score=0.9 - (i * 0.01),
                        payload={
                            "content": mem.content,
                            "category": mem.category,
                            "importance": mem.importance,
                            "tags": mem.tags,
                            "created_at": now,
                        },
                    )
                )

            return results

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher(self, mock_store: AsyncMock) -> Searcher:
        """Create searcher with skewed corpus."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store)

    @pytest.mark.asyncio
    async def test_category_filter_works_with_skew(
        self,
        searcher: Searcher,
        skewed_category_corpus: list[GeneratedMemory],
    ) -> None:
        """Category filter should work correctly even with skewed distribution."""
        # Filter for minority category
        results = await searcher.search_memories(
            "test query",
            category="preference",
            limit=50,
        )

        # Should only get preference category (10% of 100 = ~10)
        for r in results:
            assert r.category == "preference", (
                f"Got {r.category}, expected preference"
            )

        # Should have found the minority items
        assert len(results) > 0, "Should find some preference memories"

    @pytest.mark.asyncio
    async def test_unfiltered_search_includes_dominant_category(
        self,
        searcher: Searcher,
    ) -> None:
        """Unfiltered search should include items from dominant category."""
        results = await searcher.search_memories("test query", limit=20)

        # Results should include items from dominant category
        categories = set(r.category for r in results)
        assert "fact" in categories, "Should include dominant category"


class TestLargeMemoryCorpus:
    """Scenario 7: Large Memory Corpus Testing.

    Verify operations with 500 memories complete in acceptable time.
    """

    @pytest.fixture
    def large_corpus(self) -> list[GeneratedMemory]:
        """Generate 500 memories with varied content lengths."""
        return generate_memories(MEMORY_PRODUCTION, seed=42)

    @pytest.fixture
    def mock_store(self, large_corpus: list[GeneratedMemory]) -> AsyncMock:
        """Mock store with large corpus."""
        store = AsyncMock()

        async def search_impl(
            collection: str,
            query: object,
            limit: int,
            filters: dict[str, object] | None = None,
        ) -> list[SearchResult]:
            results = []
            now = datetime.now(UTC).isoformat()
            for i, mem in enumerate(large_corpus[:limit]):
                results.append(
                    SearchResult(
                        id=mem.id,
                        score=0.95 - (i * 0.001),
                        payload={
                            "content": mem.content,
                            "category": mem.category,
                            "importance": mem.importance,
                            "tags": mem.tags,
                            "created_at": now,
                        },
                    )
                )
            return results

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher_large(self, mock_store: AsyncMock) -> Searcher:
        """Create searcher with large corpus."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store)

    @pytest.mark.asyncio
    @pytest.mark.timeout(1)  # 1 second timeout per spec
    async def test_search_returns_under_1s(
        self,
        searcher_large: Searcher,
    ) -> None:
        """Search should return in < 1 second for 500-memory corpus."""
        results = await searcher_large.search_memories("test query", limit=100)
        assert len(results) == 100

    def test_handles_content_length_variation(
        self,
        large_corpus: list[GeneratedMemory],
    ) -> None:
        """Search should handle varied content lengths correctly."""
        # Content lengths should vary significantly
        lengths = [len(m.content) for m in large_corpus]
        min_len, max_len = min(lengths), max(lengths)

        assert max_len > min_len * 5, (
            f"Content length variation too low: min={min_len}, max={max_len}"
        )


class TestMemoryGeneratorProperties:
    """Verify memory generator produces expected properties."""

    def test_category_distribution_matches_profile(self) -> None:
        """Generated categories should approximately match profile distribution."""
        profile = MemoryProfile(
            count=1000,  # Large sample for statistical stability
            category_distribution={"fact": 0.6, "preference": 0.2, "workflow": 0.2},
        )

        memories = generate_memories(profile, seed=42)

        # Count categories
        category_counts: dict[str, int] = {}
        for m in memories:
            category_counts[m.category] = category_counts.get(m.category, 0) + 1

        # Check distribution (allow 10% tolerance)
        for category, expected_ratio in profile.category_distribution.items():
            actual_ratio = category_counts.get(category, 0) / len(memories)
            assert abs(actual_ratio - expected_ratio) < 0.1, (
                f"Category '{category}' ratio {actual_ratio:.2f} differs from "
                f"expected {expected_ratio:.2f}"
            )

    def test_importance_bimodal_distribution(self) -> None:
        """Bimodal importance should have distinct low and high groups."""
        profile = MemoryProfile(
            count=500,
            importance_distribution="bimodal",
        )

        memories = generate_memories(profile, seed=42)
        importances = [m.importance for m in memories]

        # Bimodal: 70% in 0.2-0.5, 30% in 0.8-1.0
        low_count = sum(1 for imp in importances if 0.2 <= imp <= 0.5)
        high_count = sum(1 for imp in importances if 0.8 <= imp <= 1.0)

        # Allow 15% tolerance
        assert abs(low_count / len(memories) - 0.7) < 0.15
        assert abs(high_count / len(memories) - 0.3) < 0.15

    def test_content_length_within_range(self) -> None:
        """Content lengths should be within profile range."""
        min_len, max_len = 50, 500
        profile = MemoryProfile(
            count=100,
            content_length_range=(min_len, max_len),
        )

        memories = generate_memories(profile, seed=42)

        for m in memories:
            assert min_len <= len(m.content) <= max_len, (
                f"Content length {len(m.content)} outside range [{min_len}, {max_len}]"
            )

    def test_reproducibility(self) -> None:
        """Same seed should produce identical results."""
        profile = MemoryProfile(count=50)

        memories1 = generate_memories(profile, seed=42)
        memories2 = generate_memories(profile, seed=42)

        for m1, m2 in zip(memories1, memories2):
            assert m1.id == m2.id
            assert m1.content == m2.content
            assert m1.category == m2.category
            assert m1.importance == m2.importance
