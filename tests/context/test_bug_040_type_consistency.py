"""Regression test for BUG-040: Duplicate result type definitions.

This test verifies that formatting functions work correctly with the
canonical result types from clams.search.results, preventing runtime
KeyError/AttributeError that occurred with mismatched field names.
"""

from datetime import UTC, datetime

from clams.context.formatting import (
    format_code,
    format_experience,
    format_memory,
    format_value,
)
from clams.search.results import (
    CodeResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)


class TestFormatCodeWithCanonicalType:
    """Test format_code() works with search.results.CodeResult."""

    def test_format_code_uses_line_start(self):
        """Verify format_code() correctly uses line_start field."""
        code_result = CodeResult(
            id="code_1",
            project="test_project",
            file_path="/src/example.py",
            language="python",
            unit_type="function",
            qualified_name="example.hello",
            code="def hello():\n    pass",
            docstring="Say hello",
            score=0.9,
            line_start=42,
            line_end=44,
        )

        # format_code expects a dict, so convert via __dict__
        output = format_code(code_result.__dict__)

        assert "line_start" in code_result.__dict__  # Canonical field name
        assert "start_line" not in code_result.__dict__  # Old field name
        assert ":42" in output  # Line number should appear in output
        assert "example.hello" in output
        assert "def hello()" in output

    def test_format_code_no_keyerror(self):
        """Ensure no KeyError when using canonical CodeResult."""
        code_result = CodeResult(
            id="code_2",
            project="clams",
            file_path="/src/main.py",
            language="python",
            unit_type="class",
            qualified_name="main.App",
            code="class App: pass",
            docstring=None,
            score=0.8,
            line_start=1,
            line_end=1,
        )

        # This should NOT raise KeyError
        output = format_code(code_result.__dict__)
        assert "**Class**" in output
        assert "main.App" in output


class TestFormatExperienceWithCanonicalType:
    """Test format_experience() works with search.results.ExperienceResult."""

    def test_format_experience_with_lesson_dataclass(self):
        """Verify format_experience() handles Lesson dataclass."""
        lesson = Lesson(what_worked="defensive programming", takeaway="check nulls")

        experience_result = ExperienceResult(
            id="exp_1",
            ghap_id="ghap_001",
            axis="full",
            domain="debugging",
            strategy="hypothesis testing",
            goal="fix bug",
            hypothesis="null pointer",
            action="add check",
            prediction="no crash",
            outcome_status="confirmed",
            outcome_result="bug fixed",
            surprise=None,
            root_cause=None,
            lesson=lesson,
            confidence_tier="high",
            iteration_count=1,
            score=0.9,
            created_at=datetime.now(UTC),
        )

        # This should NOT raise AttributeError when accessing lesson.what_worked
        output = format_experience(experience_result.__dict__)

        assert "**Lesson**: defensive programming" in output
        assert "debugging" in output
        assert "hypothesis testing" in output

    def test_format_experience_with_root_cause_dataclass(self):
        """Verify format_experience() handles RootCause dataclass."""
        root_cause = RootCause(
            category="logic_error", description="missing null check"
        )

        experience_result = ExperienceResult(
            id="exp_2",
            ghap_id="ghap_002",
            axis="root_cause",
            domain="testing",
            strategy="unit testing",
            goal="ensure coverage",
            hypothesis="tests catch bugs",
            action="write tests",
            prediction="fewer bugs",
            outcome_status="falsified",
            outcome_result="missed edge case",
            surprise="unexpected corner case",
            root_cause=root_cause,
            lesson=None,
            confidence_tier="medium",
            iteration_count=2,
            score=0.85,
            created_at=datetime.now(UTC),
        )

        # Should not crash with RootCause dataclass
        output = format_experience(experience_result.__dict__)

        assert "**Surprise**: unexpected corner case" in output
        assert "testing" in output

    def test_format_experience_no_attributeerror(self):
        """Ensure no AttributeError when lesson is Lesson dataclass."""
        experience_result = ExperienceResult(
            id="exp_3",
            ghap_id="ghap_003",
            axis="strategy",
            domain="feature",
            strategy="incremental",
            goal="add feature",
            hypothesis="small steps work",
            action="iterate",
            prediction="success",
            outcome_status="confirmed",
            outcome_result="feature added",
            surprise=None,
            root_cause=None,
            lesson=Lesson(what_worked="small commits", takeaway="easier review"),
            confidence_tier="gold",
            iteration_count=1,
            score=0.95,
            created_at=datetime.now(UTC),
        )

        # This should NOT raise AttributeError
        output = format_experience(experience_result.__dict__)
        assert "**Lesson**: small commits" in output


