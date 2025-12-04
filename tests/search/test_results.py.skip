"""Unit tests for result dataclasses."""

from datetime import UTC, datetime

from learning_memory_server.search.results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)
from learning_memory_server.storage.base import SearchResult


class TestMemoryResult:
    """Tests for MemoryResult dataclass."""

    def test_from_search_result_with_all_fields(self):
        """Verify conversion from SearchResult with all fields."""
        search_result = SearchResult(
            id="mem_123",
            score=0.95,
            payload={
                "category": "preference",
                "content": "Use async/await",
                "tags": ["python", "async"],
                "created_at": "2024-01-01T12:00:00Z",
                "verified_at": "2024-01-02T12:00:00Z",
                "verification_status": "passed",
            },
        )
        result = MemoryResult.from_search_result(search_result)
        assert result.id == "mem_123"
        assert result.score == 0.95
        assert result.category == "preference"
        assert result.content == "Use async/await"
        assert result.tags == ["python", "async"]
        assert result.created_at == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=UTC
        )
        assert result.verified_at == datetime(
            2024, 1, 2, 12, 0, 0, tzinfo=UTC
        )
        assert result.verification_status == "passed"

    def test_from_search_result_with_optional_fields_none(self):
        """Verify conversion handles None for optional fields."""
        search_result = SearchResult(
            id="mem_124",
            score=0.90,
            payload={
                "category": "fact",
                "content": "Test content",
                "created_at": "2024-01-01T12:00:00Z",
            },
        )
        result = MemoryResult.from_search_result(search_result)
        assert result.tags == []
        assert result.verified_at is None
        assert result.verification_status is None


class TestCodeResult:
    """Tests for CodeResult dataclass."""

    def test_from_search_result_with_all_fields(self):
        """Verify conversion from SearchResult with all fields."""
        search_result = SearchResult(
            id="code_123",
            score=0.92,
            payload={
                "project": "clams",
                "file_path": "/src/auth.py",
                "language": "python",
                "unit_type": "function",
                "qualified_name": "auth.login",
                "code": "def login(): pass",
                "docstring": "Login function",
                "line_start": 10,
                "line_end": 12,
            },
        )
        result = CodeResult.from_search_result(search_result)
        assert result.id == "code_123"
        assert result.score == 0.92
        assert result.project == "clams"
        assert result.file_path == "/src/auth.py"
        assert result.language == "python"
        assert result.unit_type == "function"
        assert result.qualified_name == "auth.login"
        assert result.code == "def login(): pass"
        assert result.docstring == "Login function"
        assert result.line_start == 10
        assert result.line_end == 12

    def test_from_search_result_without_docstring(self):
        """Verify conversion handles None docstring."""
        search_result = SearchResult(
            id="code_124",
            score=0.85,
            payload={
                "project": "clams",
                "file_path": "/src/utils.py",
                "language": "python",
                "unit_type": "class",
                "qualified_name": "utils.Helper",
                "code": "class Helper: pass",
                "line_start": 5,
                "line_end": 6,
            },
        )
        result = CodeResult.from_search_result(search_result)
        assert result.docstring is None


class TestExperienceResult:
    """Tests for ExperienceResult dataclass."""

    def test_from_search_result_with_all_fields(self):
        """Verify conversion from SearchResult with all nested objects."""
        search_result = SearchResult(
            id="exp_123",
            score=0.88,
            payload={
                "ghap_id": "ghap_001",
                "axis": "full",
                "domain": "debugging",
                "strategy": "hypothesis testing",
                "goal": "fix bug",
                "hypothesis": "null pointer",
                "action": "add check",
                "prediction": "no crash",
                "outcome_status": "confirmed",
                "outcome_result": "bug fixed",
                "surprise": "unexpected edge case",
                "root_cause": {
                    "category": "logic_error",
                    "description": "missing null check",
                },
                "lesson": {
                    "what_worked": "defensive programming",
                    "takeaway": "always check nulls",
                },
                "confidence_tier": "high",
                "iteration_count": 1,
                "created_at": "2024-01-01T12:00:00Z",
            },
        )
        result = ExperienceResult.from_search_result(search_result)
        assert result.id == "exp_123"
        assert result.score == 0.88
        assert result.ghap_id == "ghap_001"
        assert result.axis == "full"
        assert result.domain == "debugging"
        assert result.strategy == "hypothesis testing"
        assert result.goal == "fix bug"
        assert result.hypothesis == "null pointer"
        assert result.action == "add check"
        assert result.prediction == "no crash"
        assert result.outcome_status == "confirmed"
        assert result.outcome_result == "bug fixed"
        assert result.surprise == "unexpected edge case"
        assert result.confidence_tier == "high"
        assert result.iteration_count == 1
        assert result.created_at == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=UTC
        )

        # Check nested objects
        assert isinstance(result.root_cause, RootCause)
        assert result.root_cause.category == "logic_error"
        assert result.root_cause.description == "missing null check"

        assert isinstance(result.lesson, Lesson)
        assert result.lesson.what_worked == "defensive programming"
        assert result.lesson.takeaway == "always check nulls"

    def test_from_search_result_without_optional_nested_objects(self):
        """Verify conversion handles None for optional nested objects."""
        search_result = SearchResult(
            id="exp_124",
            score=0.80,
            payload={
                "ghap_id": "ghap_002",
                "axis": "strategy",
                "domain": "testing",
                "strategy": "unit testing",
                "goal": "ensure coverage",
                "hypothesis": "tests catch bugs",
                "action": "write tests",
                "prediction": "fewer bugs",
                "outcome_status": "confirmed",
                "outcome_result": "coverage increased",
                "confidence_tier": "medium",
                "iteration_count": 2,
                "created_at": "2024-01-02T12:00:00Z",
            },
        )
        result = ExperienceResult.from_search_result(search_result)
        assert result.surprise is None
        assert result.root_cause is None
        assert result.lesson is None


class TestValueResult:
    """Tests for ValueResult dataclass."""

    def test_from_search_result(self):
        """Verify conversion from SearchResult."""
        search_result = SearchResult(
            id="val_123",
            score=0.91,
            payload={
                "axis": "strategy",
                "cluster_id": "cluster_001",
                "text": "Test early",
                "member_count": 10,
                "avg_confidence": 0.85,
                "created_at": "2024-01-01T12:00:00Z",
            },
        )
        result = ValueResult.from_search_result(search_result)
        assert result.id == "val_123"
        assert result.score == 0.91
        assert result.axis == "strategy"
        assert result.cluster_id == "cluster_001"
        assert result.text == "Test early"
        assert result.member_count == 10
        assert result.avg_confidence == 0.85
        assert result.created_at == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=UTC
        )


class TestCommitResult:
    """Tests for CommitResult dataclass."""

    def test_from_search_result(self):
        """Verify conversion from SearchResult."""
        search_result = SearchResult(
            id="commit_123",
            score=0.87,
            payload={
                "sha": "abc123",
                "message": "Fix bug",
                "author": "alice",
                "author_email": "alice@example.com",
                "committed_at": "2024-01-01T12:00:00Z",
                "files_changed": ["src/auth.py", "tests/test_auth.py"],
            },
        )
        result = CommitResult.from_search_result(search_result)
        assert result.id == "commit_123"
        assert result.score == 0.87
        assert result.sha == "abc123"
        assert result.message == "Fix bug"
        assert result.author == "alice"
        assert result.author_email == "alice@example.com"
        assert result.committed_at == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=UTC
        )
        assert result.files_changed == ["src/auth.py", "tests/test_auth.py"]
