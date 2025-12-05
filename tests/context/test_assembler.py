"""Tests for ContextAssembler."""

from datetime import UTC, datetime

import pytest

from learning_memory_server.context.assembler import ContextAssembler
from learning_memory_server.context.models import InvalidContextTypeError
from learning_memory_server.context.searcher_types import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    MemoryResult,
    Searcher,
    ValueResult,
)


class MockSearcher(Searcher):
    """Mock searcher for testing."""

    def __init__(self) -> None:
        """Initialize mock with empty results."""
        self.memories: list[MemoryResult] = []
        self.code: list[CodeResult] = []
        self.experiences: list[ExperienceResult] = []
        self.values: list[ValueResult] = []
        self.commits: list[CommitResult] = []

    async def search_memories(
        self, query: str, limit: int = 20
    ) -> list[MemoryResult]:
        """Mock memory search."""
        return self.memories[:limit]

    async def search_code(
        self, query: str, limit: int = 20
    ) -> list[CodeResult]:
        """Mock code search."""
        return self.code[:limit]

    async def search_experiences(
        self,
        query: str,
        axis: str = "full",
        domain: str | None = None,
        strategy: str | None = None,
        outcome: str | None = None,
        limit: int = 20,
    ) -> list[ExperienceResult]:
        """Mock experience search."""
        # Filter by axis if needed
        filtered = [exp for exp in self.experiences if exp.axis == axis]

        # Apply domain filter
        if domain:
            filtered = [exp for exp in filtered if exp.domain == domain]

        # Apply strategy filter
        if strategy:
            filtered = [exp for exp in filtered if exp.strategy == strategy]

        # Apply outcome filter
        if outcome:
            filtered = [exp for exp in filtered if exp.outcome_status == outcome]

        return filtered[:limit]

    async def search_values(
        self, query: str, limit: int = 5
    ) -> list[ValueResult]:
        """Mock value search."""
        return self.values[:limit]

    async def search_commits(
        self, query: str, limit: int = 20
    ) -> list[CommitResult]:
        """Mock commit search."""
        return self.commits[:limit]


@pytest.fixture
def mock_searcher() -> MockSearcher:
    """Create a mock searcher."""
    return MockSearcher()


@pytest.fixture
def assembler(mock_searcher: MockSearcher) -> ContextAssembler:
    """Create a context assembler with mock searcher."""
    return ContextAssembler(mock_searcher)


