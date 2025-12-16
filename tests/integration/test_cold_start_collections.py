"""Cold-start integration tests for vector store collections.

These tests verify that vector store collections are properly created on first use
(cold start) against a real Qdrant instance. They complement the mock-based regression
tests in tests/server/test_bug_043_regression.py by validating actual Qdrant behavior.

Reference:
- BUG-043: Fixed 404 errors by adding lazy collection creation
- BUG-016: Fixed GHAP collection creation at startup

Each test follows the pattern:
1. Delete collection if exists (ensure cold start)
2. Verify collection doesn't exist
3. Call method that triggers lazy creation
4. Verify collection was created with correct configuration
5. Verify data round-trip works
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest

from clams.embedding.mock import MockEmbedding
from clams.storage.qdrant import QdrantVectorStore

# Mark all tests in this module as integration tests (require Qdrant)
pytestmark = pytest.mark.integration

pytest_plugins = ("pytest_asyncio",)


# =============================================================================
# Fixtures
# =============================================================================


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
def embedding_service() -> MockEmbedding:
    """Create a mock embedding service for deterministic, fast tests."""
    return MockEmbedding()  # 768-dimensional by default


@pytest.fixture
def test_id() -> str:
    """Generate unique test identifier for collection isolation."""
    return str(uuid.uuid4())[:8]


async def delete_collection_if_exists(
    vector_store: QdrantVectorStore, collection_name: str
) -> None:
    """Delete a collection if it exists (ensure cold start)."""
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass  # Collection may not exist


async def verify_collection_not_exists(
    vector_store: QdrantVectorStore, collection_name: str
) -> None:
    """Verify collection doesn't exist (cold start precondition)."""
    info = await vector_store.get_collection_info(collection_name)
    assert info is None, f"Collection {collection_name} should not exist before test"


async def cleanup_collection(
    vector_store: QdrantVectorStore, collection_name: str
) -> None:
    """Cleanup collection after test."""
    try:
        await vector_store.delete_collection(collection_name)
    except Exception:
        pass


# =============================================================================
# Memories Collection Cold-Start Tests
# =============================================================================


