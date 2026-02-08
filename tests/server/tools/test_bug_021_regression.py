"""Regression test for BUG-021: search_experiences returns internal server error.

Tests that search_experiences properly converts ExperienceResult dataclasses
to JSON-serializable dicts rather than returning raw dataclass objects.

Note: search_experiences is now part of get_learning_tools (not get_search_tools).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from calm.tools.learning import get_learning_tools


@dataclass
class MockRootCause:
    category: str
    description: str


@dataclass
class MockLesson:
    what_worked: str
    takeaway: str


@dataclass
class MockExperienceResult:
    """Mock ExperienceResult for testing."""

    id: str
    ghap_id: str
    axis: str
    domain: str
    strategy: str
    goal: str
    hypothesis: str
    action: str
    prediction: str
    outcome_status: str
    outcome_result: str
    surprise: str | None
    root_cause: MockRootCause | None
    lesson: MockLesson | None
    confidence_tier: str
    iteration_count: int
    score: float
    created_at: datetime


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_semantic_embedder() -> AsyncMock:
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.dimension = 768
    return service


@pytest.mark.asyncio
async def test_bug_021_regression_search_experiences_serialization(
    mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
) -> None:
    """Test that search_experiences returns JSON-serializable dicts.

    Regression test for BUG-021 where search_experiences returned raw
    dataclass objects that couldn't be JSON serialized, causing internal_error.
    """
    mock_result = MockExperienceResult(
        id="exp_123",
        ghap_id="ghap_456",
        axis="full",
        domain="debugging",
        strategy="systematic-elimination",
        goal="Find the bug",
        hypothesis="It's in the parser",
        action="Add logging",
        prediction="Will see error in logs",
        outcome_status="confirmed",
        outcome_result="Found the issue",
        surprise="It was faster than expected",
        root_cause=MockRootCause(
            category="incomplete_information", description="Missing context"
        ),
        lesson=MockLesson(what_worked="Logging helped", takeaway="Always add logging"),
        confidence_tier="high",
        iteration_count=2,
        score=0.95,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    # Mock the searcher via the vector store's search
    mock_vector_store.search = AsyncMock(return_value=[
        MagicMock(
            id="exp_123",
            score=0.95,
            payload={
                "id": "exp_123",
                "ghap_id": "ghap_456",
                "axis": "full",
                "domain": "debugging",
                "strategy": "systematic-elimination",
                "goal": "Find the bug",
                "hypothesis": "It's in the parser",
                "action": "Add logging",
                "prediction": "Will see error in logs",
                "outcome_status": "confirmed",
                "outcome_result": "Found the issue",
                "surprise": "It was faster than expected",
                "root_cause": {"category": "incomplete_information", "description": "Missing context"},
                "lesson": {"what_worked": "Logging helped", "takeaway": "Always add logging"},
                "confidence_tier": "high",
                "iteration_count": 2,
                "created_at": "2025-01-01T12:00:00+00:00",
            },
        )
    ])

    tools = get_learning_tools(mock_vector_store, mock_semantic_embedder)
    search_experiences = tools["search_experiences"]

    # Action: call search_experiences
    result = await search_experiences(query="debugging memory", limit=5)

    # Assert: should return dict that can be JSON serialized
    assert "error" not in result, f"Unexpected error: {result}"
    assert result["count"] == 1
    assert len(result["results"]) == 1

    exp = result["results"][0]

    # Verify key fields are present
    assert exp["id"] == "exp_123"
    assert exp["domain"] == "debugging"
    assert exp["strategy"] == "systematic-elimination"
    assert exp["goal"] == "Find the bug"
    assert exp["outcome_status"] == "confirmed"


@pytest.mark.asyncio
async def test_bug_021_search_experiences_empty_results(
    mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
) -> None:
    """Test that search_experiences handles empty results correctly."""
    tools = get_learning_tools(mock_vector_store, mock_semantic_embedder)
    search_experiences = tools["search_experiences"]

    result = await search_experiences(query="nonexistent", limit=5)

    assert "error" not in result
    assert result["count"] == 0
    assert result["results"] == []