@pytest.mark.asyncio
async def test_assemble_single_source_memories(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test assembly with single memory source."""
    mock_searcher.memories = [
        MemoryResult(
            id="mem_1",
            category="preference",
            content="Use async/await",
            score=0.95,
            importance=0.8,
            tags=["coding"],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )
    ]

    result = await assembler.assemble_context(
        query="coding preferences",
        context_types=["memories"],
        max_tokens=1000,
    )

    assert len(result.items) == 1
    assert "Memory" in result.markdown
    assert "Use async/await" in result.markdown
    assert result.token_count > 0
    assert result.sources_used["memories"] == 1


@pytest.mark.asyncio
async def test_assemble_multiple_sources(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test assembly with multiple sources."""
    mock_searcher.memories = [
        MemoryResult(
            id="mem_1",
            category="fact",
            content="Python uses indentation",
            score=0.9,
            importance=0.7,
            tags=[],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )
    ]

    mock_searcher.code = [
        CodeResult(
            id="code_1",
            unit_type="function",
            qualified_name="test.example",
            file_path="test.py",
            start_line=1,
            end_line=5,
            language="python",
            code="def example():\n    pass",
            docstring="Test function",
            score=0.85,
        )
    ]

    result = await assembler.assemble_context(
        query="python examples",
        context_types=["memories", "code"],
        max_tokens=2000,
    )

    assert len(result.items) == 2
    assert "## Memories" in result.markdown
    assert "## Code" in result.markdown
    assert result.sources_used["memories"] == 1
    assert result.sources_used["code"] == 1


@pytest.mark.asyncio
async def test_invalid_context_type(assembler: ContextAssembler) -> None:
    """Test error on invalid context type."""
    with pytest.raises(InvalidContextTypeError) as exc_info:
        await assembler.assemble_context(
            query="test",
            context_types=["invalid_type"],
        )

    assert "invalid_type" in str(exc_info.value)
    assert "memories" in str(exc_info.value)  # Should list valid types


@pytest.mark.asyncio
async def test_empty_results(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test handling of empty results."""
    # mock_searcher has no results by default

    result = await assembler.assemble_context(
        query="nothing",
        context_types=["memories", "code"],
        max_tokens=1000,
    )

    assert len(result.items) == 0
    assert result.sources_used.get("memories", 0) == 0
    assert result.sources_used.get("code", 0) == 0


@pytest.mark.asyncio
async def test_token_budget_distribution(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test token budget is distributed correctly."""
    # Create many distinct memories with different content
    distinct_contents = [
        "Python uses indentation for blocks",
        "JavaScript has async functions",
        "Rust has ownership model",
        "Go has goroutines for concurrency",
        "Java uses classes and objects",
        "C++ supports templates",
        "Ruby has blocks and yields",
        "Swift uses protocols",
    ]

    mock_searcher.memories = [
        MemoryResult(
            id=f"mem_{i}",
            category="fact",
            content=distinct_contents[i],
            score=0.9 - (i * 0.01),
            importance=0.5,
            tags=[],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )
        for i in range(len(distinct_contents))
    ]

    result = await assembler.assemble_context(
        query="test",
        context_types=["memories"],
        limit=20,
        max_tokens=500,  # Limited budget
    )

    # Should fit multiple items within budget
    assert len(result.items) > 1
    assert result.token_count <= 600  # Some tolerance


@pytest.mark.asyncio
async def test_deduplication(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test deduplication across sources."""
    # Create duplicate items with same GHAP ID
    mock_searcher.experiences = [
        ExperienceResult(
            id="exp_1",
            ghap_id="ghap_123",
            axis="full",
            domain="debugging",
            strategy="systematic",
            goal="Fix bug",
            hypothesis="Null check",
            action="Added check",
            prediction="Will fix",
            outcome_status="confirmed",
            outcome_result="Fixed",
            surprise=None,
            root_cause=None,
            lesson=None,
            confidence_tier="gold",
            iteration_count=1,
            score=0.8,
            created_at=datetime.now(UTC),
        )
    ]

    mock_searcher.values = [
        ValueResult(
            id="val_1",
            axis="strategy",
            cluster_id="cluster_1",
            cluster_size=5,
            text="Always verify",
            similarity_to_centroid=0.9,
            score=0.9,  # Higher score
        )
    ]

    # Add ghap_id to value to trigger deduplication
    mock_searcher.values[0].__dict__["ghap_id"] = "ghap_123"

    result = await assembler.assemble_context(
        query="test",
        context_types=["experiences", "values"],
        max_tokens=2000,
    )

    # Should deduplicate and keep the higher score (value)
    assert len(result.items) == 1
    assert result.items[0].source == "value"


@pytest.mark.asyncio
async def test_premortem_context(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test premortem context generation."""
    mock_searcher.experiences = [
        ExperienceResult(
            id="exp_1",
            ghap_id="ghap_1",
            axis="full",
            domain="debugging",
            strategy="systematic",
            goal="Fix bug",
            hypothesis="Null pointer",
            action="Added check",
            prediction="Will fix",
            outcome_status="falsified",
            outcome_result="Still failing",
            surprise="Different cause",
            root_cause=None,
            lesson=None,
            confidence_tier="gold",
            iteration_count=1,
            score=0.9,
            created_at=datetime.now(UTC),
        ),
        ExperienceResult(
            id="exp_2",
            ghap_id="ghap_2",
            axis="surprise",
            domain="debugging",
            strategy="systematic",
            goal="Fix bug",
            hypothesis="Race condition",
            action="Added lock",
            prediction="Will fix",
            outcome_status="confirmed",
            outcome_result="Fixed",
            surprise="Unexpected timing",
            root_cause=None,
            lesson=None,
            confidence_tier="silver",
            iteration_count=2,
            score=0.85,
            created_at=datetime.now(UTC),
        ),
    ]

    result = await assembler.get_premortem_context(
        domain="debugging",
        strategy="systematic",
    )

    assert "Premortem: debugging" in result.markdown
    assert "systematic" in result.markdown
    assert "## Common Failures" in result.markdown
    assert "## Unexpected Outcomes" in result.markdown


@pytest.mark.asyncio
async def test_premortem_partial_failure(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test premortem handles partial query failures gracefully."""
    # Create a mock that raises for surprise axis
    original_search = mock_searcher.search_experiences

    async def failing_search(
        query: str,
        axis: str = "full",
        domain: str | None = None,
        strategy: str | None = None,
        outcome: str | None = None,
        limit: int = 20,
    ) -> list[ExperienceResult]:
        if axis == "surprise":
            raise Exception("Surprise axis failed")
        return await original_search(
            query, axis, domain, strategy, outcome, limit
        )

    mock_searcher.search_experiences = failing_search  # type: ignore

    # Should not crash, just log warning and continue
    result = await assembler.get_premortem_context(domain="debugging")

    # Should still return something (even if partial)
    assert result.markdown is not None
    assert "Premortem: debugging" in result.markdown


@pytest.mark.asyncio
async def test_partial_source_failure(
    assembler: ContextAssembler, mock_searcher: MockSearcher
) -> None:
    """Test handling when one source fails."""
    # Make code search fail
    async def failing_code_search(
        query: str, limit: int = 20
    ) -> list[CodeResult]:
        raise Exception("Code search failed")

    mock_searcher.search_code = failing_code_search  # type: ignore

    # Add valid memory
    mock_searcher.memories = [
        MemoryResult(
            id="mem_1",
            category="fact",
            content="Test memory",
            score=0.9,
            importance=0.5,
            tags=[],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )
    ]

    # Should not crash, should return partial results
    result = await assembler.assemble_context(
        query="test",
        context_types=["memories", "code"],
    )

    # Should have memory result
    assert len(result.items) == 1
    assert result.items[0].source == "memory"
    # Code source should be absent or have 0 items
    assert result.sources_used.get("code", 0) == 0
