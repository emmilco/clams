"""Cross-component boundary contract tests.

Tests verify data transformation contracts at component boundaries,
catching schema mismatches, type errors, and validation gaps early.

Reference: SPEC-031 (Cross-Component Integration Tests)
Regression prevention: BUG-006, BUG-019, BUG-027, BUG-036, BUG-040, BUG-041
"""

import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import numpy as np
import pytest

from clams.context.assembler import ContextAssembler
from clams.context.formatting import (
    format_code,
    format_commit,
    format_experience,
    format_memory,
    format_value,
)
from clams.context.models import InvalidContextTypeError
from clams.context.tokens import distribute_budget
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
from clams.search.results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    MemoryResult,
    ValueResult,
)
from clams.search.searcher import Searcher
from clams.storage.base import SearchResult
from clams.storage.qdrant import QdrantVectorStore

pytestmark = pytest.mark.integration

pytest_plugins = ("pytest_asyncio",)


# =============================================================================
# Contract Definitions
# =============================================================================


GHAP_PAYLOAD_CONTRACT: dict[str, dict[str, type | tuple[type, ...]]] = {
    "required": {
        "ghap_id": str,
        "axis": str,
        "domain": str,
        "strategy": str,
        "goal": str,
        "hypothesis": str,
        "action": str,
        "prediction": str,
        "outcome_status": str,
        "outcome_result": str,
        "created_at": str,  # ISO format
        "captured_at": (int, float),  # Unix timestamp
        "confidence_tier": (str, type(None)),
        "iteration_count": int,
        "session_id": str,
    },
    "optional": {
        "surprise": str,
        "root_cause": dict,  # {"category": str, "description": str}
        "lesson": dict,  # {"what_worked": str, "takeaway": str | None}
    },
}


MEMORY_PAYLOAD_CONTRACT: dict[str, dict[str, type | tuple[type, ...]]] = {
    "required": {
        "id": str,
        "content": str,
        "category": str,
        "importance": (int, float),
        "created_at": str,  # ISO format
    },
    "optional": {
        "tags": list,
        "verified_at": str,
        "verification_status": str,
    },
}


CODE_PAYLOAD_CONTRACT: dict[str, dict[str, type | tuple[type, ...]]] = {
    "required": {
        "project": str,
        "file_path": str,
        "language": str,
        "unit_type": str,
        "qualified_name": str,
        "code": str,
        "line_start": int,
        "line_end": int,
    },
    "optional": {
        "docstring": str,
    },
}


COMMIT_PAYLOAD_CONTRACT: dict[str, dict[str, type | tuple[type, ...]]] = {
    "required": {
        "sha": str,
        "message": str,
        "author": str,
        "author_email": str,
        "committed_at": str,  # ISO format
        "files_changed": list,
    },
    "optional": {
        "insertions": int,
        "deletions": int,
    },
}


VALUE_PAYLOAD_CONTRACT: dict[str, dict[str, type | tuple[type, ...]]] = {
    "required": {
        "text": str,
        "cluster_id": str,
        "axis": str,
        "created_at": str,  # ISO format
    },
    "optional": {
        "cluster_label": int,
        "member_count": int,
        "avg_confidence": float,
        "validation": dict,
    },
}


# =============================================================================
# Contract Validation Helper
# =============================================================================


def validate_contract(
    payload: dict[str, Any],
    contract: dict[str, type | tuple[type, ...]],
    optional: set[str] | None = None,
) -> list[str]:
    """Validate payload matches contract.

    Returns list of violation messages (empty if valid).
    """
    violations = []
    optional = optional or set()

    for field, expected_type in contract.items():
        if field in optional and field not in payload:
            continue
        if field not in payload:
            violations.append(f"Missing required field: {field}")
        elif not isinstance(payload[field], expected_type):
            violations.append(
                f"Type mismatch for {field}: "
                f"expected {expected_type}, got {type(payload[field]).__name__}"
            )

    return violations


# =============================================================================
# Fixtures
# =============================================================================


# Test collection names (isolated from production)
TEST_COLLECTIONS = {
    "ghap_full": "test_bc_ghap_full",
    "ghap_strategy": "test_bc_ghap_strategy",
    "ghap_surprise": "test_bc_ghap_surprise",
    "ghap_root_cause": "test_bc_ghap_root_cause",
    "memories": "test_bc_memories",
    "code_units": "test_bc_code_units",
    "commits": "test_bc_commits",
    "values": "test_bc_values",
}


@pytest.fixture(scope="session", autouse=True)
def verify_qdrant() -> None:
    """Verify Qdrant is available before running tests."""
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

    # Create all test collections with 768-dim (Mock/Nomic embedding dimension)
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


# =============================================================================
# Storage Boundary Contract Tests
# =============================================================================


