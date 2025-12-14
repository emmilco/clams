"""Round-trip serialization tests for data integrity.

These tests verify that data survives storage and retrieval intact, specifically:
- GHAP entries (via ObservationCollector and ObservationPersister)
- Memories (via memory tools)
- Values (via ValueStore)
- Datetime fields (critical for BUG-027 regression)
- Numeric fields (especially floats)

Reference: R10-A - Add Round-Trip Serialization Tests
Related: BUG-027 (datetime round-trip issues)
"""

import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from clams.embedding.mock import MockEmbedding
from clams.observation import (
    Domain,
    Lesson,
    ObservationCollector,
    ObservationPersister,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from clams.observation.models import ConfidenceTier, GHAPEntry
from clams.storage import QdrantVectorStore

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

pytest_plugins = ("pytest_asyncio",)


# Test collection names (isolated from production)
TEST_COLLECTIONS = {
    "memories": "test_rt_memories",
    "values": "test_rt_values",
    "full": "test_rt_ghap_full",
    "strategy": "test_rt_ghap_strategy",
    "surprise": "test_rt_ghap_surprise",
    "root_cause": "test_rt_ghap_root_cause",
}


@pytest.fixture
async def vector_store() -> AsyncIterator[QdrantVectorStore]:
    """Create an in-memory Qdrant vector store for tests."""
    store = QdrantVectorStore(url=":memory:")
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


class TestGHAPRoundTrip:
    """Test GHAP entries survive round-trip serialization."""

    async def test_ghap_collector_round_trip(self) -> None:
        """Verify GHAP entry survives create -> update -> get_current cycle.

        Tests the local file-based storage in ObservationCollector.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)

            # Start session
            await collector.start_session()

            # Create with specific datetime (captured internally)
            original_domain = Domain.DEBUGGING
            original_strategy = Strategy.ROOT_CAUSE_ANALYSIS
            original_goal = "Test round-trip serialization"
            original_hypothesis = "Data survives storage"
            original_action = "Store and retrieve"
            original_prediction = "All fields preserved"

            entry = await collector.create_ghap(
                domain=original_domain,
                strategy=original_strategy,
                goal=original_goal,
                hypothesis=original_hypothesis,
                action=original_action,
                prediction=original_prediction,
            )

            # Store the original created_at for comparison
            original_created_at = entry.created_at

            # Retrieve and verify
            retrieved = await collector.get_current()
            assert retrieved is not None

            # Verify all fields
            assert retrieved.id == entry.id
            assert retrieved.domain == original_domain
            assert retrieved.strategy == original_strategy
            assert retrieved.goal == original_goal
            assert retrieved.hypothesis == original_hypothesis
            assert retrieved.action == original_action
            assert retrieved.prediction == original_prediction
            assert retrieved.iteration_count == 1

            # Verify datetime type and value preserved
            assert isinstance(retrieved.created_at, datetime)
            assert retrieved.created_at == original_created_at

            # Verify datetime is timezone-aware
            assert retrieved.created_at.tzinfo is not None

    async def test_ghap_persister_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify resolved GHAP entry survives persist -> retrieve cycle.

        Tests the vector store persistence via ObservationPersister.
        """
        # Create persister with test collection prefix
        persister = ObservationPersister(
            embedding_service=embedding_service,
            vector_store=vector_store,
            collection_prefix="test_rt_ghap",
        )

        # Create a resolved GHAP entry manually
        original_created_at = datetime.now(UTC)
        original_captured_at = datetime.now(UTC) + timedelta(minutes=5)

        from clams.observation.models import Outcome

        entry = GHAPEntry(
            id=f"test_ghap_{uuid4().hex[:8]}",
            session_id=f"session_{uuid4().hex[:8]}",
            created_at=original_created_at,
            domain=Domain.DEBUGGING,
            strategy=Strategy.ROOT_CAUSE_ANALYSIS,
            goal="Test persister round-trip",
            hypothesis="Vector store preserves data",
            action="Persist and retrieve",
            prediction="All fields intact",
            iteration_count=3,
            outcome=Outcome(
                status=OutcomeStatus.CONFIRMED,
                result="Data round-trip successful",
                captured_at=original_captured_at,
                auto_captured=False,
            ),
            confidence_tier=ConfidenceTier.SILVER,
        )

        # Persist to vector store
        await persister.persist(entry)

        # Retrieve from vector store
        result = await vector_store.get(
            collection=test_collections["full"],
            id=entry.id,
        )
        assert result is not None

        # Verify payload fields
        payload = result.payload
        assert payload["ghap_id"] == entry.id
        assert payload["domain"] == "debugging"
        assert payload["strategy"] == "root-cause-analysis"
        assert payload["outcome_status"] == "confirmed"
        assert payload["iteration_count"] == 3
        assert payload["confidence_tier"] == "silver"

        # Verify datetime fields - created_at stored as ISO string
        retrieved_created_at = datetime.fromisoformat(payload["created_at"])
        assert isinstance(retrieved_created_at, datetime)
        assert retrieved_created_at == original_created_at

        # Verify captured_at stored as timestamp
        retrieved_captured_at = datetime.fromtimestamp(
            payload["captured_at"], tz=UTC
        )
        assert isinstance(retrieved_captured_at, datetime)
        # Allow small tolerance for timestamp precision
        assert abs((retrieved_captured_at - original_captured_at).total_seconds()) < 1

    async def test_ghap_falsified_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify falsified GHAP with root_cause and surprise survives round-trip."""
        persister = ObservationPersister(
            embedding_service=embedding_service,
            vector_store=vector_store,
            collection_prefix="test_rt_ghap",
        )

        from clams.observation.models import Outcome

        original_root_cause = RootCause(
            category="wrong-assumption",
            description="The cache was not actually stale",
        )
        original_lesson = Lesson(
            what_worked="Checking logs before assuming",
            takeaway="Always verify assumptions with evidence",
        )
        original_surprise = "The issue was in the database, not the cache"

        entry = GHAPEntry(
            id=f"test_ghap_falsified_{uuid4().hex[:8]}",
            session_id=f"session_{uuid4().hex[:8]}",
            created_at=datetime.now(UTC),
            domain=Domain.DEBUGGING,
            strategy=Strategy.CHECK_ASSUMPTIONS,
            goal="Fix caching issue",
            hypothesis="Cache is stale",
            action="Clear cache",
            prediction="Issue will resolve",
            iteration_count=2,
            surprise=original_surprise,
            root_cause=original_root_cause,
            lesson=original_lesson,
            outcome=Outcome(
                status=OutcomeStatus.FALSIFIED,
                result="Cache was fine, database had stale data",
                captured_at=datetime.now(UTC),
            ),
            confidence_tier=ConfidenceTier.SILVER,
        )

        await persister.persist(entry)

        # Retrieve from full axis collection
        result = await vector_store.get(
            collection=test_collections["full"],
            id=entry.id,
        )
        assert result is not None

        payload = result.payload

        # Verify root_cause preserved
        assert "root_cause" in payload
        assert payload["root_cause"]["category"] == "wrong-assumption"
        assert payload["root_cause"]["description"] == original_root_cause.description

        # Verify lesson preserved
        assert "lesson" in payload
        assert payload["lesson"]["what_worked"] == original_lesson.what_worked
        assert payload["lesson"]["takeaway"] == original_lesson.takeaway

        # Verify surprise preserved
        assert payload["surprise"] == original_surprise

        # Also check root_cause axis collection for falsified entries
        result_rc = await vector_store.get(
            collection=test_collections["root_cause"],
            id=entry.id,
        )
        assert result_rc is not None
        assert result_rc.payload["root_cause"]["category"] == "wrong-assumption"


class TestMemoryRoundTrip:
    """Test memories survive round-trip serialization."""

    async def test_memory_store_retrieve_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify memory survives storage and retrieval."""
        collection = test_collections["memories"]
        memory_id = str(uuid4())
        original_content = "Important fact about round-trip testing"
        original_importance = 0.75
        original_tags = ["test", "round-trip", "integration"]
        original_created_at = datetime.now(UTC)

        # Store memory directly in vector store
        embedding = await embedding_service.embed(original_content)
        payload = {
            "id": memory_id,
            "content": original_content,
            "category": "fact",
            "importance": original_importance,
            "tags": original_tags,
            "created_at": original_created_at.isoformat(),
        }

        await vector_store.upsert(
            collection=collection,
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        # Retrieve and verify
        result = await vector_store.get(collection, memory_id)
        assert result is not None

        # Verify content preserved
        assert result.payload["content"] == original_content
        assert result.payload["category"] == "fact"

        # Verify importance (float) preserved
        assert result.payload["importance"] == original_importance
        assert isinstance(result.payload["importance"], float)

        # Verify tags preserved
        assert result.payload["tags"] == original_tags

        # Verify created_at preserved (stored as ISO string)
        retrieved_created_at = datetime.fromisoformat(result.payload["created_at"])
        assert isinstance(retrieved_created_at, datetime)
        assert retrieved_created_at == original_created_at

    async def test_memory_search_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify memory data preserved through semantic search."""
        collection = test_collections["memories"]

        # Store multiple memories
        memories = [
            {
                "id": f"mem_{i}",
                "content": f"Test memory content {i}",
                "category": "fact" if i % 2 == 0 else "preference",
                "importance": 0.5 + (i * 0.1),
                "tags": [f"tag{i}"],
                "created_at": datetime.now(UTC).isoformat(),
            }
            for i in range(3)
        ]

        for mem in memories:
            embedding = await embedding_service.embed(mem["content"])
            await vector_store.upsert(
                collection=collection,
                id=mem["id"],
                vector=embedding,
                payload=mem,
            )

        # Search
        query_embedding = await embedding_service.embed("test memory")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
        )

        # Verify all results have complete data
        for result in results:
            assert "content" in result.payload
            assert "category" in result.payload
            assert "importance" in result.payload
            assert isinstance(result.payload["importance"], float)
            assert "tags" in result.payload
            assert isinstance(result.payload["tags"], list)


class TestValueRoundTrip:
    """Test values survive round-trip serialization."""

    async def test_value_store_list_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify value survives store and list_values cycle."""
        collection = test_collections["values"]

        # Store value directly (simulating ValueStore.store_value)
        value_id = f"value_test_{uuid4().hex[:8]}"
        original_text = "When debugging, always check logs first"
        original_axis = "strategy"
        original_cluster_id = "strategy_0"
        original_cluster_size = 5
        original_created_at = datetime.now(UTC).isoformat()
        original_similarity = 0.85

        embedding = await embedding_service.embed(original_text)
        payload = {
            "text": original_text,
            "cluster_id": original_cluster_id,
            "axis": original_axis,
            "cluster_label": 0,
            "cluster_size": original_cluster_size,
            "created_at": original_created_at,
            "validation": {
                "candidate_distance": 0.15,
                "mean_distance": 0.20,
                "threshold": 0.25,
                "similarity": original_similarity,
            },
        }

        await vector_store.upsert(
            collection=collection,
            id=value_id,
            vector=embedding,
            payload=payload,
        )

        # Retrieve via scroll (similar to list_values)
        results = await vector_store.scroll(
            collection=collection,
            limit=100,
            with_vectors=True,
        )

        assert len(results) >= 1
        value_result = next((r for r in results if r.id == value_id), None)
        assert value_result is not None

        # Verify all fields preserved
        assert value_result.payload["text"] == original_text
        assert value_result.payload["axis"] == original_axis
        assert value_result.payload["cluster_id"] == original_cluster_id
        assert value_result.payload["cluster_size"] == original_cluster_size

        # Verify nested validation metrics (floats)
        validation = value_result.payload["validation"]
        assert isinstance(validation["similarity"], float)
        assert validation["similarity"] == original_similarity
        assert isinstance(validation["candidate_distance"], float)
        assert isinstance(validation["mean_distance"], float)
        assert isinstance(validation["threshold"], float)

        # Verify embedding preserved
        assert value_result.vector is not None
        assert len(value_result.vector) == 768


class TestDatetimeRoundTrip:
    """Specific tests for datetime field preservation.

    Reference: BUG-027 - datetime stored as ISO string but read expecting timestamp
    """

    async def test_datetime_iso_string_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify datetime stored as ISO string survives round-trip."""
        collection = test_collections["memories"]

        # Test various datetime formats
        test_cases = [
            datetime.now(UTC),  # Current time with UTC
            datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC),  # Specific time
            datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),  # Microseconds
        ]

        for i, original_dt in enumerate(test_cases):
            doc_id = f"dt_test_{i}"
            embedding = await embedding_service.embed(f"datetime test {i}")

            # Store with ISO format (current convention)
            await vector_store.upsert(
                collection=collection,
                id=doc_id,
                vector=embedding,
                payload={
                    "created_at": original_dt.isoformat(),
                    "test_index": i,
                },
            )

            # Retrieve
            result = await vector_store.get(collection, doc_id)
            assert result is not None

            # Parse and verify
            retrieved_dt = datetime.fromisoformat(result.payload["created_at"])

            # Verify type
            assert isinstance(retrieved_dt, datetime)

            # Verify timezone preserved
            assert retrieved_dt.tzinfo is not None

            # Verify value preserved (within microsecond precision)
            assert retrieved_dt == original_dt

    async def test_datetime_timestamp_round_trip(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify datetime stored as Unix timestamp survives round-trip."""
        collection = test_collections["memories"]

        original_dt = datetime.now(UTC)
        original_timestamp = original_dt.timestamp()

        embedding = await embedding_service.embed("timestamp test")

        await vector_store.upsert(
            collection=collection,
            id="ts_test",
            vector=embedding,
            payload={
                "captured_at": original_timestamp,
            },
        )

        result = await vector_store.get(collection, "ts_test")
        assert result is not None

        # Retrieve and convert back
        retrieved_timestamp = result.payload["captured_at"]
        retrieved_dt = datetime.fromtimestamp(retrieved_timestamp, tz=UTC)

        # Verify type
        assert isinstance(retrieved_dt, datetime)

        # Verify value (allow small tolerance for float precision)
        assert abs((retrieved_dt - original_dt).total_seconds()) < 0.001


class TestNumericRoundTrip:
    """Specific tests for numeric field preservation, especially floats.

    Reference: BUG-034 - float truncation issues
    """

    async def test_float_precision_preserved(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify float values don't lose precision in storage."""
        collection = test_collections["memories"]

        # Test various float values that could be problematic
        test_floats = [
            0.5,  # Simple fraction
            0.75,
            0.123456789,  # Many decimal places
            1e-10,  # Very small
            1e10,  # Very large
            3.141592653589793,  # Pi with many decimals
            -0.5,  # Negative
            0.0,  # Zero
            1.0,  # One (could be confused with int)
        ]

        for i, original_float in enumerate(test_floats):
            doc_id = f"float_test_{i}"
            embedding = await embedding_service.embed(f"float test {i}")

            await vector_store.upsert(
                collection=collection,
                id=doc_id,
                vector=embedding,
                payload={
                    "importance": original_float,
                    "score": original_float,
                    "test_index": i,
                },
            )

            result = await vector_store.get(collection, doc_id)
            assert result is not None

            # Verify type preserved
            assert isinstance(result.payload["importance"], float)
            assert isinstance(result.payload["score"], float)

            # Verify value preserved (with reasonable precision)
            assert abs(result.payload["importance"] - original_float) < 1e-9
            assert abs(result.payload["score"] - original_float) < 1e-9

    async def test_integer_preserved(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify integer values preserved correctly."""
        collection = test_collections["memories"]

        test_ints = [0, 1, -1, 100, 1000000, -999]

        for i, original_int in enumerate(test_ints):
            doc_id = f"int_test_{i}"
            embedding = await embedding_service.embed(f"int test {i}")

            await vector_store.upsert(
                collection=collection,
                id=doc_id,
                vector=embedding,
                payload={
                    "count": original_int,
                    "iteration_count": original_int,
                },
            )

            result = await vector_store.get(collection, doc_id)
            assert result is not None

            # Verify value preserved
            assert result.payload["count"] == original_int
            assert result.payload["iteration_count"] == original_int


class TestCompleteWorkflowRoundTrip:
    """Test complete data flow round-trips across multiple components."""

    async def test_ghap_full_lifecycle_round_trip(self) -> None:
        """Verify GHAP data integrity through complete lifecycle.

        Tests: create -> update -> update -> resolve -> get_session_entries
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)

            await collector.start_session()

            # Create
            entry = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.SYSTEMATIC_ELIMINATION,
                goal="Test complete lifecycle",
                hypothesis="All data flows correctly",
                action="Run lifecycle test",
                prediction="All assertions pass",
            )
            original_id = entry.id
            original_created_at = entry.created_at

            # Update 1
            await collector.update_ghap(
                hypothesis="Updated hypothesis 1",
                note="First update note",
            )

            # Update 2
            await collector.update_ghap(
                hypothesis="Updated hypothesis 2",
                action="Modified action",
            )

            # Verify updates
            current = await collector.get_current()
            assert current is not None
            assert current.id == original_id
            assert current.iteration_count == 3
            assert len(current.history) == 2
            assert current.hypothesis == "Updated hypothesis 2"
            assert current.action == "Modified action"
            assert current.created_at == original_created_at

            # Resolve
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="All tests passed successfully",
                lesson=Lesson(
                    what_worked="Systematic approach",
                    takeaway="Always iterate carefully",
                ),
            )

            assert resolved.id == original_id
            assert resolved.outcome is not None
            assert resolved.outcome.status == OutcomeStatus.CONFIRMED
            assert resolved.confidence_tier is not None
            assert resolved.lesson is not None
            assert resolved.lesson.what_worked == "Systematic approach"
            assert resolved.created_at == original_created_at

            # Verify in session entries
            entries = await collector.get_session_entries()
            assert len(entries) == 1
            assert entries[0].id == original_id
            assert entries[0].iteration_count == 3
            assert entries[0].created_at == original_created_at