class TestFormatValueWithCanonicalType:
    """Test format_value() works with search.results.ValueResult."""

    def test_format_value_uses_member_count(self):
        """Verify format_value() correctly uses member_count field."""
        value_result = ValueResult(
            id="val_1",
            axis="strategy",
            cluster_id="cluster_001",
            text="Test early and often",
            score=0.9,
            member_count=15,
            avg_confidence=0.85,
            created_at=datetime.now(UTC),
        )

        output = format_value(value_result.__dict__)

        assert "member_count" in value_result.__dict__  # Canonical field name
        assert "cluster_size" not in value_result.__dict__  # Old field name
        assert "cluster size: 15" in output
        assert "Test early and often" in output

    def test_format_value_no_keyerror(self):
        """Ensure no KeyError when using canonical ValueResult."""
        value_result = ValueResult(
            id="val_2",
            axis="domain",
            cluster_id="cluster_002",
            text="Always validate input",
            score=0.8,
            member_count=8,
            avg_confidence=0.9,
            created_at=datetime.now(UTC),
        )

        # This should NOT raise KeyError
        output = format_value(value_result.__dict__)
        assert "**Value**" in output
        assert "domain" in output


class TestFormatMemoryWithCanonicalType:
    """Test format_memory() works with search.results.MemoryResult."""

    def test_format_memory_with_importance(self):
        """Verify format_memory() correctly uses importance field."""
        memory_result = MemoryResult(
            id="mem_1",
            category="preference",
            content="Use async/await for I/O",
            score=0.95,
            importance=0.8,
            tags=["python", "async"],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )

        output = format_memory(memory_result.__dict__)

        assert "importance" in memory_result.__dict__
        assert "Importance: 0.80" in output
        assert "Use async/await" in output

    def test_format_memory_no_keyerror(self):
        """Ensure no KeyError when using canonical MemoryResult."""
        memory_result = MemoryResult(
            id="mem_2",
            category="fact",
            content="Python uses indentation",
            score=0.9,
            importance=0.5,
            tags=[],
            created_at=datetime.now(UTC),
            verified_at=datetime.now(UTC),
            verification_status="passed",
        )

        # This should NOT raise KeyError
        output = format_memory(memory_result.__dict__)
        assert "**Memory**" in output
        assert "fact" in output


class TestTypeConsistency:
    """Test that searcher_types re-exports from search.results."""

    def test_searcher_types_reexports_canonical_types(self):
        """Verify searcher_types re-exports types from search.results."""
        from clams.context.searcher_types import (
            CodeResult as SearcherCodeResult,
        )
        from clams.context.searcher_types import (
            ExperienceResult as SearcherExperienceResult,
        )
        from clams.context.searcher_types import (
            Lesson as SearcherLesson,
        )
        from clams.context.searcher_types import (
            MemoryResult as SearcherMemoryResult,
        )
        from clams.context.searcher_types import (
            RootCause as SearcherRootCause,
        )
        from clams.context.searcher_types import (
            ValueResult as SearcherValueResult,
        )

        # These should be the exact same types (same id)
        assert SearcherCodeResult is CodeResult
        assert SearcherExperienceResult is ExperienceResult
        assert SearcherValueResult is ValueResult
        assert SearcherMemoryResult is MemoryResult
        assert SearcherLesson is Lesson
        assert SearcherRootCause is RootCause

    def test_no_duplicate_definitions(self):
        """Verify there are no duplicate type definitions causing mismatches."""
        # Check that field names match
        code_fields = {f.name for f in CodeResult.__dataclass_fields__.values()}
        assert "line_start" in code_fields
        assert "line_end" in code_fields
        assert "start_line" not in code_fields  # Old field should not exist
        assert "end_line" not in code_fields  # Old field should not exist

        value_fields = {f.name for f in ValueResult.__dataclass_fields__.values()}
        assert "member_count" in value_fields
        assert "avg_confidence" in value_fields
        assert "cluster_size" not in value_fields  # Old field should not exist
        assert "similarity_to_centroid" not in value_fields  # Old field

        memory_fields = {f.name for f in MemoryResult.__dataclass_fields__.values()}
        assert "importance" in memory_fields
