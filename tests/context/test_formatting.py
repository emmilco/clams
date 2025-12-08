"""Tests for markdown formatting."""

from clams.context.formatting import (
    assemble_markdown,
    format_code,
    format_commit,
    format_experience,
    format_memory,
    format_value,
)
from clams.context.models import ContextItem


def test_format_memory() -> None:
    """Test memory formatting."""
    metadata = {
        "content": "Use async/await for concurrency",
        "category": "preference",
        "importance": 0.85,
    }
    result = format_memory(metadata)
    assert "**Memory**:" in result
    assert "Use async/await for concurrency" in result
    assert "preference" in result
    assert "0.85" in result


def test_format_code() -> None:
    """Test code formatting."""
    metadata = {
        "unit_type": "function",
        "qualified_name": "foo.bar.baz",
        "file_path": "src/foo.py",
        "start_line": 42,
        "language": "python",
        "code": "def baz():\n    pass",
        "docstring": "Does something useful",
    }
    result = format_code(metadata)
    assert "**Function**" in result
    assert "foo.bar.baz" in result
    assert "src/foo.py:42" in result
    assert "```python" in result
    assert "def baz():" in result
    assert "Does something useful" in result


def test_format_code_no_docstring() -> None:
    """Test code formatting without docstring."""
    metadata = {
        "unit_type": "class",
        "qualified_name": "MyClass",
        "file_path": "src/module.py",
        "start_line": 10,
        "language": "python",
        "code": "class MyClass:\n    pass",
        "docstring": None,
    }
    result = format_code(metadata)
    assert "**Class**" in result
    assert "MyClass" in result
    assert '"""' not in result  # No docstring


def test_format_experience() -> None:
    """Test experience formatting."""
    metadata = {
        "domain": "debugging",
        "strategy": "systematic-elimination",
        "goal": "Fix bug",
        "hypothesis": "Null pointer issue",
        "action": "Added null check",
        "prediction": "Bug will be fixed",
        "outcome_status": "falsified",
        "outcome_result": "Still failing",
        "surprise": "Different root cause",
        "lesson": {"what_worked": "Need better diagnostics"},
    }
    result = format_experience(metadata)
    assert "**Experience**:" in result
    assert "debugging | systematic-elimination" in result
    assert "**Goal**: Fix bug" in result
    assert "**Hypothesis**: Null pointer issue" in result
    assert "**Action**: Added null check" in result
    assert "**Prediction**: Bug will be fixed" in result
    assert "**Outcome**: falsified - Still failing" in result
    assert "**Surprise**: Different root cause" in result
    assert "**Lesson**: Need better diagnostics" in result


def test_format_experience_no_optional_fields() -> None:
    """Test experience formatting without optional fields."""
    metadata = {
        "domain": "feature",
        "strategy": "incremental",
        "goal": "Add feature",
        "hypothesis": "Users want this",
        "action": "Implemented feature",
        "prediction": "Will be used",
        "outcome_status": "confirmed",
        "outcome_result": "Users love it",
        "surprise": None,
        "lesson": None,
    }
    result = format_experience(metadata)
    assert "**Experience**:" in result
    assert "**Surprise**:" not in result
    assert "**Lesson**:" not in result


def test_format_value() -> None:
    """Test value formatting."""
    metadata = {
        "axis": "strategy",
        "cluster_size": 42,
        "text": "Always verify assumptions before implementing",
    }
    result = format_value(metadata)
    assert "**Value**" in result
    assert "strategy" in result
    assert "cluster size: 42" in result
    assert "Always verify assumptions" in result


def test_format_commit() -> None:
    """Test commit formatting."""
    metadata = {
        "sha": "abc123def456",
        "author": "John Doe",
        "committed_at": "2024-01-15T10:30:00Z",
        "message": "Fix critical bug in auth",
        "files_changed": ["src/auth.py", "tests/test_auth.py"],
    }
    result = format_commit(metadata)
    assert "**Commit**" in result
    assert "abc123d" in result  # Shortened SHA
    assert "John Doe" in result
    assert "2024-01-15T10:30:00Z" in result
    assert "Fix critical bug in auth" in result
    assert "src/auth.py" in result
    assert "tests/test_auth.py" in result


def test_format_commit_many_files() -> None:
    """Test commit formatting with many files."""
    metadata = {
        "sha": "abc123",
        "author": "Jane Doe",
        "committed_at": "2024-01-15",
        "message": "Refactor",
        "files_changed": ["a.py", "b.py", "c.py", "d.py", "e.py"],
    }
    result = format_commit(metadata)
    assert "a.py" in result
    assert "b.py" in result
    assert "c.py" in result
    assert "... (2 more)" in result  # Shows only first 3


def test_assemble_markdown_standard() -> None:
    """Test standard markdown assembly."""
    items_by_source = {
        "memories": [
            ContextItem(
                "memory",
                "**Memory**: Test memory\n*Category: fact*",
                0.9,
                {},
            )
        ],
        "code": [
            ContextItem(
                "code",
                "**Function** `test` in `test.py:1`\n```python\ndef test(): pass\n```",
                0.8,
                {},
            )
        ],
    }

    result = assemble_markdown(items_by_source)

    assert "# Context" in result
    assert "## Memories" in result
    assert "## Code" in result
    assert "Test memory" in result
    assert "def test(): pass" in result
    assert "2 items from 2 sources" in result


def test_assemble_markdown_empty_sources() -> None:
    """Test markdown assembly omits empty sources."""
    items_by_source = {
        "memories": [
            ContextItem("memory", "**Memory**: Test", 0.9, {}),
        ],
        "code": [],  # Empty source
    }

    result = assemble_markdown(items_by_source)

    assert "## Memories" in result
    assert "## Code" not in result  # Omitted
    assert "1 items from 1 sources" in result


def test_assemble_markdown_premortem() -> None:
    """Test premortem markdown assembly."""
    items_by_source = {
        "experiences": [
            ContextItem(
                "experience",
                "**Experience**: debugging | systematic\n- **Goal**: Fix bug",
                0.9,
                {"axis": "full"},
            ),
            ContextItem(
                "experience",
                "**Experience**: debugging | systematic\n- **Surprise**: Unexpected",
                0.8,
                {"axis": "surprise"},
            ),
        ],
        "values": [
            ContextItem(
                "value",
                "**Value**: Always test assumptions",
                0.7,
                {},
            )
        ],
    }

    result = assemble_markdown(
        items_by_source, premortem=True, domain="debugging", strategy="systematic"
    )

    assert "# Premortem: debugging with systematic" in result
    assert "## Common Failures" in result
    assert "## Unexpected Outcomes" in result
    assert "## Relevant Principles" in result
    assert "Based on 2 past experiences" in result


def test_assemble_markdown_premortem_no_strategy() -> None:
    """Test premortem without strategy."""
    items_by_source = {
        "experiences": [],
        "values": [],
    }

    result = assemble_markdown(
        items_by_source, premortem=True, domain="feature", strategy=None
    )

    assert "# Premortem: feature" in result
    assert "with" not in result  # No strategy mentioned
    assert "Based on 0 past experiences" in result
