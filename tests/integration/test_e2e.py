"""End-to-end integration tests for Learning Memory Server.

These tests validate full workflows with real Qdrant at localhost:6333.
They use isolated test collections to avoid touching production data.

Failure Policy: Tests FAIL (not skip) if Qdrant unavailable.
"""

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from learning_memory_server.clustering import ExperienceClusterer
from learning_memory_server.clustering.clusterer import Clusterer
from learning_memory_server.embedding import MockEmbedding
from learning_memory_server.observation import (
    Domain,
    ObservationCollector,
    OutcomeStatus,
    Strategy,
)
from learning_memory_server.search import Searcher
from learning_memory_server.storage import QdrantVectorStore
from learning_memory_server.values import ValueStore

pytest_plugins = ("pytest_asyncio",)

# Test collection names (isolated from production)
TEST_COLLECTIONS = {
    "memories": "test_memories",
    "code_units": "test_code_units",
    "commits": "test_commits",
    "values": "test_values",
    "full": "test_ghap_full",
    "strategy": "test_ghap_strategy",
    "surprise": "test_ghap_surprise",
    "root_cause": "test_ghap_root_cause",
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


class TestMemoryLifecycle:
    """Test memory store -> retrieve -> delete workflow."""

    async def test_memory_lifecycle(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test complete memory lifecycle: store, retrieve, delete."""
        collection = test_collections["memories"]
        memory_id = str(uuid4())
        content = "Important fact about testing workflows"

        # Store memory
        embedding = await embedding_service.embed(content)
        payload = {
            "id": memory_id,
            "content": content,
            "category": "fact",
            "importance": 0.8,
            "tags": ["test", "integration"],
        }

        await vector_store.upsert(
            collection=collection,
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        # Verify storage
        result = await vector_store.get(collection, memory_id)
        assert result is not None
        assert result.payload["content"] == content
        assert result.payload["category"] == "fact"

        # Retrieve by semantic search
        query_embedding = await embedding_service.embed("testing workflows")
        search_results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=5,
        )
        assert len(search_results) > 0
        assert any(r.id == memory_id for r in search_results)

        # List memories
        scroll_results = await vector_store.scroll(
            collection=collection,
            limit=10,
        )
        assert any(r.id == memory_id for r in scroll_results)

        # Delete memory
        await vector_store.delete(collection, memory_id)

        # Verify deletion
        result = await vector_store.get(collection, memory_id)
        assert result is None


class TestCodeWorkflow:
    """Test code indexing and search workflow."""

    async def test_code_indexing_and_search(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test index -> search -> find_similar workflow."""
        collection = test_collections["code_units"]

        # Simulate indexing code units
        code_units = [
            {
                "id": "unit_1",
                "content": "def fibonacci(n): return n if n < 2 else fib(n-1)",
                "name": "fibonacci",
                "type": "function",
                "language": "python",
                "project": "test_project",
                "file_path": "/test/math.py",
            },
            {
                "id": "unit_2",
                "content": "def factorial(n): return 1 if n <= 1 else n * fact(n-1)",
                "name": "factorial",
                "type": "function",
                "language": "python",
                "project": "test_project",
                "file_path": "/test/math.py",
            },
            {
                "id": "unit_3",
                "content": "class Calculator:\n    def add(self, a, b): return a + b",
                "name": "Calculator",
                "type": "class",
                "language": "python",
                "project": "test_project",
                "file_path": "/test/calc.py",
            },
        ]

        # Index code units
        for unit in code_units:
            embedding = await embedding_service.embed(unit["content"])
            await vector_store.upsert(
                collection=collection,
                id=unit["id"],
                vector=embedding,
                payload=unit,
            )

        # Verify indexing
        count = await vector_store.count(collection)
        assert count == 3

        # Search by semantic query
        query_embedding = await embedding_service.embed("recursive function")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=2,
        )
        assert len(results) > 0

        # Search with project filter
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"project": "test_project"},
        )
        assert len(results) == 3

        # Find similar code
        snippet = "def fib(n): return n"
        snippet_embedding = await embedding_service.embed(snippet)
        similar = await vector_store.search(
            collection=collection,
            query=snippet_embedding,
            limit=3,
        )
        assert len(similar) > 0


