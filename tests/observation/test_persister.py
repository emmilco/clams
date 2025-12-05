"""Tests for ObservationPersister multi-axis embedding."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import numpy as np
import pytest

from learning_memory_server.observation.models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    Lesson,
    Outcome,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from learning_memory_server.observation.persister import (
    TEMPLATE_FULL,
    TEMPLATE_ROOT_CAUSE,
    TEMPLATE_STRATEGY,
    TEMPLATE_SURPRISE,
    ObservationPersister,
)


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Mock embedding service."""
    service = AsyncMock()
    service.dimension = 768
    # Return a 768-dimensional vector
    service.embed.return_value = np.zeros(768, dtype=np.float32)
    return service


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock vector store."""
    store = AsyncMock()
    return store


@pytest.fixture
def persister(
    mock_embedding_service: AsyncMock, mock_vector_store: AsyncMock
) -> ObservationPersister:
    """Create persister with mocks."""
    return ObservationPersister(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        collection_prefix="ghap",
    )


@pytest.fixture
def confirmed_entry() -> GHAPEntry:
    """Create a confirmed GHAP entry with all fields."""
    return GHAPEntry(
        id="ghap_20251204_120000_abc123",
        session_id="session_20251204_120000_xyz789",
        created_at=datetime(2025, 12, 4, 12, 0, 0, tzinfo=UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix failing test",
        hypothesis="The test is failing due to incorrect mock setup",
        action="Update mock configuration",
        prediction="Test will pass after mock update",
        iteration_count=2,
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test passed after mock update",
            captured_at=datetime(2025, 12, 4, 12, 5, 0, tzinfo=UTC),
            auto_captured=True,
        ),
        lesson=Lesson(
            what_worked="Systematic mock verification",
            takeaway="Always verify mock return values",
        ),
        confidence_tier=ConfidenceTier.GOLD,
    )


@pytest.fixture
def falsified_entry() -> GHAPEntry:
    """Create a falsified GHAP entry with surprise and root cause."""
    return GHAPEntry(
        id="ghap_20251204_130000_def456",
        session_id="session_20251204_130000_xyz789",
        created_at=datetime(2025, 12, 4, 13, 0, 0, tzinfo=UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.ROOT_CAUSE_ANALYSIS,
        goal="Fix database connection error",
        hypothesis="Database is rejecting connections due to max connections reached",
        action="Check database connection pool settings",
        prediction="Will see max_connections exceeded in logs",
        iteration_count=1,
        outcome=Outcome(
            status=OutcomeStatus.FALSIFIED,
            result="Connection pool has plenty of capacity, error is authentication",
            captured_at=datetime(2025, 12, 4, 13, 10, 0, tzinfo=UTC),
            auto_captured=False,
        ),
        surprise="Expected connection pool exhaustion but found auth failure",
        root_cause=RootCause(
            category="wrong-assumption",
            description=(
                "Assumed connection error was capacity-related, "
                "but was actually credentials issue"
            ),
        ),
        lesson=Lesson(
            what_worked="Checking actual error logs instead of assuming",
        ),
        confidence_tier=ConfidenceTier.SILVER,
    )


# Template Rendering Tests


def test_render_full_axis_with_all_fields(
    persister: ObservationPersister, confirmed_entry: GHAPEntry
) -> None:
    """Verify full template renders correctly with all optional fields."""
    result = persister._render_template(TEMPLATE_FULL, confirmed_entry)

    assert "Goal: Fix failing test" in result
    assert "Hypothesis: The test is failing due to incorrect mock setup" in result
    assert "Action: Update mock configuration" in result
    assert "Prediction: Test will pass after mock update" in result
    assert "Outcome: confirmed - Test passed after mock update" in result
    assert "Lesson: Systematic mock verification" in result
    # Surprise should not be present (confirmed entry)
    assert "Surprise:" not in result


def test_render_full_axis_without_optional_fields(
    persister: ObservationPersister,
) -> None:
    """Verify optional fields are omitted when None."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
        # No lesson, no surprise
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    assert "Surprise:" not in result
    assert "Lesson:" not in result
    assert "Goal: Test goal" in result


def test_render_strategy_axis(
    persister: ObservationPersister, confirmed_entry: GHAPEntry
) -> None:
    """Verify strategy template renders correctly."""
    result = persister._render_template(TEMPLATE_STRATEGY, confirmed_entry)

    assert "Strategy: systematic-elimination" in result
    assert "Applied to: Fix failing test" in result
    assert "Outcome: confirmed after 2 iteration(s)" in result
    assert "What worked: Systematic mock verification" in result


