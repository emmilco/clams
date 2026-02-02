"""Tests for UserPromptSubmit hook."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from calm.hooks.user_prompt_submit import (
    MAX_OUTPUT_CHARS,
    MAX_PROMPT_CHARS,
    format_context,
    get_relevant_experiences,
    get_relevant_memories,
    main,
)


class TestGetRelevantMemories:
    """Tests for get_relevant_memories function."""

    def test_no_memories(self, temp_db: Path) -> None:
        """Test returns empty list when no memories exist."""
        result = get_relevant_memories(temp_db, "test prompt")
        assert result == []

    def test_with_memories(self, db_with_memories: Path) -> None:
        """Test returns memories when they exist."""
        result = get_relevant_memories(db_with_memories, "test prompt")
        assert len(result) >= 1
        assert any(m["category"] == "error" for m in result)

    def test_filters_low_importance(self, temp_db: Path) -> None:
        """Test filters out low-importance memories."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (id, content, category, importance, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("low-imp", "Low importance memory", "fact", 0.2, "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

        result = get_relevant_memories(temp_db, "test prompt")
        assert not any(m["content"] == "Low importance memory" for m in result)

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns empty list when database doesn't exist."""
        result = get_relevant_memories(tmp_path / "nonexistent.db", "test prompt")
        assert result == []


class TestGetRelevantExperiences:
    """Tests for get_relevant_experiences function."""

    def test_no_experiences(self, temp_db: Path) -> None:
        """Test returns empty list when no experiences exist."""
        result = get_relevant_experiences(temp_db, "test prompt")
        assert result == []

    def test_with_experiences(self, db_with_resolved_experiences: Path) -> None:
        """Test returns experiences when they exist."""
        result = get_relevant_experiences(db_with_resolved_experiences, "test prompt")
        assert len(result) >= 1
        assert result[0]["outcome"] == "confirmed"

    def test_excludes_active_ghap(self, db_with_active_ghap: Path) -> None:
        """Test excludes active (non-resolved) GHAP entries."""
        result = get_relevant_experiences(db_with_active_ghap, "test prompt")
        # Active GHAP should not be included
        assert not any(e["outcome"] == "active" for e in result)

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns empty list when database doesn't exist."""
        result = get_relevant_experiences(tmp_path / "nonexistent.db", "test prompt")
        assert result == []


class TestFormatContext:
    """Tests for format_context function."""

    def test_empty_context(self) -> None:
        """Test returns empty string when no context."""
        result = format_context(memories=[], experiences=[])
        assert result == ""

    def test_with_memories(self) -> None:
        """Test formats memories correctly."""
        memories = [{"content": "Test memory", "category": "error"}]
        result = format_context(memories=memories, experiences=[])
        assert "## Relevant Context from Past Sessions" in result
        assert "### Memories" in result
        assert "[error] Test memory" in result

    def test_with_experiences(self) -> None:
        """Test formats experiences correctly."""
        experiences = [
            {"goal": "Fix bug", "hypothesis": "Bad config", "outcome": "confirmed", "domain": "debugging"}
        ]
        result = format_context(memories=[], experiences=experiences)
        assert "### Past Experiences" in result
        assert 'Similar debugging: "Fix bug" (confirmed)' in result

    def test_truncates_long_content(self) -> None:
        """Test truncates long memory content."""
        memories = [{"content": "x" * 200, "category": "fact"}]
        result = format_context(memories=memories, experiences=[])
        # Should be truncated to 100 chars + "..."
        assert "x" * 100 in result
        assert "x" * 101 + "..." not in result

    def test_truncates_long_goals(self) -> None:
        """Test truncates long experience goals."""
        experiences = [
            {"goal": "y" * 100, "hypothesis": "test", "outcome": "confirmed", "domain": "debugging"}
        ]
        result = format_context(memories=[], experiences=experiences)
        # Should be truncated to 60 chars + "..."
        assert "y" * 60 in result


class TestMain:
    """Tests for main entry point."""

    def test_empty_prompt(
        self,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing for empty prompt."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: temp_db)

        stdin = io.StringIO(json.dumps({"prompt": ""}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_whitespace_prompt(
        self,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing for whitespace-only prompt."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: temp_db)

        stdin = io.StringIO(json.dumps({"prompt": "   \n  "}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_no_relevant_context(
        self,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing when no relevant context."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: temp_db)

        stdin = io.StringIO(json.dumps({"prompt": "How do I fix this?"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        # No memories or experiences = no output
        assert stdout.getvalue() == ""

    def test_with_memories(
        self,
        db_with_memories: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs context when memories exist."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: db_with_memories)

        stdin = io.StringIO(json.dumps({"prompt": "How do I fix this?"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        output = stdout.getvalue()
        assert "Relevant Context" in output

    def test_missing_database(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing when database missing (silent failure)."""
        monkeypatch.setattr(
            "calm.hooks.user_prompt_submit.get_db_path",
            lambda: tmp_path / "nonexistent.db",
        )

        stdin = io.StringIO(json.dumps({"prompt": "test"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        # Silent failure - no output
        assert stdout.getvalue() == ""

    def test_output_character_limit(
        self,
        db_with_memories: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test output respects character limit."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: db_with_memories)

        stdin = io.StringIO(json.dumps({"prompt": "test"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        output = stdout.getvalue()
        assert len(output) <= MAX_OUTPUT_CHARS

    def test_prompt_truncation(
        self,
        db_with_memories: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test oversized prompts are truncated."""
        monkeypatch.setattr("calm.hooks.user_prompt_submit.get_db_path", lambda: db_with_memories)

        # Create a very long prompt
        long_prompt = "x" * (MAX_PROMPT_CHARS + 1000)
        stdin = io.StringIO(json.dumps({"prompt": long_prompt}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            # Should not crash even with oversized prompt
            main()
