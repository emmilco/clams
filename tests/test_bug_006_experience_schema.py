"""Regression test for BUG-006: search_experiences fails with KeyError.

This test verifies that ObservationPersister stores complete GHAP payloads
that can be successfully retrieved via search_experiences.

The bug was caused by _build_axis_metadata() only storing metadata fields,
not the content fields (goal, hypothesis, action, prediction, outcome_result, axis)
that ExperienceResult.from_search_result() expects.
"""

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# Mark all tests in this module as integration tests (require Qdrant)
pytestmark = pytest.mark.integration

from clams.embedding.mock import MockEmbedding
from clams.observation import (
    Domain,
    ObservationCollector,
    OutcomeStatus,
    Strategy,
)
from clams.observation import (
    Lesson as GHAPLesson,
)
from clams.observation import (
    RootCause as GHAPRootCause,
)
from clams.observation.persister import ObservationPersister
from clams.search.searcher import Searcher
from clams.storage import QdrantVectorStore

# Test collection names (using production names for integration test)
# The searcher has hardcoded collection names, so we use the production ones
TEST_COLLECTIONS = {
    "full": "ghap_full",
    "strategy": "ghap_strategy",
    "surprise": "ghap_surprise",
    "root_cause": "ghap_root_cause",
}


@pytest.fixture
async def vector_store() -> AsyncIterator[QdrantVectorStore]:
    """Create a Qdrant vector store for tests."""
    store = QdrantVectorStore(url="http://localhost:6333")
    yield store


@pytest.fixture
async def embedding_service() -> MockEmbedding:
    """Create a mock embedding service for deterministic tests."""
    return MockEmbedding()


@pytest.fixture
async def test_collections(
    vector_store: QdrantVectorStore,
) -> AsyncIterator[dict[str, str]]:
    """Create isolated test collections and clean up after tests."""
    # Create all test collections
    for collection in TEST_COLLECTIONS.values():
        try:
            await vector_store.delete_collection(collection)
        except Exception:
            pass  # Collection may not exist

        await vector_store.create_collection(
            name=collection,
            dimension=768,
            distance="cosine",
        )

    yield TEST_COLLECTIONS

    # Cleanup
    for collection in TEST_COLLECTIONS.values():
        try:
            await vector_store.delete_collection(collection)
        except Exception:
            pass


@pytest.fixture
async def persister(
    embedding_service: MockEmbedding,
    vector_store: QdrantVectorStore,
    test_collections: dict[str, str],
) -> ObservationPersister:
    """Create an ObservationPersister with test collections."""
    # Use "ghap" prefix to match production collection names
    # The searcher has hardcoded collection names
    return ObservationPersister(
        embedding_service=embedding_service,
        vector_store=vector_store,
        collection_prefix="ghap",
    )