def test_render_surprise_axis(
    persister: ObservationPersister, falsified_entry: GHAPEntry
) -> None:
    """Verify surprise template for falsified entries."""
    result = persister._render_template(TEMPLATE_SURPRISE, falsified_entry)

    assert "Expected: Will see max_connections exceeded in logs" in result
    assert (
        "Actual: Connection pool has plenty of capacity, error is authentication"
        in result
    )
    assert (
        "Surprise: Expected connection pool exhaustion but found auth failure" in result
    )
    assert "Root cause: wrong-assumption -" in result


def test_render_root_cause_axis(
    persister: ObservationPersister, falsified_entry: GHAPEntry
) -> None:
    """Verify root_cause template for falsified entries."""
    result = persister._render_template(TEMPLATE_ROOT_CAUSE, falsified_entry)

    assert "Category: wrong-assumption" in result
    assert "Description: Assumed connection error was capacity-related" in result
    assert "Context: debugging - root-cause-analysis" in result
    assert (
        "Original hypothesis: Database is rejecting connections "
        "due to max connections reached"
    ) in result


# Metadata Tests


def test_build_metadata_structure(
    persister: ObservationPersister, confirmed_entry: GHAPEntry
) -> None:
    """Verify metadata contains all required fields."""
    metadata = persister._build_metadata(confirmed_entry)

    assert metadata["ghap_id"] == "ghap_20251204_120000_abc123"
    assert metadata["session_id"] == "session_20251204_120000_xyz789"
    assert isinstance(metadata["created_at"], float)
    assert isinstance(metadata["captured_at"], float)
    assert metadata["domain"] == "debugging"
    assert metadata["strategy"] == "systematic-elimination"
    assert metadata["outcome_status"] == "confirmed"
    assert metadata["confidence_tier"] == "gold"
    assert metadata["iteration_count"] == 2


def test_metadata_timestamp_conversion(
    persister: ObservationPersister, confirmed_entry: GHAPEntry
) -> None:
    """Verify datetime → Unix epoch conversion."""
    metadata = persister._build_metadata(confirmed_entry)

    # Verify created_at timestamp
    created_timestamp = datetime(2025, 12, 4, 12, 0, 0, tzinfo=UTC).timestamp()
    assert metadata["created_at"] == created_timestamp

    # Verify captured_at timestamp
    captured_timestamp = datetime(2025, 12, 4, 12, 5, 0, tzinfo=UTC).timestamp()
    assert metadata["captured_at"] == captured_timestamp


def test_axis_specific_metadata(
    persister: ObservationPersister, falsified_entry: GHAPEntry
) -> None:
    """Verify root_cause_category added for surprise/root_cause axes."""
    base_metadata = persister._build_metadata(falsified_entry)

    # Full axis should not have root_cause_category
    full_metadata = persister._build_axis_metadata(
        falsified_entry, "full", base_metadata
    )
    assert "root_cause_category" not in full_metadata

    # Surprise axis should have root_cause_category
    surprise_metadata = persister._build_axis_metadata(
        falsified_entry, "surprise", base_metadata
    )
    assert surprise_metadata["root_cause_category"] == "wrong-assumption"

    # Root cause axis should have root_cause_category
    root_cause_metadata = persister._build_axis_metadata(
        falsified_entry, "root_cause", base_metadata
    )
    assert root_cause_metadata["root_cause_category"] == "wrong-assumption"


# Axis Determination Tests


def test_confirmed_entry_gets_full_and_strategy_only(
    persister: ObservationPersister, confirmed_entry: GHAPEntry
) -> None:
    """Confirmed entries should only get full and strategy axes."""
    axes = persister._determine_axes(confirmed_entry)

    assert "full" in axes
    assert "strategy" in axes
    assert "surprise" not in axes
    assert "root_cause" not in axes


def test_falsified_entry_with_surprise_gets_all_axes(
    persister: ObservationPersister, falsified_entry: GHAPEntry
) -> None:
    """Falsified with surprise/root_cause gets all 4 axes."""
    axes = persister._determine_axes(falsified_entry)

    assert "full" in axes
    assert "strategy" in axes
    assert "surprise" in axes
    assert "root_cause" in axes


def test_falsified_without_surprise_skips_surprise_axis(
    persister: ObservationPersister,
) -> None:
    """Falsified without surprise field skips surprise axis."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.FALSIFIED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
        # No surprise field
    )

    axes = persister._determine_axes(entry)

    assert "full" in axes
    assert "strategy" in axes
    assert "surprise" not in axes
    assert "root_cause" not in axes


# Edge Case Tests


def test_render_with_empty_string_vs_none(persister: ObservationPersister) -> None:
    """Verify empty string '' vs None are handled correctly for optional fields."""
    # Entry with empty string for surprise (should be treated as missing)
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
        surprise="",  # Empty string
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    # Empty string should cause optional section to be removed
    assert "Surprise:" not in result


def test_entry_with_no_confidence_tier(persister: ObservationPersister) -> None:
    """Verify metadata construction when confidence_tier is None."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
        confidence_tier=None,
    )

    metadata = persister._build_metadata(entry)
    assert metadata["confidence_tier"] is None


