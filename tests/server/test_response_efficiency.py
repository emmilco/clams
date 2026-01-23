"""Tests for response size efficiency.

This module verifies that tool responses stay within token-efficient byte limits.
Size limits are designed to prevent excessive token waste during LLM interactions.

GHAP Size Limits Rationale (SPEC-044, BUG-030):
- 500 bytes for confirmations (start/update/resolve): UUID (36 chars) + status +
  JSON overhead fits in ~100-200 bytes. 500 bytes provides headroom while catching
  bloat like full entries (~2KB+).
- 2000 bytes for get_active (with entry): Returns full entry with all fields.
  Typical entries are 800-1500 bytes.
- 500 bytes for get_active (no entry): Should return minimal empty state.
- 500 bytes per entry for list: Summaries only (ID, domain, status).
  Each summary should be ~100-200 bytes.

Memory Size Limits Rationale (SPEC-045):
- 500 bytes for store_memory: Store operations need only return confirmation + memory ID.
  A UUID (36 chars) + status + category + timestamps fits in ~150-200 bytes.
- 1000 bytes per entry for retrieve_memories: Retrieved memories include content
  (for search context) but should have bounded content.
- 500 bytes per entry for list_memories: Metadata only (id, category, importance,
  created_at). No content needed for browsing/filtering.
- 300 bytes for delete_memory: Simplest operation - just needs confirmation.

Reference: BUG-030 - GHAP tools wasted ~50k tokens during bulk generation.
"""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.observation import (
    ObservationCollector,
    ObservationPersister,
)
from clams.server.tools.ghap import get_ghap_tools
from clams.server.tools.memory import get_memory_tools

# Size limits in bytes (exclusive - responses must be LESS than these values)
# See module docstring for rationale
MAX_CONFIRMATION_SIZE = 500  # For start/update/resolve - minimal confirmation only
MAX_FULL_ENTRY_SIZE = 2000  # For get_active with entry - full entry expected
MAX_EMPTY_STATE_SIZE = 500  # For get_active without entry - minimal empty state
MAX_ENTRY_SUMMARY_SIZE = 500  # For list_ghap_entries - per entry size limit

# Minimum size to catch broken endpoints returning empty/minimal responses
MIN_RESPONSE_SIZE = 10


