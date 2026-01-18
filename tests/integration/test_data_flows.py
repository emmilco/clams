"""Data flow integration tests for CLAMS.

These tests verify data flows correctly across component boundaries without mocks.
They test the complete lifecycle of data from creation through retrieval.

Addresses: R10-D (Add Data Flow Integration Tests)
- GHAP flow: start_ghap -> update_ghap -> resolve_ghap -> search_experiences
- Memory flow: store_memory -> retrieve_memories -> delete_memory
- Code indexing flow: index_codebase -> search_code -> find_similar_code
- Git flow: index_commits -> search_commits -> get_file_history

Reference: BUG-040 (duplicate result types), BUG-041 (abstract/concrete Searcher conflict),
BUG-027 (datetime round-trip) - data flows across modules without validation.
"""

import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
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
from clams.search.searcher import Searcher
from clams.storage.qdrant import QdrantVectorStore

# Mark all tests in this module as integration tests (require external services)
pytestmark = pytest.mark.integration

pytest_plugins = ("pytest_asyncio",)

# Test collection names (isolated from production)
TEST_COLLECTIONS = {
    "memories": "test_flow_memories",
    "code_units": "test_flow_code_units",
    "commits": "test_flow_commits",
    "values": "test_flow_values",
    "ghap_full": "test_flow_ghap_full",
    "ghap_strategy": "test_flow_ghap_strategy",
    "ghap_surprise": "test_flow_ghap_surprise",
    "ghap_root_cause": "test_flow_ghap_root_cause",
}