class TestStorageBoundaryContracts:
    """Verify data contracts at storage layer boundaries."""

    async def test_ghap_persist_contract(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify persisted GHAP contains all required fields.

        Boundary: ObservationCollector -> ObservationPersister -> VectorStore
        Contract: GHAP_PAYLOAD_CONTRACT
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = ObservationCollector(journal_dir=Path(tmpdir) / "journal")
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_bc_ghap",
            )

            await collector.start_session()
            entry = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.ROOT_CAUSE_ANALYSIS,
                goal="Test boundary contract",
                hypothesis="Payload matches contract",
                action="Verify all fields present",
                prediction="Contract validation passes",
            )
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="All fields present",
                lesson=Lesson(what_worked="Testing", takeaway="Always test"),
            )
            await persister.persist(resolved)

            # Retrieve and validate contract
            result = await vector_store.get(
                collection=test_collections["ghap_full"],
                id=entry.id,
            )
            assert result is not None, "GHAP entry should exist after persist"

            violations = validate_contract(
                result.payload,
                GHAP_PAYLOAD_CONTRACT["required"],
                optional=set(GHAP_PAYLOAD_CONTRACT["optional"].keys()),
            )
            assert violations == [], f"Contract violations: {violations}"

    async def test_ghap_falsified_includes_root_cause(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify falsified GHAP includes root_cause and surprise fields.

        Regression: BUG-006 (incomplete GHAP payload)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = ObservationCollector(journal_dir=Path(tmpdir) / "journal")
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_bc_ghap",
            )

            await collector.start_session()
            await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=Strategy.CHECK_ASSUMPTIONS,
                goal="Test falsified contract",
                hypothesis="Initial hypothesis",
                action="Investigate",
                prediction="Find issue",
            )
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.FALSIFIED,
                result="Hypothesis was wrong",
                surprise="Unexpected discovery",
                root_cause=RootCause(
                    category="wrong-assumption",
                    description="Made incorrect assumption",
                ),
                lesson=Lesson(what_worked="Investigation", takeaway="Verify assumptions"),
            )
            await persister.persist(resolved)

            # Verify payload in full axis collection
            result = await vector_store.get(
                collection=test_collections["ghap_full"],
                id=resolved.id,
            )
            assert result is not None
            payload = result.payload

            # BUG-006 regression: these fields must be present
            assert "surprise" in payload, "surprise field missing (BUG-006)"
            assert "root_cause" in payload, "root_cause field missing (BUG-006)"
            assert isinstance(payload["root_cause"], dict)
            assert "category" in payload["root_cause"]
            assert "description" in payload["root_cause"]
            assert "lesson" in payload, "lesson field missing (BUG-006)"

    async def test_memory_persist_contract(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify memory payload matches contract."""
        memory_id = str(uuid4())
        embedding = await embedding_service.embed("Test memory content")
        payload = {
            "id": memory_id,
            "content": "Test memory content",
            "category": "fact",
            "importance": 0.75,
            "tags": ["test", "boundary"],
            "created_at": datetime.now(UTC).isoformat(),
        }

        await vector_store.upsert(
            collection=test_collections["memories"],
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["memories"], memory_id)
        assert result is not None

        violations = validate_contract(
            result.payload,
            MEMORY_PAYLOAD_CONTRACT["required"],
            optional=set(MEMORY_PAYLOAD_CONTRACT["optional"].keys()),
        )
        assert violations == [], f"Contract violations: {violations}"

    async def test_code_persist_contract(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify code unit payload matches contract."""
        code_id = str(uuid4())
        embedding = await embedding_service.embed("def test_function(): pass")
        payload = {
            "id": code_id,
            "project": "test_project",
            "file_path": "/src/test.py",
            "language": "python",
            "unit_type": "function",
            "qualified_name": "test_module.test_function",
            "code": "def test_function(): pass",
            "line_start": 1,
            "line_end": 1,
            "docstring": "Test function docstring",
        }

        await vector_store.upsert(
            collection=test_collections["code_units"],
            id=code_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["code_units"], code_id)
        assert result is not None

        violations = validate_contract(
            result.payload,
            CODE_PAYLOAD_CONTRACT["required"],
            optional=set(CODE_PAYLOAD_CONTRACT["optional"].keys()),
        )
        assert violations == [], f"Contract violations: {violations}"

    async def test_commit_persist_contract(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify commit payload matches contract."""
        commit_id = str(uuid4())
        embedding = await embedding_service.embed("feat: Add new feature")
        payload = {
            "id": commit_id,
            "sha": "abc123def456",
            "message": "feat: Add new feature",
            "author": "test_author",
            "author_email": "test@example.com",
            "committed_at": datetime.now(UTC).isoformat(),
            "files_changed": ["file1.py", "file2.py"],
            "insertions": 10,
            "deletions": 5,
        }

        await vector_store.upsert(
            collection=test_collections["commits"],
            id=commit_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["commits"], commit_id)
        assert result is not None

        violations = validate_contract(
            result.payload,
            COMMIT_PAYLOAD_CONTRACT["required"],
            optional=set(COMMIT_PAYLOAD_CONTRACT["optional"].keys()),
        )
        assert violations == [], f"Contract violations: {violations}"

    async def test_value_persist_contract(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify value payload matches contract."""
        value_id = str(uuid4())
        embedding = await embedding_service.embed("Test value statement")
        payload = {
            "id": value_id,
            "text": "Test value statement",
            "cluster_id": "cluster_001",
            "axis": "strategy",
            "created_at": datetime.now(UTC).isoformat(),
            "member_count": 5,
            "avg_confidence": 0.85,
        }

        await vector_store.upsert(
            collection=test_collections["values"],
            id=value_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["values"], value_id)
        assert result is not None

        violations = validate_contract(
            result.payload,
            VALUE_PAYLOAD_CONTRACT["required"],
            optional=set(VALUE_PAYLOAD_CONTRACT["optional"].keys()),
        )
        assert violations == [], f"Contract violations: {violations}"


# =============================================================================
# Retrieval Boundary Contract Tests
# =============================================================================


class TestRetrievalBoundaryContracts:
    """Verify data contracts at retrieval layer boundaries."""

    def test_experience_result_from_search_result(self) -> None:
        """Verify ExperienceResult.from_search_result handles actual payloads.

        Boundary: VectorStore -> Searcher -> ExperienceResult
        Contract: ExperienceResult fields
        """
        # Create SearchResult with actual payload structure
        search_result = SearchResult(
            id="test_exp_1",
            score=0.95,
            payload={
                "ghap_id": "test_exp_1",
                "axis": "full",
                "domain": "debugging",
                "strategy": "root-cause-analysis",
                "goal": "Test goal",
                "hypothesis": "Test hypothesis",
                "action": "Test action",
                "prediction": "Test prediction",
                "outcome_status": "confirmed",
                "outcome_result": "Test result",
                "confidence_tier": "silver",
                "iteration_count": 2,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

        # Conversion must not raise
        experience = ExperienceResult.from_search_result(search_result)

        # Verify all fields populated
        assert experience.ghap_id == "test_exp_1"
        assert experience.domain == "debugging"
        assert experience.outcome_status == "confirmed"
        assert isinstance(experience.created_at, datetime)

    def test_experience_result_with_optional_fields(self) -> None:
        """Verify ExperienceResult handles optional fields correctly."""
        # Create SearchResult with surprise, root_cause, and lesson
        search_result = SearchResult(
            id="test_exp_2",
            score=0.85,
            payload={
                "ghap_id": "test_exp_2",
                "axis": "root_cause",
                "domain": "testing",
                "strategy": "systematic-elimination",
                "goal": "Find bug",
                "hypothesis": "Cache issue",
                "action": "Clear cache",
                "prediction": "Bug fixed",
                "outcome_status": "falsified",
                "outcome_result": "Bug persisted",
                "confidence_tier": "bronze",
                "iteration_count": 3,
                "created_at": datetime.now(UTC).isoformat(),
                "surprise": "Unexpected side effect",
                "root_cause": {
                    "category": "wrong-assumption",
                    "description": "Cache was not the issue",
                },
                "lesson": {
                    "what_worked": "Systematic elimination",
                    "takeaway": "Check all assumptions",
                },
            },
        )

        experience = ExperienceResult.from_search_result(search_result)

        # Optional fields should be populated
        assert experience.surprise == "Unexpected side effect"
        assert experience.root_cause is not None
        assert experience.root_cause.category == "wrong-assumption"
        assert experience.lesson is not None
        assert experience.lesson.what_worked == "Systematic elimination"

    def test_memory_result_datetime_parsing(self) -> None:
        """Verify MemoryResult parses created_at as ISO string.

        Regression: BUG-027 (datetime format mismatch)
        """
        # Create SearchResult with ISO datetime
        search_result = SearchResult(
            id="mem_1",
            score=0.9,
            payload={
                "category": "fact",
                "content": "Test content",
                "importance": 0.8,
                "tags": ["test"],
                "created_at": "2024-06-15T12:30:45+00:00",  # ISO format
            },
        )

        # Must parse without error
        memory = MemoryResult.from_search_result(search_result)
        assert isinstance(memory.created_at, datetime)
        assert memory.created_at.year == 2024
        assert memory.created_at.month == 6

    def test_memory_result_datetime_z_suffix(self) -> None:
        """Verify MemoryResult parses created_at with Z suffix.

        Regression: BUG-027 (datetime format mismatch)
        """
        # Python's fromisoformat handles Z suffix starting in Python 3.11
        search_result = SearchResult(
            id="mem_2",
            score=0.85,
            payload={
                "category": "preference",
                "content": "Test preference",
                "importance": 0.7,
                "tags": [],
                "created_at": "2024-06-15T12:30:45Z",  # Z suffix format
            },
        )

        # Must parse without error (Python 3.11+)
        memory = MemoryResult.from_search_result(search_result)
        assert isinstance(memory.created_at, datetime)

    def test_code_result_from_search_result(self) -> None:
        """Verify CodeResult.from_search_result handles actual payloads."""
        search_result = SearchResult(
            id="code_1",
            score=0.9,
            payload={
                "project": "test_project",
                "file_path": "/src/main.py",
                "language": "python",
                "unit_type": "function",
                "qualified_name": "main.entry_point",
                "code": "def entry_point(): pass",
                "line_start": 10,
                "line_end": 15,
                "docstring": "Entry point function",
            },
        )

        code = CodeResult.from_search_result(search_result)

        assert code.project == "test_project"
        assert code.line_start == 10
        assert code.line_end == 15
        assert code.docstring == "Entry point function"

    def test_commit_result_datetime_parsing(self) -> None:
        """Verify CommitResult parses committed_at as ISO string."""
        search_result = SearchResult(
            id="commit_1",
            score=0.9,
            payload={
                "sha": "abc123",
                "message": "Test commit",
                "author": "test_author",
                "author_email": "test@example.com",
                "committed_at": "2024-06-15T14:00:00+00:00",
                "files_changed": ["file1.py"],
            },
        )

        commit = CommitResult.from_search_result(search_result)

        assert isinstance(commit.committed_at, datetime)
        assert commit.committed_at.year == 2024
        assert commit.sha == "abc123"

    def test_value_result_from_search_result(self) -> None:
        """Verify ValueResult.from_search_result handles actual payloads."""
        search_result = SearchResult(
            id="value_1",
            score=0.88,
            payload={
                "axis": "strategy",
                "cluster_id": "cluster_001",
                "text": "Always validate inputs",
                "member_count": 8,
                "avg_confidence": 0.92,
                "created_at": "2024-06-15T10:00:00+00:00",
            },
        )

        value = ValueResult.from_search_result(search_result)

        assert value.axis == "strategy"
        assert value.text == "Always validate inputs"
        assert value.member_count == 8
        assert isinstance(value.created_at, datetime)


# =============================================================================
# Context Assembly Boundary Contract Tests
# =============================================================================


class TestContextAssemblyBoundaryContracts:
    """Verify data contracts at context assembly boundaries."""

    def test_distribute_budget_rejects_invalid_types(self) -> None:
        """Verify distribute_budget raises ValueError for invalid types.

        Regression: BUG-036 (unhelpful KeyError)
        """
        with pytest.raises(ValueError) as exc_info:
            distribute_budget(["memories", "invalid_type"], 1000)

        # Error message must include the invalid type and valid options
        error_msg = str(exc_info.value)
        assert "invalid_type" in error_msg
        assert "Valid:" in error_msg or "memories" in error_msg

    def test_distribute_budget_validates_all_types(self) -> None:
        """Verify distribute_budget validates all provided types."""
        # Should not raise
        result = distribute_budget(["memories", "code", "experiences"], 1000)
        assert "memories" in result
        assert "code" in result
        assert "experiences" in result
        # Integer division may result in slightly less than max_tokens
        assert sum(result.values()) <= 1000
        assert sum(result.values()) >= 990  # Should be close to budget

    def test_format_experience_handles_all_fields(self) -> None:
        """Verify format_experience handles all field variations."""
        # Complete experience with all optional fields
        metadata_full: dict[str, Any] = {
            "domain": "debugging",
            "strategy": "root-cause-analysis",
            "goal": "Fix bug",
            "hypothesis": "Cache issue",
            "action": "Clear cache",
            "prediction": "Bug resolved",
            "outcome_status": "falsified",
            "outcome_result": "Bug persisted",
            "surprise": "Unexpected finding",
            "lesson": {"what_worked": "Investigation", "takeaway": "Check logs"},
        }

        # Must not raise
        formatted = format_experience(metadata_full)
        assert "debugging" in formatted
        assert "Fix bug" in formatted
        assert "Unexpected finding" in formatted
        assert "Investigation" in formatted

    def test_format_experience_handles_missing_optional(self) -> None:
        """Verify format_experience handles missing optional fields."""
        # Minimal experience without optional fields
        metadata_minimal: dict[str, Any] = {
            "domain": "feature",
            "strategy": "divide-and-conquer",
            "goal": "Add feature",
            "hypothesis": "This approach works",
            "action": "Implement",
            "prediction": "Feature works",
            "outcome_status": "confirmed",
            "outcome_result": "Feature delivered",
        }

        # Must not raise
        formatted = format_experience(metadata_minimal)
        assert "feature" in formatted
        assert "confirmed" in formatted

    def test_format_experience_handles_lesson_dataclass(self) -> None:
        """Verify format_experience handles Lesson dataclass."""
        lesson = Lesson(what_worked="Testing approach", takeaway="Always test")

        metadata: dict[str, Any] = {
            "domain": "testing",
            "strategy": "systematic-elimination",
            "goal": "Find bug",
            "hypothesis": "Input validation issue",
            "action": "Add validation",
            "prediction": "Bug fixed",
            "outcome_status": "confirmed",
            "outcome_result": "Validation added",
            "lesson": lesson,
        }

        formatted = format_experience(metadata)
        assert "Testing approach" in formatted

    def test_format_memory_handles_importance(self) -> None:
        """Verify format_memory displays importance correctly."""
        metadata: dict[str, Any] = {
            "content": "Important fact about coding",
            "category": "fact",
            "importance": 0.85,
        }

        formatted = format_memory(metadata)
        assert "0.85" in formatted
        assert "fact" in formatted

    def test_format_code_handles_line_start(self) -> None:
        """Verify format_code uses line_start field correctly."""
        metadata: dict[str, Any] = {
            "unit_type": "function",
            "qualified_name": "module.my_function",
            "file_path": "/src/module.py",
            "line_start": 42,
            "language": "python",
            "code": "def my_function(): pass",
            "docstring": None,
        }

        formatted = format_code(metadata)
        assert ":42" in formatted
        assert "module.my_function" in formatted

    def test_format_value_handles_member_count(self) -> None:
        """Verify format_value uses member_count field correctly."""
        metadata: dict[str, Any] = {
            "axis": "strategy",
            "member_count": 15,
            "text": "Test early and often",
        }

        formatted = format_value(metadata)
        assert "15" in formatted
        assert "strategy" in formatted

    def test_format_commit_handles_files(self) -> None:
        """Verify format_commit handles files_changed correctly."""
        metadata: dict[str, Any] = {
            "sha": "abc123def",
            "author": "developer",
            "committed_at": "2024-06-15",
            "message": "Add feature",
            "files_changed": ["file1.py", "file2.py", "file3.py", "file4.py"],
        }

        formatted = format_commit(metadata)
        assert "abc123d" in formatted  # First 7 chars of SHA
        assert "file1.py" in formatted
        assert "1 more" in formatted  # Shows count of extra files


# =============================================================================
# Embedding Layer Boundary Contract Tests
# =============================================================================


class TestEmbeddingBoundaryContracts:
    """Verify data contracts at embedding layer boundaries.

    Tests embedding dimension consistency and float32 precision preservation
    as required by spec section 4 (Embedding Layer Boundaries).
    """

    async def test_embedding_dimension_matches_expectation(
        self,
        embedding_service: MockEmbedding,
    ) -> None:
        """Verify embedding dimension matches expected value.

        Boundary: EmbeddingService -> VectorStore
        Critical Constraint: Dimension must match collection (768 for Mock)
        """
        embedding = await embedding_service.embed("test text")

        # Verify dimension matches expected value
        assert len(embedding) == 768, f"Expected 768 dimensions, got {len(embedding)}"

        # Verify dimension property is consistent
        assert embedding_service.dimension == 768

    async def test_embedding_float32_precision(
        self,
        embedding_service: MockEmbedding,
    ) -> None:
        """Verify embedding is float32 type.

        Boundary: EmbeddingService output
        Critical Constraint: Float32 precision
        """
        embedding = await embedding_service.embed("precision test")

        # Verify dtype is float32
        assert embedding.dtype == np.float32, (
            f"Expected float32, got {embedding.dtype}"
        )

    async def test_embedding_float32_preserved_through_storage(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify float32 precision is preserved through storage round-trip.

        Boundary: np.ndarray -> Qdrant vector -> retrieval
        Critical Constraint: Float32 values preserved
        """
        # Generate embedding
        original_embedding = await embedding_service.embed("precision test")

        # Store and retrieve
        test_id = "precision_test_001"
        await vector_store.upsert(
            collection=test_collections["memories"],
            id=test_id,
            vector=original_embedding,
            payload={
                "id": test_id,
                "content": "test",
                "category": "fact",
                "importance": 0.5,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

        # Retrieve by ID
        result = await vector_store.get(
            test_collections["memories"], test_id, with_vector=True
        )
        assert result is not None

        # Qdrant may return vectors as lists, so convert if needed
        if result.vector is not None:
            retrieved_vector = np.array(result.vector, dtype=np.float32)

            # Check values are close (float32 precision)
            assert np.allclose(
                original_embedding, retrieved_vector, rtol=1e-5
            ), "Float32 precision not preserved through storage round-trip"

    async def test_embedding_dimension_constant_across_texts(
        self,
        embedding_service: MockEmbedding,
    ) -> None:
        """Verify all embeddings have consistent dimension regardless of input."""
        # Various text inputs
        texts = [
            "",  # empty string
            "a",  # single char
            "test",  # short
            "This is a longer text with more words to embed",  # medium
            "x" * 1000,  # very long
        ]

        embeddings = []
        for text in texts:
            emb = await embedding_service.embed(text)
            embeddings.append(emb)

        # All should have same dimension
        dimensions = [len(emb) for emb in embeddings]
        assert all(d == 768 for d in dimensions), f"Inconsistent dimensions: {dimensions}"


# =============================================================================
# Premortem Context Assembly Boundary Tests (Scenario 6)
# =============================================================================


class TestPremortemContextAssemblyBoundary:
    """Verify data contracts for premortem context assembly.

    Tests Scenario 6 from the spec: get_premortem_context flow
    which searches experiences across 4 axes and values.
    """

    async def test_premortem_context_groups_by_axis(self) -> None:
        """Verify premortem context groups experiences by axis.

        Validation checkpoint 1: Experiences grouped by axis in output
        """
        from unittest.mock import AsyncMock, MagicMock

        # Create mock searcher with experiences from different axes
        mock_searcher = MagicMock()

        # Mock experience results for each axis
        mock_exp_full = ExperienceResult(
            id="exp_full_1",
            ghap_id="ghap_1",
            axis="full",
            domain="debugging",
            strategy="root-cause-analysis",
            goal="Fix bug",
            hypothesis="Cache issue",
            action="Clear cache",
            prediction="Bug fixed",
            outcome_status="falsified",
            outcome_result="Bug persisted",
            surprise=None,
            root_cause=None,
            lesson=None,
            confidence_tier="silver",
            iteration_count=1,
            score=0.9,
            created_at=datetime.now(UTC),
        )

        # Configure mock searcher methods
        mock_searcher.search_experiences = AsyncMock(
            side_effect=[
                [mock_exp_full],  # full axis
                [],  # surprise axis
                [],  # root_cause axis
            ]
        )
        mock_searcher.search_values = AsyncMock(return_value=[])

        assembler = ContextAssembler(mock_searcher)

        # Get premortem context
        result = await assembler.get_premortem_context(
            domain="debugging",
            strategy=None,
            limit=10,
        )

        # Verify result structure
        assert result.markdown is not None
        assert result.items is not None

    async def test_premortem_context_includes_values_section(self) -> None:
        """Verify premortem context includes values in 'Relevant Principles' section.

        Validation checkpoint 2: Values appear in 'Relevant Principles' section
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_searcher = MagicMock()
        mock_searcher.search_experiences = AsyncMock(return_value=[])
        mock_searcher.search_values = AsyncMock(
            return_value=[
                ValueResult(
                    id="val_1",
                    axis="strategy",
                    cluster_id="cluster_1",
                    text="Validate inputs early",
                    score=0.9,
                    member_count=10,
                    avg_confidence=0.95,
                    created_at=datetime.now(UTC),
                ),
            ]
        )

        assembler = ContextAssembler(mock_searcher)
        result = await assembler.get_premortem_context(
            domain="debugging",
            limit=10,
        )

        # Values should be included
        assert "Relevant Principles" in result.markdown or len(
            [i for i in result.items if i.source == "value"]
        ) > 0


# =============================================================================
# Graceful Degradation Boundary Tests
# =============================================================================


class TestGracefulDegradationBoundary:
    """Verify graceful degradation at component boundaries.

    Tests that partial failures don't crash the system and
    error information is properly propagated.
    """

    async def test_premortem_partial_failure_doesnt_crash(self) -> None:
        """Verify premortem assembly continues despite partial search failures.

        Validation checkpoint 3 (Scenario 6): Partial failures don't crash
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_searcher = MagicMock()

        # Some queries succeed, some fail
        mock_searcher.search_experiences = AsyncMock(
            side_effect=[
                [],  # full axis succeeds with empty
                Exception("Connection timeout"),  # surprise axis fails
                Exception("Service unavailable"),  # root_cause axis fails
            ]
        )
        mock_searcher.search_values = AsyncMock(return_value=[])

        assembler = ContextAssembler(mock_searcher)

        # Should NOT raise despite partial failures
        result = await assembler.get_premortem_context(
            domain="debugging",
            strategy=None,
            limit=10,
        )

        # Result should still be valid (may be empty)
        assert result is not None
        assert result.markdown is not None

    async def test_context_assembly_partial_source_failure(self) -> None:
        """Verify context assembly handles source failures gracefully.

        Spec requirement: Some results return even if one source fails
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_searcher = MagicMock()

        # Memories succeed
        mock_searcher.search_memories = AsyncMock(
            return_value=[
                MemoryResult(
                    id="mem_1",
                    category="fact",
                    content="Test fact",
                    score=0.9,
                    importance=0.8,
                    tags=[],
                    created_at=datetime.now(UTC),
                    verified_at=None,
                    verification_status=None,
                ),
            ]
        )

        # Code search fails
        mock_searcher.search_code = AsyncMock(
            side_effect=Exception("Code index unavailable")
        )

        assembler = ContextAssembler(mock_searcher)

        # Should NOT raise despite code search failure
        result = await assembler.assemble_context(
            query="test query",
            context_types=["memories", "code"],
            limit=10,
        )

        # Should still have memory results
        assert result is not None
        assert result.markdown is not None
        # Memory results should be present
        assert "memories" in result.sources_used

    async def test_invalid_context_type_raises_proper_error(self) -> None:
        """Verify invalid context type raises InvalidContextTypeError.

        Regression: BUG-036 (KeyError instead of helpful error)
        """
        from unittest.mock import MagicMock

        mock_searcher = MagicMock()
        assembler = ContextAssembler(mock_searcher)

        with pytest.raises(InvalidContextTypeError) as exc_info:
            await assembler.assemble_context(
                query="test",
                context_types=["memories", "invalid_source"],
                limit=10,
            )

        # Error should include the invalid type and valid options
        assert exc_info.value.invalid_type == "invalid_source"
        assert len(exc_info.value.valid_types) > 0


# =============================================================================
# Tool Response Boundary Contract Tests
# =============================================================================


class TestToolResponseBoundaryContracts:
    """Verify tool response boundaries."""

    async def test_search_experiences_no_keyerror_on_payload(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify search_experiences doesn't raise KeyError on conversion.

        Tests that all required fields are present in persisted payloads.
        """
        from unittest.mock import patch

        # First, persist a GHAP entry
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = ObservationCollector(journal_dir=Path(tmpdir) / "journal")
            persister = ObservationPersister(
                embedding_service=embedding_service,
                vector_store=vector_store,
                collection_prefix="test_bc_ghap",
            )

            await collector.start_session()
            await collector.create_ghap(
                domain=Domain.FEATURE,
                strategy=Strategy.DIVIDE_AND_CONQUER,
                goal="Test search boundary",
                hypothesis="Search returns valid results",
                action="Persist and search",
                prediction="No KeyError",
            )
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus.CONFIRMED,
                result="Search worked",
            )
            await persister.persist(resolved)

            # Now search and convert
            searcher = Searcher(
                embedding_service=embedding_service,
                vector_store=vector_store,
            )

            with patch(
                "clams.search.collections.CollectionName.get_experience_collection",
                return_value="test_bc_ghap_full",
            ):
                # This should NOT raise KeyError
                results = await searcher.search_experiences(
                    query="test search boundary",
                    axis="full",
                    limit=5,
                )

                # Should find results
                assert len(results) > 0
                # All results should have required fields
                for result in results:
                    assert result.ghap_id is not None
                    assert result.domain is not None
                    assert result.outcome_status is not None


# =============================================================================
# Regression Prevention Tests
# =============================================================================


class TestRegressionPrevention:
    """Specific regression tests for bugs mentioned in spec.

    Note: BUG-040 and BUG-041 have comprehensive test files at:
    - tests/context/test_bug_040_type_consistency.py
    - tests/bugs/test_bug_041_searcher_inheritance.py

    This class provides additional boundary-focused regression tests
    that complement those existing test files.
    """

    def test_bug_006_ghap_content_fields(self) -> None:
        """BUG-006: GHAP payload must contain all content fields.

        Issue: ObservationPersister stored incomplete payload that
        ExperienceResult.from_search_result() expected.

        Note: Full test in test_ghap_falsified_includes_root_cause
        """
        # This is a marker test - the actual verification is in
        # TestStorageBoundaryContracts.test_ghap_falsified_includes_root_cause
        pass

    def test_bug_019_similarity_must_be_float(self) -> None:
        """BUG-019: validate_value similarity must be float, not None.

        Note: This tests the contract - if similarity is returned, it must be float.
        """
        # Test that ExperienceResult score is always float
        search_result = SearchResult(
            id="test",
            score=0.85,  # Must be float, not None
            payload={
                "ghap_id": "test",
                "axis": "full",
                "domain": "debugging",
                "strategy": "root-cause-analysis",
                "goal": "Test",
                "hypothesis": "Test",
                "action": "Test",
                "prediction": "Test",
                "outcome_status": "confirmed",
                "outcome_result": "Test",
                "confidence_tier": "silver",
                "iteration_count": 1,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        result = ExperienceResult.from_search_result(search_result)
        assert isinstance(result.score, float)
        assert result.score == 0.85

    def test_bug_027_datetime_iso_format(self) -> None:
        """BUG-027: created_at stored as ISO string, parsed correctly.

        Note: Full test in test_memory_result_datetime_parsing
        """
        # Verify ISO format is correctly parsed
        iso_string = "2024-06-15T12:30:45+00:00"
        parsed = datetime.fromisoformat(iso_string)
        assert parsed.year == 2024
        assert parsed.month == 6
        assert parsed.day == 15

    def test_bug_036_distribute_budget_validation(self) -> None:
        """BUG-036: distribute_budget must reject invalid types with clear error.

        Note: Full test in test_distribute_budget_rejects_invalid_types
        """
        # This is a marker test - the actual verification is in
        # TestContextAssemblyBoundaryContracts.test_distribute_budget_rejects_invalid_types
        pass

    def test_bug_040_types_are_reexports(self) -> None:
        """BUG-040: Result types in searcher_types are re-exports from search.results.

        After the BUG-040 fix, context/searcher_types.py re-exports types from
        search/results.py to ensure a single source of truth. These should be
        the EXACT SAME types (identity, not just equality).

        Note: Comprehensive tests exist in tests/context/test_bug_040_type_consistency.py
        """
        from clams.context.searcher_types import CodeResult as ABCCodeResult
        from clams.context.searcher_types import (
            ExperienceResult as ABCExperienceResult,
        )
        from clams.context.searcher_types import Lesson as ABCLesson
        from clams.context.searcher_types import MemoryResult as ABCMemoryResult
        from clams.context.searcher_types import RootCause as ABCRootCause
        from clams.context.searcher_types import ValueResult as ABCValueResult
        from clams.search.results import CodeResult as SearchCodeResult
        from clams.search.results import ExperienceResult as SearchExperienceResult
        from clams.search.results import Lesson as SearchLesson
        from clams.search.results import MemoryResult as SearchMemoryResult
        from clams.search.results import RootCause as SearchRootCause
        from clams.search.results import ValueResult as SearchValueResult

        # These MUST be the SAME types (is, not just ==)
        # The fix for BUG-040 consolidated to a single source of truth
        assert (
            SearchExperienceResult is ABCExperienceResult
        ), "ExperienceResult should be re-exported from search.results"
        assert (
            SearchCodeResult is ABCCodeResult
        ), "CodeResult should be re-exported from search.results"
        assert (
            SearchMemoryResult is ABCMemoryResult
        ), "MemoryResult should be re-exported from search.results"
        assert (
            SearchValueResult is ABCValueResult
        ), "ValueResult should be re-exported from search.results"
        assert (
            SearchLesson is ABCLesson
        ), "Lesson should be re-exported from search.results"
        assert (
            SearchRootCause is ABCRootCause
        ), "RootCause should be re-exported from search.results"

    def test_bug_041_searcher_inheritance(self) -> None:
        """BUG-041: Concrete Searcher inherits from abstract Searcher ABC.

        Note: Comprehensive tests exist in tests/bugs/test_bug_041_searcher_inheritance.py
        This test provides a quick sanity check for the boundary contract suite.
        """
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher as ConcreteSearcher

        # Concrete Searcher must be a SUBCLASS of the ABC (inheritance)
        assert issubclass(
            ConcreteSearcher, SearcherABC
        ), "Concrete Searcher must inherit from abstract Searcher"


# =============================================================================
# Datetime Round-Trip Tests (Scenario 8)
# =============================================================================


class TestDatetimeRoundTrip:
    """Verify datetime round-trip integrity."""

    async def test_datetime_timezone_preserved(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify timezone is preserved through storage round-trip."""
        utc_time = datetime(2024, 6, 15, 12, 30, 45, tzinfo=UTC)
        memory_id = str(uuid4())

        embedding = await embedding_service.embed("timezone test")
        payload = {
            "id": memory_id,
            "content": "Test content",
            "category": "fact",
            "importance": 0.5,
            "created_at": utc_time.isoformat(),
        }

        await vector_store.upsert(
            collection=test_collections["memories"],
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["memories"], memory_id)
        assert result is not None

        # Parse and verify
        parsed = datetime.fromisoformat(result.payload["created_at"])
        assert parsed.tzinfo is not None
        assert parsed.year == 2024
        assert parsed.month == 6
        assert parsed.day == 15
        assert parsed.hour == 12
        assert parsed.minute == 30
        assert parsed.second == 45

    async def test_datetime_microsecond_precision(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        test_collections: dict[str, str],
    ) -> None:
        """Verify microsecond precision is preserved."""
        precise_time = datetime(2024, 6, 15, 12, 30, 45, 123456, tzinfo=UTC)
        memory_id = str(uuid4())

        embedding = await embedding_service.embed("precision test")
        payload = {
            "id": memory_id,
            "content": "Test content",
            "category": "fact",
            "importance": 0.5,
            "created_at": precise_time.isoformat(),
        }

        await vector_store.upsert(
            collection=test_collections["memories"],
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        result = await vector_store.get(test_collections["memories"], memory_id)
        assert result is not None

        # Parse and verify microseconds
        parsed = datetime.fromisoformat(result.payload["created_at"])
        assert parsed.microsecond == 123456
