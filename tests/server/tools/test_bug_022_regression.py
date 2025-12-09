"""Regression test for BUG-022: _delete_file_units should delete all entries, not just first 1000."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.indexers.indexer import CodeIndexer


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create a mock vector store."""
    return AsyncMock()


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Create a mock embedding service."""
    service = MagicMock()
    service.dimension = 768
    return service


@pytest.fixture
def mock_parser() -> MagicMock:
    """Create a mock code parser."""
    return MagicMock()


@pytest.fixture
def mock_metadata_store() -> AsyncMock:
    """Create a mock metadata store."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_delete_file_units_handles_more_than_1000_entries(
    mock_vector_store: AsyncMock,
    mock_embedding_service: MagicMock,
    mock_parser: MagicMock,
    mock_metadata_store: AsyncMock,
) -> None:
    """Verify _delete_file_units loops until all entries are deleted.

    BUG-022: Previously, only the first 1000 entries were deleted because
    scroll was called once with limit=1000. If a file had >1000 units,
    the remaining entries became orphaned.
    """
    # Setup: Create mock results simulating >1000 entries
    # First call returns 1000 entries, second returns 500, third returns empty
    batch1 = [MagicMock(id=f"id-{i}") for i in range(1000)]
    batch2 = [MagicMock(id=f"id-{i}") for i in range(1000, 1500)]
    batch3: list[MagicMock] = []

    mock_vector_store.scroll.side_effect = [batch1, batch2, batch3]
    mock_vector_store.delete = AsyncMock()

    # Create indexer with mocks
    indexer = CodeIndexer(
        parser=mock_parser,
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        metadata_store=mock_metadata_store,
    )

    # Action: Delete file units
    await indexer._delete_file_units(path="/test/file.py", project="test-project")

    # Assert: scroll was called 3 times (until empty)
    assert mock_vector_store.scroll.call_count == 3

    # Assert: delete was called 1500 times (once per entry)
    assert mock_vector_store.delete.call_count == 1500

    # Verify all IDs were deleted
    deleted_ids = {call.kwargs["id"] for call in mock_vector_store.delete.call_args_list}
    expected_ids = {f"id-{i}" for i in range(1500)}
    assert deleted_ids == expected_ids


@pytest.mark.asyncio
async def test_delete_file_units_handles_empty_collection(
    mock_vector_store: AsyncMock,
    mock_embedding_service: MagicMock,
    mock_parser: MagicMock,
    mock_metadata_store: AsyncMock,
) -> None:
    """Verify _delete_file_units handles empty result gracefully."""
    # Setup: scroll returns empty immediately
    mock_vector_store.scroll.return_value = []
    mock_vector_store.delete = AsyncMock()

    indexer = CodeIndexer(
        parser=mock_parser,
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        metadata_store=mock_metadata_store,
    )

    # Action: Delete file units (should not raise)
    await indexer._delete_file_units(path="/test/file.py", project="test-project")

    # Assert: scroll called once, delete never called
    assert mock_vector_store.scroll.call_count == 1
    assert mock_vector_store.delete.call_count == 0


@pytest.mark.asyncio
async def test_delete_file_units_handles_exactly_1000_entries(
    mock_vector_store: AsyncMock,
    mock_embedding_service: MagicMock,
    mock_parser: MagicMock,
    mock_metadata_store: AsyncMock,
) -> None:
    """Verify _delete_file_units correctly handles exactly 1000 entries.

    This edge case ensures we loop correctly when first batch is exactly
    at the limit.
    """
    # Setup: First call returns exactly 1000, second returns empty
    batch1 = [MagicMock(id=f"id-{i}") for i in range(1000)]
    batch2: list[MagicMock] = []

    mock_vector_store.scroll.side_effect = [batch1, batch2]
    mock_vector_store.delete = AsyncMock()

    indexer = CodeIndexer(
        parser=mock_parser,
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        metadata_store=mock_metadata_store,
    )

    # Action
    await indexer._delete_file_units(path="/test/file.py", project="test-project")

    # Assert: scroll called twice (first with results, second empty)
    assert mock_vector_store.scroll.call_count == 2
    assert mock_vector_store.delete.call_count == 1000