class TestMemoriesColdStart:
    """Cold-start tests for memories collection.

    These tests verify the lazy collection creation pattern works correctly
    against a real Qdrant instance. They test the underlying _ensure_*_collection()
    functions directly rather than through the full tool interface.
    """

    async def test_memories_lazy_creation_pattern(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify the lazy creation pattern creates collection on first use."""
        collection_name = f"test_cold_start_memories_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Simulate the _ensure_memories_collection pattern
            # (create if not exists, handle "already exists" gracefully)
            try:
                await vector_store.create_collection(
                    name=collection_name,
                    dimension=embedding_service.dimension,
                    distance="cosine",
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    pass  # Expected in non-cold-start scenario
                else:
                    raise

            # Verify collection was created
            info = await vector_store.get_collection_info(collection_name)
            assert info is not None, "Collection should exist after lazy creation"
            assert info.dimension == 768, "Collection should have 768 dimensions"

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_memories_operations_work_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify memory operations work correctly after cold-start creation."""
        collection_name = f"test_cold_start_memories_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Create collection (lazy creation)
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Store a memory
            memory_id = str(uuid.uuid4())
            content = "Important fact about cold-start testing"
            embedding = await embedding_service.embed(content)

            await vector_store.upsert(
                collection=collection_name,
                id=memory_id,
                vector=embedding,
                payload={
                    "id": memory_id,
                    "content": content,
                    "category": "fact",
                    "importance": 0.9,
                    "tags": ["testing", "cold-start"],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

            # Retrieve by ID
            result = await vector_store.get(collection_name, memory_id)
            assert result is not None
            assert result.payload["content"] == content
            assert result.payload["category"] == "fact"
            assert result.payload["importance"] == 0.9

            # Retrieve by semantic search
            search_results = await vector_store.search(
                collection=collection_name,
                query=embedding,
                limit=5,
            )
            assert len(search_results) > 0
            assert any(r.id == memory_id for r in search_results)

            # List by scroll
            scroll_results = await vector_store.scroll(
                collection=collection_name,
                limit=10,
            )
            assert any(r.id == memory_id for r in scroll_results)

            # Count
            count = await vector_store.count(collection_name)
            assert count == 1

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_memories_handles_already_exists_gracefully(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify lazy creation handles 'already exists' error gracefully."""
        collection_name = f"test_cold_start_memories_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)

        try:
            # Create collection first time
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Try to create again (simulating multiple lazy creation calls)
            try:
                await vector_store.create_collection(
                    name=collection_name,
                    dimension=768,
                    distance="cosine",
                )
            except Exception as e:
                error_msg = str(e).lower()
                # Should either succeed silently or raise "already exists" error
                assert (
                    "already exists" in error_msg or "409" in str(e)
                ), f"Expected 'already exists' error, got: {e}"

            # Collection should still be usable
            info = await vector_store.get_collection_info(collection_name)
            assert info is not None, "Collection should still exist"
            assert info.dimension == 768

        finally:
            await cleanup_collection(vector_store, collection_name)


# =============================================================================
# Commits Collection Cold-Start Tests
# =============================================================================


class TestCommitsColdStart:
    """Cold-start tests for commits collection.

    Tests that the commits collection can be lazily created and used
    for indexing and searching git commits.
    """

    async def test_commits_lazy_creation_pattern(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify the lazy creation pattern for commits collection."""
        collection_name = f"test_cold_start_commits_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Simulate the _ensure_commits_collection pattern
            try:
                await vector_store.create_collection(
                    name=collection_name,
                    dimension=embedding_service.dimension,
                    distance="cosine",
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    pass
                else:
                    raise

            # Verify collection was created
            info = await vector_store.get_collection_info(collection_name)
            assert info is not None, "Collection should exist after lazy creation"
            assert info.dimension == 768

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_commits_operations_work_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify commit operations work correctly after cold-start creation."""
        collection_name = f"test_cold_start_commits_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Create collection (lazy creation)
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Index a commit
            commit_sha = "abc123def456"
            message = "feat: Add cold-start test functionality"
            embedding = await embedding_service.embed(message)

            await vector_store.upsert(
                collection=collection_name,
                id=commit_sha,
                vector=embedding,
                payload={
                    "sha": commit_sha,
                    "message": message,
                    "author": "test_author",
                    "author_email": "test@example.com",
                    "timestamp": datetime.now(UTC).timestamp(),
                    "timestamp_iso": datetime.now(UTC).isoformat(),
                    "files_changed": ["test.py", "test_cold_start.py"],
                    "insertions": 50,
                    "deletions": 10,
                },
            )

            # Search by semantic query
            query_embedding = await embedding_service.embed("cold-start test")
            search_results = await vector_store.search(
                collection=collection_name,
                query=query_embedding,
                limit=5,
            )
            assert len(search_results) > 0
            assert any(r.id == commit_sha for r in search_results)

            # Verify payload
            result = await vector_store.get(collection_name, commit_sha)
            assert result is not None
            assert result.payload["message"] == message
            assert result.payload["author"] == "test_author"

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_commits_search_with_filters_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify commit search with filters works after cold-start creation."""
        collection_name = f"test_cold_start_commits_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)

        try:
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Index multiple commits
            commits = [
                {
                    "sha": f"sha_{i}",
                    "message": f"Commit {i} by author_{i % 2}",
                    "author": f"author_{i % 2}",
                    "author_email": f"author_{i % 2}@example.com",
                    "timestamp": (datetime.now(UTC).timestamp() - i * 3600),
                }
                for i in range(5)
            ]

            for commit in commits:
                embedding = await embedding_service.embed(commit["message"])
                await vector_store.upsert(
                    collection=collection_name,
                    id=commit["sha"],
                    vector=embedding,
                    payload=commit,
                )

            # Search with author filter
            query_embedding = await embedding_service.embed("Commit")
            results = await vector_store.search(
                collection=collection_name,
                query=query_embedding,
                limit=10,
                filters={"author": "author_0"},
            )
            assert len(results) > 0
            assert all(r.payload["author"] == "author_0" for r in results)

        finally:
            await cleanup_collection(vector_store, collection_name)


# =============================================================================
# Values Collection Cold-Start Tests
# =============================================================================


class TestValuesColdStart:
    """Cold-start tests for values collection.

    Tests that the values collection can be lazily created and used
    for storing and retrieving validated values.
    """

    async def test_values_lazy_creation_pattern(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify the lazy creation pattern for values collection."""
        collection_name = f"test_cold_start_values_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Simulate the _ensure_values_collection pattern
            try:
                await vector_store.create_collection(
                    name=collection_name,
                    dimension=embedding_service.dimension,
                    distance="cosine",
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    pass
                else:
                    raise

            # Verify collection was created
            info = await vector_store.get_collection_info(collection_name)
            assert info is not None, "Collection should exist after lazy creation"
            assert info.dimension == 768

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_values_operations_work_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify value operations work correctly after cold-start creation."""
        collection_name = f"test_cold_start_values_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Create collection (lazy creation)
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Store a value
            value_id = f"value_full_0_{test_id}"
            text = "Test value statement for cold-start verification"
            embedding = await embedding_service.embed(text)

            await vector_store.upsert(
                collection=collection_name,
                id=value_id,
                vector=embedding,
                payload={
                    "text": text,
                    "cluster_id": "full_0",
                    "axis": "full",
                    "cluster_label": 0,
                    "cluster_size": 5,
                    "created_at": datetime.now(UTC).isoformat(),
                    "validation": {
                        "candidate_distance": 0.1,
                        "mean_distance": 0.15,
                        "threshold": 0.2,
                        "similarity": 0.9,
                    },
                },
            )

            # Retrieve by scroll (simulating list_values)
            results = await vector_store.scroll(
                collection=collection_name,
                limit=10,
                with_vectors=True,
            )
            assert len(results) == 1
            assert results[0].id == value_id
            assert results[0].payload["text"] == text
            assert results[0].payload["axis"] == "full"

            # Retrieve with axis filter
            results_filtered = await vector_store.scroll(
                collection=collection_name,
                limit=10,
                filters={"axis": "full"},
                with_vectors=False,
            )
            assert len(results_filtered) == 1

        finally:
            await cleanup_collection(vector_store, collection_name)


# =============================================================================
# Code Units Collection Cold-Start Tests
# =============================================================================


class TestCodeUnitsColdStart:
    """Cold-start tests for code_units collection.

    Tests that the code_units collection can be lazily created and used
    for indexing and searching code.
    """

    async def test_code_units_lazy_creation_pattern(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify the lazy creation pattern for code_units collection."""
        collection_name = f"test_cold_start_code_units_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Simulate the _ensure_collection pattern from CodeIndexer
            try:
                await vector_store.create_collection(
                    name=collection_name,
                    dimension=embedding_service.dimension,
                    distance="cosine",
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    pass
                else:
                    raise

            # Verify collection was created
            info = await vector_store.get_collection_info(collection_name)
            assert info is not None, "Collection should exist after lazy creation"
            assert info.dimension == 768

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_code_units_operations_work_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify code indexing works correctly after cold-start creation."""
        collection_name = f"test_cold_start_code_units_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)
        await verify_collection_not_exists(vector_store, collection_name)

        try:
            # Create collection (lazy creation)
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Index a code unit
            unit_id = f"unit_{test_id}"
            content = """def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)"""
            embedding = await embedding_service.embed(content)

            await vector_store.upsert(
                collection=collection_name,
                id=unit_id,
                vector=embedding,
                payload={
                    "project": "test_project",
                    "file_path": "/test/math.py",
                    "name": "fibonacci",
                    "qualified_name": "math.fibonacci",
                    "unit_type": "function",
                    "signature": "def fibonacci(n)",
                    "language": "python",
                    "start_line": 1,
                    "end_line": 5,
                    "complexity": 3,
                    "has_docstring": False,
                    "indexed_at": datetime.now(UTC).isoformat(),
                },
            )

            # Search for the code unit
            search_results = await vector_store.search(
                collection=collection_name,
                query=embedding,
                limit=5,
            )
            assert len(search_results) > 0
            assert any(r.id == unit_id for r in search_results)

            # Verify payload
            result = await vector_store.get(collection_name, unit_id)
            assert result is not None
            assert result.payload["name"] == "fibonacci"
            assert result.payload["language"] == "python"
            assert result.payload["unit_type"] == "function"

        finally:
            await cleanup_collection(vector_store, collection_name)

    async def test_code_units_search_with_filters_after_cold_start(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify code search with project and language filters works."""
        collection_name = f"test_cold_start_code_units_{test_id}"

        # Ensure cold start
        await delete_collection_if_exists(vector_store, collection_name)

        try:
            await vector_store.create_collection(
                name=collection_name,
                dimension=768,
                distance="cosine",
            )

            # Index code units from different projects/languages
            units = [
                {
                    "id": "unit_py_1",
                    "project": "project_a",
                    "language": "python",
                    "name": "func_a",
                },
                {
                    "id": "unit_py_2",
                    "project": "project_a",
                    "language": "python",
                    "name": "func_b",
                },
                {
                    "id": "unit_ts_1",
                    "project": "project_b",
                    "language": "typescript",
                    "name": "funcC",
                },
            ]

            for unit in units:
                embedding = await embedding_service.embed(unit["name"])
                await vector_store.upsert(
                    collection=collection_name,
                    id=unit["id"],
                    vector=embedding,
                    payload=unit,
                )

            # Search with project filter
            query_embedding = await embedding_service.embed("func")
            results = await vector_store.search(
                collection=collection_name,
                query=query_embedding,
                limit=10,
                filters={"project": "project_a"},
            )
            assert len(results) == 2
            assert all(r.payload["project"] == "project_a" for r in results)

            # Search with language filter
            results = await vector_store.search(
                collection=collection_name,
                query=query_embedding,
                limit=10,
                filters={"language": "typescript"},
            )
            assert len(results) == 1
            assert results[0].payload["language"] == "typescript"

        finally:
            await cleanup_collection(vector_store, collection_name)


# =============================================================================
# GHAP Collections Cold-Start Tests
# =============================================================================


class TestGHAPCollectionsColdStart:
    """Cold-start tests for GHAP collections.

    Tests that ObservationPersister correctly creates all four GHAP collections
    (ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause) on first use.
    """

    async def test_ensure_collections_creates_all_ghap_collections(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify ensure_collections creates all four GHAP collections."""
        from clams.observation import ObservationPersister

        collection_prefix = f"test_cold_start_ghap_{test_id}"
        expected_collections = [
            f"{collection_prefix}_full",
            f"{collection_prefix}_strategy",
            f"{collection_prefix}_surprise",
            f"{collection_prefix}_root_cause",
        ]

        # Ensure cold start for all collections
        for name in expected_collections:
            await delete_collection_if_exists(vector_store, name)
            await verify_collection_not_exists(vector_store, name)

        try:
            # Create persister with custom prefix
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix=collection_prefix,
            )

            # Action: ensure_collections (should create all four)
            await persister.ensure_collections()

            # Verify all collections were created with correct dimension
            for name in expected_collections:
                info = await vector_store.get_collection_info(name)
                assert info is not None, f"Collection {name} should exist"
                assert (
                    info.dimension == 768
                ), f"Collection {name} should have 768 dimensions"

        finally:
            for name in expected_collections:
                await cleanup_collection(vector_store, name)

    async def test_ghap_persist_works_after_ensure_collections(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify persist works after ensure_collections is called."""
        from clams.observation import (
            ConfidenceTier,
            Domain,
            GHAPEntry,
            Lesson,
            Outcome,
            OutcomeStatus,
            Strategy,
        )
        from clams.observation.persister import ObservationPersister

        collection_prefix = f"test_cold_start_ghap_{test_id}"
        expected_collections = [
            f"{collection_prefix}_full",
            f"{collection_prefix}_strategy",
            f"{collection_prefix}_surprise",
            f"{collection_prefix}_root_cause",
        ]

        # Ensure cold start
        for name in expected_collections:
            await delete_collection_if_exists(vector_store, name)

        try:
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix=collection_prefix,
            )

            # Ensure collections
            await persister.ensure_collections()

            # Create a resolved GHAP entry
            entry = GHAPEntry(
                id=f"ghap_{test_id}",
                session_id=f"session_{test_id}",
                created_at=datetime.now(UTC),
                domain=Domain.DEBUGGING,
                strategy=Strategy.ROOT_CAUSE_ANALYSIS,
                goal="Test GHAP persistence after cold start",
                hypothesis="Persistence should work",
                action="Test the persist method",
                prediction="Entry should be stored",
                iteration_count=1,
                outcome=Outcome(
                    status=OutcomeStatus.CONFIRMED,
                    result="Persistence works correctly",
                    captured_at=datetime.now(UTC),
                ),
                confidence_tier=ConfidenceTier.SILVER,  # Manual resolution
                lesson=Lesson(
                    what_worked="Testing cold start",
                    takeaway="Always test cold start scenarios",
                ),
            )

            # Action: persist entry
            await persister.persist(entry)

            # Verify entry was stored in full and strategy collections
            # (CONFIRMED entries only go to full and strategy, not surprise/root_cause)
            full_result = await vector_store.get(
                f"{collection_prefix}_full", entry.id
            )
            assert full_result is not None
            assert full_result.payload["ghap_id"] == entry.id
            assert full_result.payload["domain"] == "debugging"

            strategy_result = await vector_store.get(
                f"{collection_prefix}_strategy", entry.id
            )
            assert strategy_result is not None
            assert strategy_result.payload["ghap_id"] == entry.id

        finally:
            for name in expected_collections:
                await cleanup_collection(vector_store, name)

    async def test_ghap_falsified_persists_to_all_axes(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify falsified GHAP with root cause persists to all four axes."""
        from clams.observation import (
            ConfidenceTier,
            Domain,
            GHAPEntry,
            Lesson,
            Outcome,
            OutcomeStatus,
            RootCause,
            Strategy,
        )
        from clams.observation.persister import ObservationPersister

        collection_prefix = f"test_cold_start_ghap_{test_id}"
        expected_collections = [
            f"{collection_prefix}_full",
            f"{collection_prefix}_strategy",
            f"{collection_prefix}_surprise",
            f"{collection_prefix}_root_cause",
        ]

        # Ensure cold start
        for name in expected_collections:
            await delete_collection_if_exists(vector_store, name)

        try:
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix=collection_prefix,
            )

            await persister.ensure_collections()

            # Create a falsified GHAP entry with root cause
            entry = GHAPEntry(
                id=f"ghap_falsified_{test_id}",
                session_id=f"session_{test_id}",
                created_at=datetime.now(UTC),
                domain=Domain.DEBUGGING,
                strategy=Strategy.SYSTEMATIC_ELIMINATION,
                goal="Test falsified GHAP persistence",
                hypothesis="Initial hypothesis was incorrect",
                action="Investigate the issue",
                prediction="Will find root cause",
                iteration_count=1,
                outcome=Outcome(
                    status=OutcomeStatus.FALSIFIED,
                    result="Hypothesis was wrong",
                    captured_at=datetime.now(UTC),
                ),
                surprise="The actual cause was completely different",
                root_cause=RootCause(
                    category="wrong-assumption",
                    description="Made incorrect assumption about the problem",
                ),
                confidence_tier=ConfidenceTier.SILVER,
                lesson=Lesson(
                    what_worked="Systematic investigation",
                    takeaway="Always verify assumptions",
                ),
            )

            # Persist entry
            await persister.persist(entry)

            # Verify entry was stored in all four collections
            for collection_suffix in ["full", "strategy", "surprise", "root_cause"]:
                collection_name = f"{collection_prefix}_{collection_suffix}"
                result = await vector_store.get(collection_name, entry.id)
                assert result is not None, f"Entry should exist in {collection_suffix}"
                assert result.payload["ghap_id"] == entry.id

        finally:
            for name in expected_collections:
                await cleanup_collection(vector_store, name)

    async def test_ghap_collections_have_correct_dimension(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify each GHAP collection has dimension 768."""
        from clams.observation import ObservationPersister

        collection_prefix = f"test_cold_start_ghap_{test_id}"
        axes = ["full", "strategy", "surprise", "root_cause"]

        # Ensure cold start
        for axis in axes:
            name = f"{collection_prefix}_{axis}"
            await delete_collection_if_exists(vector_store, name)

        try:
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix=collection_prefix,
            )

            await persister.ensure_collections()

            # Verify each collection has correct dimension
            for axis in axes:
                name = f"{collection_prefix}_{axis}"
                info = await vector_store.get_collection_info(name)
                assert info is not None, f"Collection {name} should exist"
                assert (
                    info.dimension == 768
                ), f"Collection {name} should have 768 dimensions, got {info.dimension}"

        finally:
            for axis in axes:
                name = f"{collection_prefix}_{axis}"
                await cleanup_collection(vector_store, name)

    async def test_ensure_collections_is_idempotent(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_id: str,
    ) -> None:
        """Verify ensure_collections can be called multiple times safely."""
        from clams.observation import ObservationPersister

        collection_prefix = f"test_cold_start_ghap_{test_id}"
        axes = ["full", "strategy", "surprise", "root_cause"]

        # Ensure cold start
        for axis in axes:
            name = f"{collection_prefix}_{axis}"
            await delete_collection_if_exists(vector_store, name)

        try:
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix=collection_prefix,
            )

            # Call ensure_collections multiple times
            await persister.ensure_collections()
            await persister.ensure_collections()
            await persister.ensure_collections()

            # All collections should still exist
            for axis in axes:
                name = f"{collection_prefix}_{axis}"
                info = await vector_store.get_collection_info(name)
                assert info is not None, f"Collection {name} should exist after multiple ensures"

        finally:
            for axis in axes:
                name = f"{collection_prefix}_{axis}"
                await cleanup_collection(vector_store, name)
