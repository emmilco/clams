"""Tests for GHAP response size efficiency.

This module verifies that GHAP tool responses stay within token-efficient byte limits.
Size limits are based on BUG-030 analysis, which showed GHAP tools returning full records
on every operation, wasting approximately 50,000 tokens during bulk generation.

Size Limits Rationale:
- 500 bytes for confirmations (start/update/resolve): UUID (36 chars) + status +
  JSON overhead fits in ~100-200 bytes. 500 bytes provides headroom while catching
  bloat like full entries (~2KB+).
- 2000 bytes for get_active (with entry): Returns full entry with all fields.
  Typical entries are 800-1500 bytes.
- 500 bytes for get_active (no entry): Should return minimal empty state.
- 500 bytes per entry for list: Summaries only (ID, domain, status).
  Each summary should be ~100-200 bytes.

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