@pytest.fixture
async def searcher(
    embedding_service: MockEmbedding,
    vector_store: QdrantVectorStore,
    test_collections: dict[str, str],
) -> Searcher:
    """Create a Searcher with test collections."""
    return Searcher(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


class TestBug006ExperienceSchema:
    """Regression tests for BUG-006: incomplete GHAP payload schema."""

    async def test_search_experiences_with_confirmed_outcome(
        self,
        persister: ObservationPersister,
        searcher: Searcher,
    ) -> None:
        """Test that search_experiences works with confirmed GHAP entries.

        Verifies that:
        1. GHAP entry is persisted with complete payload
        2. search_experiences can retrieve it
        3. ExperienceResult is successfully created with all fields
        4. All fields match the original entry
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create ObservationCollector and GHAP entry
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)
            await collector.start_session()

            _ghap = await collector.create_ghap(
                domain=Domain.TESTING,
                strategy=Strategy.SYSTEMATIC_ELIMINATION,
                goal="Verify schema completeness",
                hypothesis="Payload will contain all required fields",
                action="Create GHAP and search for it",
                prediction="Search will return complete ExperienceResult",
            )

            # 2. Resolve it with confirmed outcome
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="All fields present in payload",
                lesson=GHAPLesson(
                    what_worked="Storing content fields in payload",
                    takeaway="Templates are for embeddings, payload is for retrieval",
                ),
            )

            # 3. Persist to Qdrant
            await persister.persist(resolved)

            # 4. Search for the entry
            results = await searcher.search_experiences(
                query="schema completeness",
                axis="full",
                limit=5,
            )

            # 5. Verify results
            assert len(results) > 0, "Search should return at least one result"

            # Find our entry (may not be first if other entries exist)
            result = next((r for r in results if r.ghap_id == resolved.id), None)
            assert result is not None, f"Should find GHAP {resolved.id} in results"

            # 6. Verify all fields match
            assert result.ghap_id == resolved.id
            assert result.axis == "full"
            assert result.domain == resolved.domain.value
            assert result.strategy == resolved.strategy.value
            assert result.goal == resolved.goal
            assert result.hypothesis == resolved.hypothesis
            assert result.action == resolved.action
            assert result.prediction == resolved.prediction
            assert result.outcome_status == OutcomeStatus.CONFIRMED.value
            assert result.outcome_result == "All fields present in payload"
            assert result.iteration_count == resolved.iteration_count

            # Lesson should be present
            assert result.lesson is not None
            assert result.lesson.what_worked == "Storing content fields in payload"
            assert (
                result.lesson.takeaway
                == "Templates are for embeddings, payload is for retrieval"
            )

            # Optional fields for confirmed outcome
            assert result.surprise is None
            assert result.root_cause is None


    async def test_search_experiences_with_falsified_outcome(
        self,
        persister: ObservationPersister,
        searcher: Searcher,
    ) -> None:
        """Test that search_experiences works with falsified GHAP entries.

        Verifies that surprise and root_cause fields are correctly stored
        and retrieved for falsified outcomes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create ObservationCollector and GHAP entry
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)
            await collector.start_session()

            _ghap = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.ROOT_CAUSE_ANALYSIS,
                goal="Fix schema bug",
                hypothesis="Missing fields in persister",
                action="Inspect persister code",
                prediction="Will find missing field assignments",
            )

            # 2. Resolve it with falsified outcome (includes surprise and root_cause)
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.FALSIFIED,
                result="Fields were never added to payload",
                surprise="Templates were used for embeddings but not payload",
                root_cause=GHAPRootCause(
                    category="incomplete_information",
                    description="Persister only stored metadata, not content",
                ),
                lesson=GHAPLesson(
                    what_worked="Reading both persister and result converter",
                    takeaway="Verify both write and read paths in schema bugs",
                ),
            )

            # 3. Persist to Qdrant
            await persister.persist(resolved)

            # 4. Search for the entry in the surprise axis
            results = await searcher.search_experiences(
                query="schema bug debugging",
                axis="surprise",
                limit=5,
            )

            # 5. Verify results
            assert len(results) > 0, "Search should return at least one result"

            # Find our entry
            result = next((r for r in results if r.ghap_id == resolved.id), None)
            assert result is not None, f"Should find GHAP {resolved.id} in results"

            # 6. Verify all fields match
            assert result.ghap_id == resolved.id
            assert result.axis == "surprise"
            assert result.domain == resolved.domain.value
            assert result.strategy == resolved.strategy.value
            assert result.goal == resolved.goal
            assert result.hypothesis == resolved.hypothesis
            assert result.action == resolved.action
            assert result.prediction == resolved.prediction
            assert result.outcome_status == OutcomeStatus.FALSIFIED.value
            assert result.outcome_result == "Fields were never added to payload"

            # Surprise and root_cause should be present for falsified outcomes
            assert (
                result.surprise
                == "Templates were used for embeddings but not payload"
            )
            assert result.root_cause is not None
            assert result.root_cause.category == "incomplete_information"
            assert (
                result.root_cause.description
                == "Persister only stored metadata, not content"
            )

            # Lesson should be present
            assert result.lesson is not None
            assert (
                result.lesson.what_worked
                == "Reading both persister and result converter"
            )
            assert (
                result.lesson.takeaway
                == "Verify both write and read paths in schema bugs"
            )


    async def test_search_experiences_all_axes(
        self,
        persister: ObservationPersister,
        searcher: Searcher,
    ) -> None:
        """Test that search_experiences works on all four axes.

        Verifies that each axis (full, strategy, surprise, root_cause) stores
        complete payloads with the correct axis identifier.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create ObservationCollector and GHAP entry
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)
            await collector.start_session()

            _ghap = await collector.create_ghap(
                domain=Domain.FEATURE,
                strategy=Strategy.DIVIDE_AND_CONQUER,
                goal="Test all axes",
                hypothesis="All axes will have complete schema",
                action="Create falsified GHAP and search all axes",
                prediction="All axes will return valid results",
            )

            # 2. Resolve with falsified outcome (creates all 4 axes)
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.FALSIFIED,
                result="Found incomplete axis",
                surprise="One axis was missing fields",
                root_cause=GHAPRootCause(
                    category="wrong_assumption",
                    description="Assumed all axes used same schema",
                ),
            )

            # 3. Persist to Qdrant
            await persister.persist(resolved)

            # 4. Test each axis
            for axis in ["full", "strategy", "surprise", "root_cause"]:
                results = await searcher.search_experiences(
                    query="test all axes",
                    axis=axis,
                    limit=5,
                )

                # Should find at least one result
                assert len(results) > 0, f"Search should return results for {axis}"

                # Find our entry
                result = next((r for r in results if r.ghap_id == resolved.id), None)
                assert result is not None, f"Should find GHAP {resolved.id} in {axis}"

                # Verify axis identifier is correct
                assert result.axis == axis, f"Result should have axis={axis}"

                # Verify required content fields are present
                assert result.goal == resolved.goal
                assert result.hypothesis == resolved.hypothesis
                assert result.action == resolved.action
                assert result.prediction == resolved.prediction
                assert result.outcome_result == "Found incomplete axis"