def test_unicode_emoji_in_fields(persister: ObservationPersister) -> None:
    """Verify template rendering handles unicode/emoji correctly."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Fix the 🐛 bug",
        hypothesis="The bug 🪲 is in the code 💻",
        action="Debug with 🔍",
        prediction="Will find the issue ✅",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Found it! 🎉",
            captured_at=datetime.now(UTC),
        ),
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    assert "🐛" in result
    assert "🪲" in result
    assert "💻" in result
    assert "🔍" in result
    assert "✅" in result
    assert "🎉" in result


def test_very_long_field_values(persister: ObservationPersister) -> None:
    """Verify handling of very long field values (e.g., 10KB text)."""
    long_text = "x" * 10000
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal=long_text,
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    # Should not raise an error
    assert long_text in result


def test_special_regex_chars_in_field_values(persister: ObservationPersister) -> None:
    """Verify template handles regex special chars in field values."""
    special_chars = r"[ ] { } ( ) . * + ? ^ $ \ |"
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal=f"Test with special chars: {special_chars}",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    # Special chars should be preserved
    assert special_chars in result


def test_all_confidence_tier_values(persister: ObservationPersister) -> None:
    """Verify metadata construction for all ConfidenceTier enum values."""
    for tier in [
        ConfidenceTier.GOLD,
        ConfidenceTier.SILVER,
        ConfidenceTier.BRONZE,
        ConfidenceTier.ABANDONED,
    ]:
        entry = GHAPEntry(
            id="ghap_test",
            session_id="session_test",
            created_at=datetime.now(UTC),
            domain=Domain.DEBUGGING,
            strategy=Strategy.TRIAL_AND_ERROR,
            goal="Test goal",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
            outcome=Outcome(
                status=OutcomeStatus.CONFIRMED,
                result="Test result",
                captured_at=datetime.now(UTC),
            ),
            confidence_tier=tier,
        )

        metadata = persister._build_metadata(entry)
        assert metadata["confidence_tier"] == tier.value


def test_literal_template_syntax_in_fields(persister: ObservationPersister) -> None:
    """Verify fields with literal text like '{field}' render correctly."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Use {variable} in the code",
        hypothesis="The [array] needs fixing",
        action="Update {config}",
        prediction="Will see [success]",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="Got [result]",
            captured_at=datetime.now(UTC),
        ),
    )

    result = persister._render_template(TEMPLATE_FULL, entry)

    # These should be preserved as literal text
    assert "Use {variable} in the code" in result
    assert "The [array] needs fixing" in result
    assert "Update {config}" in result
    assert "Will see [success]" in result
    assert "Got [result]" in result


