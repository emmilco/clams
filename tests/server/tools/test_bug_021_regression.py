"""Regression test for BUG-021: search_experiences returns internal server error.

Tests that search_experiences properly converts ExperienceResult dataclasses
to JSON-serializable dicts rather than returning raw dataclass objects.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pytest

from clams.server.tools.search import get_search_tools
from clams.search import Searcher
from unittest.mock import AsyncMock, MagicMock


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
    surprise: Optional[str]
    root_cause: Optional[MockRootCause]
    lesson: Optional[MockLesson]
    confidence_tier: str
    iteration_count: int
    score: float
    created_at: datetime


@pytest.mark.asyncio
async def test_bug_021_regression_search_experiences_serialization() -> None:
    """Test that search_experiences returns JSON-serializable dicts.

    Regression test for BUG-021 where search_experiences returned raw
    dataclass objects that couldn't be JSON serialized, causing internal_error.
    """
    # Setup: Mock Searcher that returns ExperienceResult dataclasses
    mock_searcher = MagicMock(spec=Searcher)

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
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    mock_searcher.search_experiences = AsyncMock(return_value=[mock_result])

    tools = get_search_tools(mock_searcher)
    search_experiences = tools["search_experiences"]

    # Action: call search_experiences
    result = await search_experiences(query="debugging memory", limit=5)

    # Assert: should return dict that can be JSON serialized
    assert "error" not in result, f"Unexpected error: {result}"
    assert result["count"] == 1
    assert len(result["results"]) == 1

    exp = result["results"][0]

    # Verify all fields are present and are proper types (not dataclasses)
    assert exp["id"] == "exp_123"
    assert exp["ghap_id"] == "ghap_456"
    assert exp["axis"] == "full"
    assert exp["domain"] == "debugging"
    assert exp["strategy"] == "systematic-elimination"
    assert exp["goal"] == "Find the bug"
    assert exp["hypothesis"] == "It's in the parser"
    assert exp["action"] == "Add logging"
    assert exp["prediction"] == "Will see error in logs"
    assert exp["outcome_status"] == "confirmed"
    assert exp["outcome_result"] == "Found the issue"
    assert exp["surprise"] == "It was faster than expected"
    assert exp["confidence_tier"] == "high"
    assert exp["iteration_count"] == 2
    assert exp["score"] == 0.95
    assert exp["created_at"] == "2025-01-01T12:00:00+00:00"

    # Verify nested objects are dicts, not dataclasses
    assert isinstance(exp["root_cause"], dict)
    assert exp["root_cause"]["category"] == "incomplete_information"
    assert exp["root_cause"]["description"] == "Missing context"

    assert isinstance(exp["lesson"], dict)
    assert exp["lesson"]["what_worked"] == "Logging helped"
    assert exp["lesson"]["takeaway"] == "Always add logging"


@pytest.mark.asyncio
async def test_bug_021_search_experiences_empty_results() -> None:
    """Test that search_experiences handles empty results correctly."""
    mock_searcher = MagicMock(spec=Searcher)
    mock_searcher.search_experiences = AsyncMock(return_value=[])

    tools = get_search_tools(mock_searcher)
    search_experiences = tools["search_experiences"]

    result = await search_experiences(query="nonexistent", limit=5)

    assert "error" not in result
    assert result["count"] == 0
    assert result["results"] == []