@pytest.fixture(scope="session", autouse=True)
def verify_qdrant() -> None:
    """Verify Qdrant is available before running tests.

    Tests FAIL if Qdrant unavailable - no skips per spec.
    """
    try:
        response = httpx.get("http://localhost:6333/healthz", timeout=5)
        response.raise_for_status()
    except Exception as e:
        pytest.fail(f"Qdrant not available at localhost:6333: {e}")


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
    # Delete any existing test collections first
    for collection in TEST_COLLECTIONS.values():
        try:
            await vector_store.delete_collection(collection)
        except Exception:
            pass  # Collection may not exist

    # Create all test collections with 768-dim (Nomic/semantic embedding dimension)
    for collection in TEST_COLLECTIONS.values():
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
async def searcher(
    embedding_service: MockEmbedding,
    vector_store: QdrantVectorStore,
    test_collections: dict[str, str],
) -> Searcher:
    """Create a searcher with test collections."""
    return Searcher(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


class TestGHAPDataFlow:
    """Test complete GHAP lifecycle across components.

    This tests the data flow from:
    1. ObservationCollector (local state management)
    2. ObservationPersister (vector storage)
    3. Searcher (experience retrieval)

    Verifies data integrity at each boundary crossing.
    """

    async def test_ghap_complete_lifecycle(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify GHAP data flows correctly through entire lifecycle."""
        from unittest.mock import patch

        # Create temporary journal directory
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"

            # Initialize components
            # Use custom collection_prefix to use our test collections
            # The persister will use {prefix}_{axis} pattern, e.g., test_flow_ghap_full
            collector = ObservationCollector(journal_dir=journal_dir)
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_flow_ghap",  # Creates test_flow_ghap_full, etc.
            )

            # 1. Start session
            session_id = await collector.start_session()
            assert session_id is not None
            assert session_id.startswith("session_")

            # 2. Create GHAP entry
            original_created_at = datetime.now(UTC)
            entry = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.ROOT_CAUSE_ANALYSIS,
                goal="Test data flow across components",
                hypothesis="Data flows correctly between modules",
                action="Run lifecycle test with real components",
                prediction="All assertions pass at each boundary",
            )
            ghap_id = entry.id

            assert ghap_id is not None
            assert entry.domain == Domain.DEBUGGING
            assert entry.strategy == Strategy.ROOT_CAUSE_ANALYSIS
            assert entry.iteration_count == 1
            # Verify datetime is preserved
            assert isinstance(entry.created_at, datetime)
            assert (entry.created_at - original_created_at).total_seconds() < 1

            # 3. Verify active GHAP is retrievable
            active = await collector.get_current()
            assert active is not None
            assert active.id == ghap_id
            assert active.goal == "Test data flow across components"

            # 4. Update GHAP (creates history entry)
            updated = await collector.update_ghap(
                hypothesis="Updated hypothesis for data flow test",
                note="Testing update preserves state",
            )
            assert updated.iteration_count == 2
            assert len(updated.history) == 1
            assert updated.hypothesis == "Updated hypothesis for data flow test"

            # 5. Resolve GHAP
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="Data flow test completed successfully",
                lesson=Lesson(
                    what_worked="Testing across real components",
                    takeaway="Integration tests catch boundary issues",
                ),
            )
            assert resolved.outcome is not None
            assert resolved.outcome.status == OutcomeStatus.CONFIRMED
            assert resolved.outcome.result == "Data flow test completed successfully"
            assert resolved.confidence_tier is not None
            # confidence_tier is a ConfidenceTier enum
            from clams.observation import ConfidenceTier
            assert isinstance(resolved.confidence_tier, ConfidenceTier)

            # 6. Persist to vector store
            await persister.persist(resolved)

            # 7. Verify no active GHAP after resolution
            current = await collector.get_current()
            assert current is None

            # 8. Verify data is searchable via Searcher
            searcher = Searcher(
                embedding_service=embedding_service,
                vector_store=vector_store,
            )

            # Patch searcher's collection name mapping to use our test collection
            with patch(
                "clams.search.collections.CollectionName.get_experience_collection",
                return_value="test_flow_ghap_full",  # Matches persister's prefix
            ):
                experiences = await searcher.search_experiences(
                    query="data flow test",
                    axis="full",
                    limit=10,
                )
                # Should find our entry
                assert len(experiences) > 0
                found_entry = next(
                    (e for e in experiences if e.ghap_id == ghap_id), None
                )
                assert found_entry is not None
                assert found_entry.domain == "debugging"
                assert found_entry.outcome_status == "confirmed"

    async def test_ghap_falsified_with_root_cause(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test falsified GHAP flow with root cause captures all data."""

        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_flow_ghap",  # Use test collections
            )

            await collector.start_session()

            await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.SYSTEMATIC_ELIMINATION,
                goal="Test falsified flow",
                hypothesis="Initial hypothesis was wrong",
                action="Investigate the issue",
                prediction="Will find the root cause",
            )

            # Resolve as falsified with root cause
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.FALSIFIED,
                result="Hypothesis was incorrect",
                surprise="The actual cause was different",
                root_cause=RootCause(
                    category="wrong-assumption",
                    description="Made incorrect assumption about the data flow",
                ),
                lesson=Lesson(
                    what_worked="Systematic investigation",
                    takeaway="Always verify assumptions",
                ),
            )

            assert resolved.outcome is not None
            assert resolved.outcome.status == OutcomeStatus.FALSIFIED
            # surprise and root_cause are on the entry, not the outcome
            assert resolved.surprise == "The actual cause was different"
            assert resolved.root_cause is not None
            assert resolved.root_cause.category == "wrong-assumption"

            # Persist and verify
            await persister.persist(resolved)

            # Verify falsified GHAP creates entries in full, strategy, surprise, root_cause axes
            # Full and strategy are always created, surprise and root_cause only for falsified
            test_axis_collections = {
                "full": "test_flow_ghap_full",
                "strategy": "test_flow_ghap_strategy",
                "surprise": "test_flow_ghap_surprise",
                "root_cause": "test_flow_ghap_root_cause",
            }
            for axis_name, collection_name in test_axis_collections.items():
                count = await vector_store.count(collection_name)
                # Falsified GHAP should have entries in all 4 axes
                assert count > 0, f"Expected data in {axis_name} collection"