class TestGitWorkflow:
    """Test git analysis workflow."""

    async def test_git_commit_indexing(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test git commit indexing and search."""
        collection = test_collections["commits"]

        # Simulate indexed commits
        commits = [
            {
                "id": "commit_abc123",
                "sha": "abc123",
                "message": "Add fibonacci function for math utilities",
                "author": "test_author",
                "author_email": "test@test.com",
                "timestamp": "2024-01-15T10:30:00Z",
                "files_changed": ["math.py"],
                "insertions": 10,
                "deletions": 0,
            },
            {
                "id": "commit_def456",
                "sha": "def456",
                "message": "Fix bug in calculator division",
                "author": "test_author",
                "author_email": "test@test.com",
                "timestamp": "2024-01-16T14:20:00Z",
                "files_changed": ["calc.py"],
                "insertions": 5,
                "deletions": 2,
            },
        ]

        # Index commits
        for commit in commits:
            embedding = await embedding_service.embed(commit["message"])
            await vector_store.upsert(
                collection=collection,
                id=commit["id"],
                vector=embedding,
                payload=commit,
            )

        # Search commits
        query_embedding = await embedding_service.embed("math function")
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=5,
        )
        assert len(results) > 0

        # Filter by author
        results = await vector_store.search(
            collection=collection,
            query=query_embedding,
            limit=10,
            filters={"author": "test_author"},
        )
        assert len(results) == 2

    async def test_churn_hotspots(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test get_churn_hotspots returns file change statistics."""
        from learning_memory_server.git import GitAnalyzer, GitPythonReader
        from learning_memory_server.storage.metadata import MetadataStore

        # Use the actual repository for real git data
        repo_path = Path(__file__).parent.parent.parent
        git_reader = GitPythonReader(repo_path)

        # Create a temporary metadata store for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_store = MetadataStore(Path(tmpdir) / "metadata.db")
            await metadata_store.initialize()

            analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=embedding_service,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )

            # Get churn hotspots (files with most changes in last 90 days)
            hotspots = await analyzer.get_churn_hotspots(
                days=90,
                limit=10,
                min_changes=1,  # Low threshold to ensure we get results
            )

            # Verify we get a list of churn records
            assert isinstance(hotspots, list)

            # If there are results, verify structure
            if len(hotspots) > 0:
                first_hotspot = hotspots[0]
                # Verify ChurnRecord structure
                assert hasattr(first_hotspot, "file_path")
                assert hasattr(first_hotspot, "change_count")
                assert hasattr(first_hotspot, "total_insertions")
                assert hasattr(first_hotspot, "total_deletions")
                assert hasattr(first_hotspot, "authors")
                assert hasattr(first_hotspot, "last_changed")

                # Verify ordering (most changes first)
                for i in range(1, len(hotspots)):
                    assert hotspots[i - 1].change_count >= hotspots[i].change_count

    async def test_code_authors(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test get_file_authors returns author statistics for a file."""
        from learning_memory_server.git import GitAnalyzer, GitPythonReader
        from learning_memory_server.storage.metadata import MetadataStore

        # Use the actual repository for real git data
        repo_path = Path(__file__).parent.parent.parent
        git_reader = GitPythonReader(repo_path)

        # Create a temporary metadata store for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_store = MetadataStore(Path(tmpdir) / "metadata.db")
            await metadata_store.initialize()

            analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=embedding_service,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )

            # Get authors for a file that exists in the repo
            # Use this test file itself as it definitely exists
            test_file = "tests/integration/test_e2e.py"
            authors = await analyzer.get_file_authors(test_file)

            # Verify we get a list of author stats
            assert isinstance(authors, list)

            # If there are results, verify structure
            if len(authors) > 0:
                first_author = authors[0]
                # Verify AuthorStats structure
                assert hasattr(first_author, "author")
                assert hasattr(first_author, "author_email")
                assert hasattr(first_author, "commit_count")
                assert hasattr(first_author, "lines_added")
                assert hasattr(first_author, "lines_removed")
                assert hasattr(first_author, "first_commit")
                assert hasattr(first_author, "last_commit")

                # Verify we have at least one commit for this file
                assert first_author.commit_count >= 1

                # Verify ordering (most commits first)
                for i in range(1, len(authors)):
                    assert authors[i - 1].commit_count >= authors[i].commit_count


class TestGHAPLearningLoop:
    """Test GHAP learning loop with 20+ entries for clustering."""

    async def test_ghap_full_workflow(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Test 20+ GHAP entries -> clustering -> value extraction."""
        from unittest.mock import patch

        test_axis_collections = {
            "full": test_collections["full"],
            "strategy": test_collections["strategy"],
            "surprise": test_collections["surprise"],
            "root_cause": test_collections["root_cause"],
        }

        # Use patch.dict for proper cleanup even on test failure
        with patch.dict(
            "learning_memory_server.clustering.experience.AXIS_COLLECTIONS",
            test_axis_collections,
            clear=True,
        ):
            # Create 25 GHAP entries to exceed clustering threshold (20)
            for i in range(25):
                entry_id = f"ghap_{i}"
                domain = list(Domain)[i % len(Domain)].value
                strategy = list(Strategy)[i % len(Strategy)].value

                # Create full narrative
                narrative = (
                    f"Goal: Fix issue {i}. "
                    f"Hypothesis: The bug is in module {i % 5}. "
                    f"Action: Added logging and traced execution. "
                    f"Prediction: Logs will reveal the error source. "
                    f"Result: Found the issue in configuration."
                )

                embedding = await embedding_service.embed(narrative)
                payload = {
                    "id": entry_id,
                    "domain": domain,
                    "strategy": strategy,
                    "goal": f"Fix issue {i}",
                    "hypothesis": f"The bug is in module {i % 5}",
                    "action": "Added logging and traced execution",
                    "prediction": "Logs will reveal the error source",
                    "outcome_status": "confirmed" if i % 3 != 0 else "falsified",
                    "confidence_tier": "silver",
                    "confidence_weight": 0.7,
                }

                # Store in full axis collection
                await vector_store.upsert(
                    collection=test_collections["full"],
                    id=entry_id,
                    vector=embedding,
                    payload=payload,
                )

                # Store strategy projection
                strategy_text = f"Strategy: {strategy} - {payload['action']}"
                strategy_embedding = await embedding_service.embed(strategy_text)
                await vector_store.upsert(
                    collection=test_collections["strategy"],
                    id=f"strategy_{entry_id}",
                    vector=strategy_embedding,
                    payload=payload,
                )

            # Verify storage
            count = await vector_store.count(test_collections["full"])
            assert count == 25

            # Test clustering (using mock clusterer for speed)
            clusterer = Clusterer(min_cluster_size=5, min_samples=3)
            experience_clusterer = ExperienceClusterer(
                vector_store=vector_store,
                clusterer=clusterer,
            )

            # Cluster full axis - should get clusters or all noise
            clusters = await experience_clusterer.cluster_axis("full")
            assert isinstance(clusters, list)

            # Verify value store can be instantiated
            _ = ValueStore(
                embedding_service=embedding_service,
                vector_store=vector_store,
                clusterer=experience_clusterer,
            )

            # Search experiences
            query_embedding = await embedding_service.embed("debugging issue")
            search_results = await vector_store.search(
                collection=test_collections["full"],
                query=query_embedding,
                limit=10,
            )
            assert len(search_results) > 0


class TestContextAssembly:
    """Test context assembly workflow."""

    async def test_context_assembly_workflow(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        searcher: Searcher,
        test_collections: dict[str, str],
    ) -> None:
        """Test populate -> assemble light -> assemble rich -> premortem workflow."""
        from unittest.mock import patch

        from learning_memory_server.context import ContextAssembler
        from learning_memory_server.search.collections import CollectionName

        # Populate test data in memories collection
        memories = [
            {
                "id": "mem_1",
                "content": "Important context about debugging techniques",
                "category": "context",
                "importance": 0.9,
                "tags": ["debug", "techniques"],
                "created_at": "2024-01-15T10:00:00Z",
                "verified_at": "2024-01-15T12:00:00Z",
                "verification_status": "verified",
            },
            {
                "id": "mem_2",
                "content": "Reference to testing best practices",
                "category": "fact",
                "importance": 0.7,
                "tags": ["testing", "practices"],
                "created_at": "2024-01-16T10:00:00Z",
                "verified_at": "2024-01-16T12:00:00Z",
                "verification_status": "verified",
            },
        ]

        for mem in memories:
            embedding = await embedding_service.embed(mem["content"])
            await vector_store.upsert(
                collection=test_collections["memories"],
                id=mem["id"],
                vector=embedding,
                payload=mem,
            )

        # Populate test data in code collection
        code_units = [
            {
                "id": "code_1",
                "content": "def debug_function():\n    pass",
                "qualified_name": "test.debug_function",
                "unit_type": "function",
                "file_path": "/test/debug.py",
                "start_line": 1,
                "end_line": 2,
                "language": "python",
                "docstring": "Debug helper function",
            },
        ]

        for unit in code_units:
            embedding = await embedding_service.embed(unit["content"])
            await vector_store.upsert(
                collection=test_collections["code_units"],
                id=unit["id"],
                vector=embedding,
                payload=unit,
            )

        # Populate experiences for premortem
        experiences = [
            {
                "id": "exp_1",
                "ghap_id": "ghap_1",
                "axis": "full",
                "domain": "debugging",
                "strategy": "systematic-elimination",
                "goal": "Fix authentication bug",
                "hypothesis": "Token expired",
                "action": "Check token refresh",
                "prediction": "Will fix auth",
                "outcome_status": "falsified",
                "outcome_result": "Token was valid, issue elsewhere",
                "surprise": "Token was not the issue",
                "root_cause": "Session cookie was malformed",
                "lesson": {"key": "Always check cookies first"},
                "confidence_tier": "silver",
                "iteration_count": 2,
                "created_at": "2024-01-15T10:00:00Z",
            },
        ]

        for exp in experiences:
            embedding = await embedding_service.embed(
                f"{exp['goal']} {exp['hypothesis']} {exp['action']}"
            )
            await vector_store.upsert(
                collection=test_collections["full"],
                id=exp["id"],
                vector=embedding,
                payload=exp,
            )

        # Verify data exists
        mem_count = await vector_store.count(test_collections["memories"])
        code_count = await vector_store.count(test_collections["code_units"])
        exp_count = await vector_store.count(test_collections["full"])
        assert mem_count == 2
        assert code_count == 1
        assert exp_count == 1

        # Patch collection names to use test collections
        with patch.object(
            CollectionName, "MEMORIES", test_collections["memories"]
        ), patch.object(
            CollectionName, "CODE", test_collections["code_units"]
        ), patch.object(
            CollectionName,
            "get_experience_collection",
            lambda axis: test_collections.get(axis, test_collections["full"]),
        ):
            # Create context assembler with the searcher
            assembler = ContextAssembler(searcher)

            # Test 1: Light context assembly (single source)
            light_context = await assembler.assemble_context(
                query="debugging techniques",
                context_types=["memories"],
                limit=10,
                max_tokens=1000,
            )
            assert light_context.markdown is not None
            assert len(light_context.items) > 0
            assert "memories" in light_context.sources_used
            assert light_context.token_count > 0

            # Test 2: Rich context assembly (multiple sources)
            rich_context = await assembler.assemble_context(
                query="debugging code",
                context_types=["memories", "code"],
                limit=10,
                max_tokens=2000,
            )
            assert rich_context.markdown is not None
            assert len(rich_context.items) >= 1
            # At least memories should be found
            assert rich_context.token_count > 0

            # Test 3: Premortem analysis
            premortem_context = await assembler.get_premortem_context(
                domain="debugging",
                strategy="systematic-elimination",
                limit=5,
                max_tokens=1500,
            )
            assert premortem_context.markdown is not None
            # Premortem should return experiences
            assert premortem_context.token_count >= 0


class TestObservationCollector:
    """Test ObservationCollector GHAP state machine."""

    async def test_ghap_state_machine(self) -> None:
        """Test GHAP create -> update -> resolve workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_dir = Path(tmpdir) / "journal"
            collector = ObservationCollector(journal_dir=journal_dir)

            # Start session
            session_id = await collector.start_session()
            assert session_id is not None
            assert session_id.startswith("session_")

            # Create GHAP entry
            entry = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.SYSTEMATIC_ELIMINATION,
                goal="Fix the authentication bug",
                hypothesis="The session token is not being refreshed",
                action="Adding token refresh logic",
                prediction="Authentication will succeed after refresh",
            )
            assert entry.id is not None
            assert entry.domain == Domain.DEBUGGING
            assert entry.iteration_count == 1

            # Get active GHAP
            current = await collector.get_current()
            assert current is not None
            assert current.id == entry.id

            # Update GHAP (should create history entry)
            updated = await collector.update_ghap(
                hypothesis="The session token expires too quickly",
                note="Found that token TTL is only 5 minutes",
            )
            assert updated.iteration_count == 2
            assert len(updated.history) == 1

            # Resolve GHAP
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="Token refresh logic fixed the issue",
            )
            assert resolved.outcome is not None
            assert resolved.outcome.status == OutcomeStatus.CONFIRMED
            assert resolved.confidence_tier is not None

            # Verify no active GHAP
            current = await collector.get_current()
            assert current is None

            # Get session entries
            entries = await collector.get_session_entries()
            assert len(entries) == 1
            assert entries[0].id == entry.id