@pytest.fixture
def temp_journal_path() -> Path:
    """Create a temporary journal path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def observation_collector(temp_journal_path: Path) -> ObservationCollector:
    """Create an ObservationCollector with temp path."""
    return ObservationCollector(str(temp_journal_path))


@pytest.fixture
def observation_persister() -> ObservationPersister:
    """Create a mock ObservationPersister."""
    vector_store = MagicMock()
    # Make scroll an async method that returns empty results
    vector_store.scroll = AsyncMock(return_value=[])

    # Create a mock embedding service
    embedding_service = MagicMock()
    embedding_service.embed = AsyncMock(return_value=[0.1] * 768)

    persister = ObservationPersister(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    # Mock the persist method to avoid actual persistence
    persister.persist = AsyncMock(return_value=None)
    return persister


@pytest.fixture
def tools(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> dict[str, Any]:
    """Get GHAP tools."""
    return get_ghap_tools(observation_collector, observation_persister)


class TestGHAPResponseEfficiency:
    """Verify GHAP tool responses stay within token-efficient limits.

    These tests act as regression guards to prevent verbose responses
    (like returning full entries instead of confirmations) from creeping back.
    If any test fails, it indicates a potential regression in response efficiency.

    See BUG-030 for context on why response sizes matter.
    """

    @pytest.mark.asyncio
    async def test_start_ghap_response_size(
        self, tools: dict[str, Any]
    ) -> None:
        """start_ghap should return minimal confirmation, not full entry.

        Expected response: {ok: true, id: "ghap_..."} (~60-80 bytes)
        Limit: 500 bytes provides headroom while catching bloat (full entries ~2KB+)
        """
        start_ghap = tools["start_ghap"]

        result = await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test goal for response size verification",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        response_size = len(json.dumps(result))

        # Verify response is not empty (catches broken endpoints)
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"start_ghap response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify response is within size limit
        assert response_size < MAX_CONFIRMATION_SIZE, (
            f"start_ghap response too large: {response_size} bytes >= {MAX_CONFIRMATION_SIZE} byte limit. "
            f"Response should be minimal confirmation (ok, id), not full entry. "
            f"See BUG-030 for context."
        )

    @pytest.mark.asyncio
    async def test_update_ghap_response_size(
        self, tools: dict[str, Any]
    ) -> None:
        """update_ghap should return minimal confirmation.

        Expected response: {success: true, iteration_count: N} (~40-50 bytes)
        Limit: 500 bytes provides headroom while catching bloat
        """
        start_ghap = tools["start_ghap"]
        update_ghap = tools["update_ghap"]

        # First start a GHAP entry
        await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test goal",
            hypothesis="Initial hypothesis",
            action="Initial action",
            prediction="Initial prediction",
        )

        # Update it
        result = await update_ghap(
            hypothesis="Updated hypothesis for size testing",
            action="Updated action",
        )

        response_size = len(json.dumps(result))

        # Verify response is not empty
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"update_ghap response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify response is within size limit
        assert response_size < MAX_CONFIRMATION_SIZE, (
            f"update_ghap response too large: {response_size} bytes >= {MAX_CONFIRMATION_SIZE} byte limit. "
            f"Response should be minimal confirmation (success, iteration_count). "
            f"See BUG-030 for context."
        )

    @pytest.mark.asyncio
    async def test_resolve_ghap_response_size(
        self, tools: dict[str, Any], observation_persister: ObservationPersister
    ) -> None:
        """resolve_ghap should return minimal confirmation, not full entry.

        Expected response: {ok: true, id: "ghap_..."} (~60-80 bytes)
        Limit: 500 bytes provides headroom while catching bloat
        """
        start_ghap = tools["start_ghap"]
        resolve_ghap = tools["resolve_ghap"]

        # First start a GHAP entry
        await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test goal",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        # Resolve it
        result = await resolve_ghap(
            status="confirmed",
            result="Test confirmed as expected",
            lesson={
                "what_worked": "The approach worked",
                "takeaway": "This is the key learning",
            },
        )

        response_size = len(json.dumps(result))

        # Verify response is not empty
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"resolve_ghap response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify response is within size limit
        assert response_size < MAX_CONFIRMATION_SIZE, (
            f"resolve_ghap response too large: {response_size} bytes >= {MAX_CONFIRMATION_SIZE} byte limit. "
            f"Response should be minimal confirmation (ok, id), not full entry. "
            f"See BUG-030 for context."
        )

    @pytest.mark.asyncio
    async def test_get_active_ghap_response_size_with_entry(
        self, tools: dict[str, Any]
    ) -> None:
        """get_active_ghap with an active entry should return full entry.

        Expected response: Full entry dict (~800-1500 bytes typical)
        Limit: 2000 bytes allows reasonable content (including long hypothesis/action)
        """
        start_ghap = tools["start_ghap"]
        get_active_ghap = tools["get_active_ghap"]

        # Start a GHAP entry with substantial content to test realistic sizes
        await start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="A reasonably detailed goal that describes what we're trying to achieve",
            hypothesis="A detailed hypothesis explaining what we believe is causing the issue",
            action="The specific action we are taking based on this hypothesis",
            prediction="What we expect to observe if our hypothesis is correct",
        )

        # Get active GHAP
        result = await get_active_ghap()

        response_size = len(json.dumps(result))

        # Verify response is not empty
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"get_active_ghap response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify response is within size limit
        # This is higher since full entry content is expected
        assert response_size < MAX_FULL_ENTRY_SIZE, (
            f"get_active_ghap response too large: {response_size} bytes >= {MAX_FULL_ENTRY_SIZE} byte limit. "
            f"Even a full entry should fit within this limit. "
            f"Check if extra fields were added without updating the limit."
        )

    @pytest.mark.asyncio
    async def test_get_active_ghap_response_size_no_entry(
        self, tools: dict[str, Any]
    ) -> None:
        """get_active_ghap without an active entry should return minimal empty state.

        Expected response: {has_active: false, id: null, ...} (~200-300 bytes)
        Limit: 500 bytes for empty state response
        """
        get_active_ghap = tools["get_active_ghap"]

        # Get active GHAP when none exists
        result = await get_active_ghap()

        response_size = len(json.dumps(result))

        # Verify response is not empty
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"get_active_ghap (no entry) response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify response is within size limit
        assert response_size < MAX_EMPTY_STATE_SIZE, (
            f"get_active_ghap (no entry) response too large: {response_size} bytes >= {MAX_EMPTY_STATE_SIZE} byte limit. "
            f"Empty state response should be minimal. "
            f"See BUG-030 for context."
        )

    @pytest.mark.asyncio
    async def test_list_ghap_entries_response_size_empty(
        self, tools: dict[str, Any]
    ) -> None:
        """list_ghap_entries with no entries should return minimal response.

        Expected response: {results: [], count: 0} (~20-30 bytes)
        Limit: Well under 500 bytes
        """
        list_ghap_entries = tools["list_ghap_entries"]

        # List entries when none exist
        result = await list_ghap_entries()

        response_size = len(json.dumps(result))

        # Verify response is not empty
        assert response_size >= MIN_RESPONSE_SIZE, (
            f"list_ghap_entries response too small: {response_size} bytes < {MIN_RESPONSE_SIZE} bytes. "
            "Response appears to be broken or empty."
        )

        # Verify empty list response is minimal
        assert response_size < MAX_ENTRY_SUMMARY_SIZE, (
            f"list_ghap_entries (empty) response too large: {response_size} bytes >= {MAX_ENTRY_SUMMARY_SIZE} byte limit. "
            f"Empty results response should be minimal."
        )

    @pytest.mark.asyncio
    async def test_list_ghap_entries_response_size_per_entry(
        self, observation_collector: ObservationCollector,
        observation_persister: ObservationPersister,
    ) -> None:
        """list_ghap_entries should return summaries, not full entries.

        Expected per-entry size: ~100-200 bytes (ID, domain, status, created_at)
        Limit: 500 bytes per entry catches bloat (full entries ~2KB+)
        """
        # Mock the vector store to return simulated list entries
        # This tests the response format, not the actual persistence
        num_entries = 3
        mock_results = []

        for i in range(num_entries):
            mock_entry = MagicMock()
            mock_entry.id = f"ghap_20260118_test_{i}"
            mock_entry.payload = {
                "domain": "debugging",
                "strategy": "systematic-elimination",
                "outcome_status": "confirmed",
                "confidence_tier": "silver",
                "iteration_count": 1,
                "created_at": "2026-01-18T10:00:00+00:00",
                "captured_at": 1737212400.0,  # Unix timestamp
            }
            mock_results.append(mock_entry)

        # Configure the mock vector store scroll to return our mock entries
        observation_persister._vector_store.scroll = AsyncMock(return_value=mock_results)

        # Get fresh tools with updated persister
        tools = get_ghap_tools(observation_collector, observation_persister)
        list_ghap_entries = tools["list_ghap_entries"]

        # List entries
        result = await list_ghap_entries(limit=10)

        response_size = len(json.dumps(result))

        # Verify we got the entries
        assert result["count"] == num_entries, (
            f"Expected {num_entries} entries, got {result['count']}"
        )

        # Calculate per-entry size (subtract base response overhead)
        # Base response is roughly {results: [], count: N} which is ~25-30 bytes
        base_overhead = len(json.dumps({"results": [], "count": num_entries}))
        entries_size = response_size - base_overhead
        per_entry_size = entries_size / num_entries if num_entries > 0 else 0

        # Verify per-entry size is within limit
        assert per_entry_size < MAX_ENTRY_SUMMARY_SIZE, (
            f"list_ghap_entries per-entry size too large: {per_entry_size:.0f} bytes >= {MAX_ENTRY_SUMMARY_SIZE} byte limit. "
            f"Total response: {response_size} bytes for {num_entries} entries. "
            f"List should return summaries, not full entries. "
            f"See BUG-030 for context."
        )

    @pytest.mark.asyncio
    async def test_start_ghap_error_response_size(
        self, tools: dict[str, Any]
    ) -> None:
        """Error responses should also be small (<500 bytes).

        Expected response: {error: {type, message}} (~100-200 bytes)
        """
        start_ghap = tools["start_ghap"]

        # Trigger validation error with invalid domain
        result = await start_ghap(
            domain="invalid_domain",
            strategy="systematic-elimination",
            goal="Test goal",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        response_size = len(json.dumps(result))

        # Verify error response is within size limit
        assert response_size < MAX_CONFIRMATION_SIZE, (
            f"start_ghap error response too large: {response_size} bytes >= {MAX_CONFIRMATION_SIZE} byte limit. "
            f"Error responses should be concise."
        )

        # Verify it's actually an error response
        assert "error" in result, "Expected error response for invalid domain"


class TestMemoryResponseEfficiency:
    """Verify memory tool responses stay within token-efficient limits.

    These tests ensure memory tools don't waste tokens by echoing back
    full content or including unnecessary fields in responses.
    """

    @pytest.mark.asyncio
    async def test_store_memory_response_size(self, mock_services):
        """store_memory should return confirmation, not echo full content.

        Size limit: < 500 bytes

        Rationale: Store operations need only return confirmation + memory ID.
        A UUID (36 chars) + status + category + timestamps fits in ~150-200 bytes.
        500 bytes provides headroom while catching content echo-back bugs
        where storing 1000+ chars would return 1000+ bytes.
        """
        tools = get_memory_tools(mock_services)
        store_memory = tools["store_memory"]

        # Use large content to detect echo-back bugs
        large_content = "A" * 1000  # 1KB content

        response = await store_memory(
            content=large_content,
            category="fact",
            importance=0.8,
            tags=["test"],
        )

        response_size = len(json.dumps(response))
        max_size = 500

        assert response_size < max_size, (
            f"store_memory response too large: {response_size} bytes >= {max_size} bytes. "
            f"Response should not echo back the full content. "
            f"Stored 1000 char content but response should be ~150-200 bytes."
        )

    @pytest.mark.asyncio
    async def test_store_memory_no_content_echo(self, mock_services):
        """store_memory response should not include the stored content.

        The content field is only needed on retrieval, not on store confirmation.
        Including it wastes tokens proportional to content size.
        """
        tools = get_memory_tools(mock_services)
        store_memory = tools["store_memory"]

        test_content = "This is test content that should not be echoed"

        response = await store_memory(
            content=test_content,
            category="fact",
        )

        # Response should not contain the content
        response_str = json.dumps(response)
        assert test_content not in response_str, (
            f"store_memory echoed back content in response. "
            f"Response should be confirmation only, not include: '{test_content}'"
        )

    @pytest.mark.asyncio
    async def test_retrieve_memories_response_size_per_entry(
        self, mock_services, mock_search_result
    ):
        """retrieve_memories entries should stay under size limit.

        Size limit: < 1000 bytes per entry

        Rationale: Retrieved memories include content (for search context) but
        should have bounded content. 1000 bytes allows ~500 char useful content
        plus metadata while preventing unbounded bloat.
        """
        tools = get_memory_tools(mock_services)
        retrieve_memories = tools["retrieve_memories"]

        # Create mock result with moderate content
        mock_result = mock_search_result(
            id="12345678-1234-1234-1234-123456789abc",
            payload={
                "id": "12345678-1234-1234-1234-123456789abc",
                "content": "Test content " * 20,  # ~260 chars
                "category": "fact",
                "importance": 0.8,
                "tags": ["test"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        )
        mock_services.vector_store.search.return_value = [mock_result]

        response = await retrieve_memories(query="test", limit=5)

        # Check each result individually
        for i, result in enumerate(response["results"]):
            result_size = len(json.dumps(result))
            max_size = 1000

            assert result_size < max_size, (
                f"retrieve_memories result[{i}] too large: {result_size} bytes >= {max_size} bytes. "
                f"Each result should stay under {max_size} bytes."
            )

    @pytest.mark.asyncio
    async def test_list_memories_response_size_per_entry(
        self, mock_services, mock_search_result
    ):
        """list_memories entries should return metadata only, under size limit.

        Size limit: < 500 bytes per entry

        Rationale: List operations return metadata only (id, category, importance,
        created_at). No content needed for browsing/filtering. Each entry should
        be ~100-200 bytes of pure metadata.
        """
        tools = get_memory_tools(mock_services)
        list_memories = tools["list_memories"]

        # Create mock result - content should NOT be in response
        mock_result = mock_search_result(
            id="12345678-1234-1234-1234-123456789abc",
            payload={
                "id": "12345678-1234-1234-1234-123456789abc",
                "content": "This content should not appear in list response " * 10,
                "category": "fact",
                "importance": 0.8,
                "tags": ["test"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        )
        mock_services.vector_store.scroll.return_value = [mock_result]
        mock_services.vector_store.count.return_value = 1

        response = await list_memories(limit=10)

        for i, result in enumerate(response["results"]):
            result_size = len(json.dumps(result))
            max_size = 500

            assert result_size < max_size, (
                f"list_memories result[{i}] too large: {result_size} bytes >= {max_size} bytes. "
                f"List should return metadata only (no content). Each entry ~100-200 bytes."
            )

    @pytest.mark.asyncio
    async def test_delete_memory_response_size(self, mock_services):
        """delete_memory should return minimal confirmation.

        Size limit: < 300 bytes

        Rationale: Simplest operation - just needs {"deleted": true/false}.
        Actual response is typically ~20 bytes.
        """
        tools = get_memory_tools(mock_services)
        delete_memory = tools["delete_memory"]

        response = await delete_memory(memory_id="12345678-1234-1234-1234-123456789abc")

        response_size = len(json.dumps(response))
        max_size = 300

        assert response_size < max_size, (
            f"delete_memory response too large: {response_size} bytes >= {max_size} bytes. "
            f"Should be simple confirmation like {{'deleted': true}}."
        )

    @pytest.mark.asyncio
    async def test_memory_responses_non_empty(self, mock_services):
        """All memory tool responses should be non-empty (minimum 10 bytes).

        This catches broken endpoints that return empty responses.
        """
        tools = get_memory_tools(mock_services)
        min_size = 10

        # Test store_memory
        store_response = await tools["store_memory"](
            content="Test", category="fact"
        )
        store_size = len(json.dumps(store_response))
        assert store_size >= min_size, (
            f"store_memory response too small: {store_size} bytes < {min_size} bytes"
        )

        # Test retrieve_memories (empty result is valid, but response structure exists)
        retrieve_response = await tools["retrieve_memories"](query="test", limit=5)
        retrieve_size = len(json.dumps(retrieve_response))
        assert retrieve_size >= min_size, (
            f"retrieve_memories response too small: {retrieve_size} bytes < {min_size} bytes"
        )

        # Test list_memories
        list_response = await tools["list_memories"](limit=10)
        list_size = len(json.dumps(list_response))
        assert list_size >= min_size, (
            f"list_memories response too small: {list_size} bytes < {min_size} bytes"
        )

        # Test delete_memory
        delete_response = await tools["delete_memory"](memory_id="12345678-1234-1234-1234-123456789abc")
        delete_size = len(json.dumps(delete_response))
        assert delete_size >= min_size, (
            f"delete_memory response too small: {delete_size} bytes < {min_size} bytes"
        )