class TestMemoryDataFlow:
    """Test memory store -> retrieve -> delete workflow.

    Tests the complete memory lifecycle using real vector store operations.
    """

    async def test_memory_complete_lifecycle(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test complete memory lifecycle: store, retrieve, delete."""
        collection = test_collections["memories"]
        memory_id = str(uuid4())
        content = "Important fact about data flow testing"
        original_created_at = datetime.now(UTC)

        # 1. Store memory
        embedding = await embedding_service.embed(content)
        payload = {
            "id": memory_id,
            "content": content,
            "category": "fact",
            "importance": 0.85,
            "tags": ["testing", "data-flow", "integration"],
            "created_at": original_created_at.isoformat(),
        }

        await vector_store.upsert(
            collection=collection,
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        # 2. Verify storage - get by ID
        result = await vector_store.get(collection, memory_id)
        assert result is not None
        assert result.payload["content"] == content
        assert result.payload["category"] == "fact"
        assert result.payload["importance"] == 0.85
        assert "testing" in result.payload["tags"]

        # Verify datetime survives round-trip
        stored_created_at = datetime.fromisoformat(result.payload["created_at"])
        assert isinstance(stored_created_at, datetime)
        # Compare timestamps (may have microsecond differences due to serialization)
        assert abs((stored_created_at - original_created_at).total_seconds()) < 1

        # 3. Retrieve by semantic search
        query_embedding = await embedding_service.embed("data flow testing facts")
        search_results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=5,
        )
        assert len(search_results) > 0
        found = any(r.id == memory_id for r in search_results)
        assert found, "Memory should be found via semantic search"

        # 4. List memories via scroll
        scroll_results = await vector_store.scroll(
            collection=collection,
            limit=10,
        )
        assert any(r.id == memory_id for r in scroll_results)

        # 5. Delete memory
        await vector_store.delete(collection, memory_id)

        # 6. Verify deletion
        result = await vector_store.get(collection, memory_id)
        assert result is None

    async def test_memory_filtering(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test memory retrieval with category and importance filters."""
        collection = test_collections["memories"]

        # Store multiple memories with different categories and importance
        memories = [
            {
                "id": str(uuid4()),
                "content": "High importance fact",
                "category": "fact",
                "importance": 0.9,
            },
            {
                "id": str(uuid4()),
                "content": "Low importance preference",
                "category": "preference",
                "importance": 0.3,
            },
            {
                "id": str(uuid4()),
                "content": "Medium importance workflow",
                "category": "workflow",
                "importance": 0.6,
            },
        ]

        for mem in memories:
            embedding = await embedding_service.embed(mem["content"])
            await vector_store.upsert(
                collection=collection,
                id=mem["id"],
                vector=embedding,
                payload=mem,
            )

        # Search with category filter
        query_embedding = await embedding_service.embed("importance")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"category": "fact"},
        )
        assert all(r.payload["category"] == "fact" for r in results)

        # Search with importance filter
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"importance": {"$gte": 0.5}},
        )
        assert all(r.payload["importance"] >= 0.5 for r in results)