def test_root_cause_without_surprise(persister: ObservationPersister) -> None:
    """Verify root_cause axis is skipped when root_cause exists but surprise is None."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=Outcome(
            status=OutcomeStatus.FALSIFIED,
            result="Test result",
            captured_at=datetime.now(UTC),
        ),
        surprise=None,  # No surprise
        root_cause=RootCause(
            category="test-category",
            description="test description",
        ),
    )

    axes = persister._determine_axes(entry)

    assert "full" in axes
    assert "strategy" in axes
    assert "surprise" not in axes
    assert "root_cause" not in axes


# Integration Tests


@pytest.mark.asyncio
async def test_persist_confirmed_entry(
    persister: ObservationPersister,
    confirmed_entry: GHAPEntry,
    mock_embedding_service: AsyncMock,
    mock_vector_store: AsyncMock,
) -> None:
    """Test persisting a confirmed entry with mocks."""
    await persister.persist(confirmed_entry)

    # Verify embed() called 2x (full, strategy)
    assert mock_embedding_service.embed.call_count == 2

    # Verify upsert() called 2x with correct collections
    assert mock_vector_store.upsert.call_count == 2
    calls = mock_vector_store.upsert.call_args_list
    collections = [call.kwargs["collection"] for call in calls]
    assert "ghap_full" in collections
    assert "ghap_strategy" in collections


@pytest.mark.asyncio
async def test_persist_falsified_entry_with_surprise(
    persister: ObservationPersister,
    falsified_entry: GHAPEntry,
    mock_embedding_service: AsyncMock,
    mock_vector_store: AsyncMock,
) -> None:
    """Test persisting a falsified entry with surprise."""
    await persister.persist(falsified_entry)

    # Verify embed() called 4x
    assert mock_embedding_service.embed.call_count == 4

    # Verify upsert() called 4x
    assert mock_vector_store.upsert.call_count == 4
    calls = mock_vector_store.upsert.call_args_list
    collections = [call.kwargs["collection"] for call in calls]
    assert "ghap_full" in collections
    assert "ghap_strategy" in collections
    assert "ghap_surprise" in collections
    assert "ghap_root_cause" in collections

    # Verify root_cause_category in surprise/root_cause metadata
    for call in calls:
        if call.kwargs["collection"] in ["ghap_surprise", "ghap_root_cause"]:
            assert call.kwargs["payload"]["root_cause_category"] == "wrong-assumption"


@pytest.mark.asyncio
async def test_persist_batch(
    persister: ObservationPersister,
    confirmed_entry: GHAPEntry,
    falsified_entry: GHAPEntry,
    mock_embedding_service: AsyncMock,
    mock_vector_store: AsyncMock,
) -> None:
    """Test batch persistence."""
    entries = [confirmed_entry, falsified_entry]
    await persister.persist_batch(entries)

    # Verify all entries persisted (2 axes + 4 axes = 6 total)
    assert mock_embedding_service.embed.call_count == 6
    assert mock_vector_store.upsert.call_count == 6


@pytest.mark.asyncio
async def test_persist_without_outcome_raises(
    persister: ObservationPersister,
) -> None:
    """Test that unresolved entry raises ValueError."""
    entry = GHAPEntry(
        id="ghap_test",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=None,  # No outcome
    )

    with pytest.raises(ValueError, match="Entry must be resolved"):
        await persister.persist(entry)


# Collection Management Tests


@pytest.mark.asyncio
async def test_ensure_collections_creates_all(
    persister: ObservationPersister,
    mock_vector_store: AsyncMock,
) -> None:
    """Test that ensure_collections creates all 4 collections."""
    await persister.ensure_collections()

    # Verify create_collection called 4x
    assert mock_vector_store.create_collection.call_count == 4
    calls = mock_vector_store.create_collection.call_args_list
    collections = [call.kwargs["name"] for call in calls]
    assert "ghap_full" in collections
    assert "ghap_strategy" in collections
    assert "ghap_surprise" in collections
    assert "ghap_root_cause" in collections


@pytest.mark.asyncio
async def test_ensure_collections_idempotent(
    persister: ObservationPersister,
    mock_vector_store: AsyncMock,
) -> None:
    """Test that calling ensure_collections twice is safe."""
    # First call succeeds
    await persister.ensure_collections()

    # Second call raises ValueError for existing collections
    mock_vector_store.create_collection.side_effect = ValueError(
        "Collection already exists"
    )

    # Should not raise - ValueError is caught and logged
    await persister.ensure_collections()


# Error Handling Tests


@pytest.mark.asyncio
async def test_embedding_failure_propagates(
    persister: ObservationPersister,
    confirmed_entry: GHAPEntry,
    mock_embedding_service: AsyncMock,
) -> None:
    """Test that EmbeddingModelError is propagated."""
    from learning_memory_server.embedding.base import EmbeddingModelError

    mock_embedding_service.embed.side_effect = EmbeddingModelError("Model failed")

    with pytest.raises(EmbeddingModelError, match="Model failed"):
        await persister.persist(confirmed_entry)


@pytest.mark.asyncio
async def test_storage_failure_propagates(
    persister: ObservationPersister,
    confirmed_entry: GHAPEntry,
    mock_vector_store: AsyncMock,
) -> None:
    """Test that storage errors are propagated."""
    mock_vector_store.upsert.side_effect = Exception("Storage failed")

    with pytest.raises(Exception, match="Storage failed"):
        await persister.persist(confirmed_entry)


@pytest.mark.asyncio
async def test_batch_fails_on_first_invalid_entry(
    persister: ObservationPersister,
    confirmed_entry: GHAPEntry,
) -> None:
    """Test that persist_batch validates all entries upfront."""
    # Create an entry without outcome
    invalid_entry = GHAPEntry(
        id="ghap_invalid",
        session_id="session_test",
        created_at=datetime.now(UTC),
        domain=Domain.DEBUGGING,
        strategy=Strategy.TRIAL_AND_ERROR,
        goal="Test goal",
        hypothesis="Test hypothesis",
        action="Test action",
        prediction="Test prediction",
        outcome=None,  # Invalid
    )

    entries = [confirmed_entry, invalid_entry]

    with pytest.raises(ValueError, match="must be resolved"):
        await persister.persist_batch(entries)