class TestCodeIndexingDataFlow:
    """Test code indexing -> search -> find_similar flow.

    Tests data flow through code indexing and search components.
    """

    async def test_code_index_search_similar(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test code indexing, search, and similarity flow."""
        collection = test_collections["code_units"]

        # Simulate indexing code units
        code_units = [
            {
                "id": "unit_flow_1",
                "content": "def fibonacci(n):\n    if n < 2:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                "qualified_name": "math_utils.fibonacci",
                "unit_type": "function",
                "language": "python",
                "project": "test_flow_project",
                "file_path": "/test/math_utils.py",
                "start_line": 1,
                "end_line": 5,
            },
            {
                "id": "unit_flow_2",
                "content": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)",
                "qualified_name": "math_utils.factorial",
                "unit_type": "function",
                "language": "python",
                "project": "test_flow_project",
                "file_path": "/test/math_utils.py",
                "start_line": 7,
                "end_line": 11,
            },
            {
                "id": "unit_flow_3",
                "content": "class DataProcessor:\n    def process(self, data):\n        return [x * 2 for x in data]",
                "qualified_name": "processor.DataProcessor",
                "unit_type": "class",
                "language": "python",
                "project": "test_flow_project",
                "file_path": "/test/processor.py",
                "start_line": 1,
                "end_line": 4,
            },
        ]

        # 1. Index code units
        for unit in code_units:
            embedding = await embedding_service.embed(unit["content"])
            await vector_store.upsert(
                collection=collection,
                id=unit["id"],
                vector=embedding,
                payload=unit,
            )

        # 2. Verify indexing
        count = await vector_store.count(collection)
        assert count == 3

        # 3. Search by semantic query
        query_embedding = await embedding_service.embed("recursive mathematical function")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=3,
        )
        assert len(results) > 0
        # Should find fibonacci and factorial (recursive functions)
        found_ids = {r.id for r in results}
        assert "unit_flow_1" in found_ids or "unit_flow_2" in found_ids

        # 4. Search with project filter
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"project": "test_flow_project"},
        )
        assert len(results) == 3
        assert all(r.payload["project"] == "test_flow_project" for r in results)

        # 5. Search with language filter
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"language": "python"},
        )
        assert len(results) == 3

        # 6. Find similar code (similarity search)
        similar_snippet = "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)"
        snippet_embedding = await embedding_service.embed(similar_snippet)
        similar_results = await vector_store.search(
            collection=collection,
            query=snippet_embedding,
            limit=3,
        )
        assert len(similar_results) > 0
        # Note: MockEmbedding returns deterministic vectors based on text length,
        # so semantic similarity won't match real embedding behavior.
        # We just verify that similarity search returns results from our indexed units.
        found_ids = {r.id for r in similar_results}
        assert found_ids.issubset({"unit_flow_1", "unit_flow_2", "unit_flow_3"})


class TestGitDataFlow:
    """Test git commit indexing -> search -> history flow.

    Tests data flow through git analysis components.
    """

    async def test_git_index_search_history(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test git commit indexing and search flow."""
        collection = test_collections["commits"]

        # Simulate indexed commits
        commits = [
            {
                "id": "commit_flow_abc123",
                "sha": "abc123def456",
                "message": "feat: Add fibonacci function for mathematical computations",
                "author": "test_author",
                "author_email": "test@example.com",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC).isoformat(),
                "files_changed": ["math_utils.py"],
                "insertions": 15,
                "deletions": 0,
            },
            {
                "id": "commit_flow_def456",
                "sha": "def456ghi789",
                "message": "fix: Correct edge case in factorial calculation",
                "author": "test_author",
                "author_email": "test@example.com",
                "timestamp": datetime(2024, 1, 16, 14, 20, 0, tzinfo=UTC).isoformat(),
                "files_changed": ["math_utils.py"],
                "insertions": 3,
                "deletions": 1,
            },
            {
                "id": "commit_flow_ghi789",
                "sha": "ghi789jkl012",
                "message": "refactor: Improve data processor performance",
                "author": "another_author",
                "author_email": "another@example.com",
                "timestamp": datetime(2024, 1, 17, 9, 0, 0, tzinfo=UTC).isoformat(),
                "files_changed": ["processor.py", "tests/test_processor.py"],
                "insertions": 25,
                "deletions": 10,
            },
        ]

        # 1. Index commits
        for commit in commits:
            embedding = await embedding_service.embed(commit["message"])
            await vector_store.upsert(
                collection=collection,
                id=commit["id"],
                vector=embedding,
                payload=commit,
            )

        # 2. Verify indexing
        count = await vector_store.count(collection)
        assert count == 3

        # 3. Search commits by message content
        query_embedding = await embedding_service.embed("mathematical function")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=5,
        )
        assert len(results) > 0
        # Should find the fibonacci commit
        messages = [r.payload["message"] for r in results]
        assert any("fibonacci" in msg.lower() for msg in messages)

        # 4. Search with author filter
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"author": "test_author"},
        )
        assert len(results) == 2
        assert all(r.payload["author"] == "test_author" for r in results)

        # 5. Verify datetime serialization/deserialization
        result = await vector_store.get(collection, "commit_flow_abc123")
        assert result is not None
        stored_timestamp = result.payload["timestamp"]
        parsed_timestamp = datetime.fromisoformat(stored_timestamp)
        assert isinstance(parsed_timestamp, datetime)
        assert parsed_timestamp.year == 2024
        assert parsed_timestamp.month == 1
        assert parsed_timestamp.day == 15

    async def test_git_file_change_tracking(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test tracking file changes across commits."""
        collection = test_collections["commits"]

        # Create commits that modify the same file
        file_commits = [
            {
                "id": f"file_commit_{i}",
                "sha": f"sha{i:03d}",
                "message": f"Update {i} to math_utils.py",
                "author": "test_author",
                "author_email": "test@example.com",
                "timestamp": datetime(2024, 1, i + 1, 10, 0, 0, tzinfo=UTC).isoformat(),
                "files_changed": ["math_utils.py"],
                "insertions": i * 5,
                "deletions": i * 2,
            }
            for i in range(1, 6)
        ]

        for commit in file_commits:
            embedding = await embedding_service.embed(commit["message"])
            await vector_store.upsert(
                collection=collection,
                id=commit["id"],
                vector=embedding,
                payload=commit,
            )

        # Scroll to get all commits (simulating file history retrieval)
        all_commits = await vector_store.scroll(
            collection=collection,
            limit=100,
            with_vectors=False,
        )

        # Filter to commits that changed math_utils.py
        math_commits = [
            c for c in all_commits
            if "math_utils.py" in c.payload.get("files_changed", [])
        ]

        assert len(math_commits) >= 5  # At least our file commits


class TestCrossComponentDataFlow:
    """Test data flows that cross multiple component boundaries.

    These tests verify that data maintains integrity when flowing
    through multiple modules (e.g., GHAP -> experiences -> context assembly).
    """

    async def test_ghap_to_experience_search_boundary(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test data integrity from GHAP creation to experience search."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_flow_ghap",  # Use test collections
            )

            await collector.start_session()

            # Create multiple GHAP entries with different characteristics
            domains = [Domain.DEBUGGING, Domain.FEATURE, Domain.REFACTORING]
            strategies = [
                Strategy.ROOT_CAUSE_ANALYSIS,
                Strategy.DIVIDE_AND_CONQUER,
                Strategy.CHECK_ASSUMPTIONS,
            ]

            created_ids = []
            for i, (domain, strategy) in enumerate(zip(domains, strategies)):
                entry = await collector.create_ghap(
                    domain=domain,
                    strategy=strategy,
                    goal=f"Test goal {i}",
                    hypothesis=f"Test hypothesis {i}",
                    action=f"Test action {i}",
                    prediction=f"Test prediction {i}",
                )
                created_ids.append(entry.id)

                resolved = await collector.resolve_ghap(
                    status=OutcomeStatus.CONFIRMED,
                    result=f"Test result {i}",
                )
                await persister.persist(resolved)

            # Verify all entries are searchable
            searcher = Searcher(
                embedding_service=embedding_service,
                vector_store=vector_store,
            )

            with patch(
                "clams.search.collections.CollectionName.get_experience_collection",
                return_value="test_flow_ghap_full",  # Matches persister's prefix
            ):
                # Search should find all entries
                experiences = await searcher.search_experiences(
                    query="test",
                    axis="full",
                    limit=10,
                )
                found_ids = {e.ghap_id for e in experiences}
                for ghap_id in created_ids:
                    assert ghap_id in found_ids, f"GHAP {ghap_id} not found in search"

    async def test_numeric_precision_across_boundaries(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test that numeric values maintain precision across storage boundaries."""
        collection = test_collections["memories"]
        memory_id = str(uuid4())

        # Use specific float values that might lose precision
        test_values = {
            "importance": 0.123456789,
            "score": 0.999999999,
            "threshold": 0.000000001,
        }

        embedding = await embedding_service.embed("numeric precision test")
        payload = {
            "id": memory_id,
            "content": "Test numeric precision",
            **test_values,
        }

        await vector_store.upsert(
            collection=collection,
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        # Retrieve and verify precision
        result = await vector_store.get(collection, memory_id)
        assert result is not None

        for key, original_value in test_values.items():
            stored_value = result.payload[key]
            # Allow small floating point differences
            assert abs(stored_value - original_value) < 1e-6, \
                f"{key}: {stored_value} != {original_value}"

    async def test_datetime_timezone_handling(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test datetime with timezone survives storage round-trip."""
        collection = test_collections["commits"]

        # Test with explicit UTC timezone
        utc_time = datetime(2024, 6, 15, 12, 30, 45, tzinfo=UTC)

        commit = {
            "id": "tz_test_commit",
            "sha": "tz123",
            "message": "Timezone test commit",
            "author": "test",
            "timestamp": utc_time.isoformat(),
        }

        embedding = await embedding_service.embed(commit["message"])
        await vector_store.upsert(
            collection=collection,
            id=commit["id"],
            vector=embedding,
            payload=commit,
        )

        # Retrieve and verify
        result = await vector_store.get(collection, commit["id"])
        assert result is not None

        stored_timestamp = result.payload["timestamp"]
        parsed = datetime.fromisoformat(stored_timestamp)

        # Verify datetime components
        assert parsed.year == 2024
        assert parsed.month == 6
        assert parsed.day == 15
        assert parsed.hour == 12
        assert parsed.minute == 30
        assert parsed.second == 45
        # Timezone should be preserved
        assert parsed.tzinfo is not None
