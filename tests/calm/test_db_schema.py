"""Tests for CALM database schema."""

import sqlite3
from pathlib import Path

import pytest

from calm.db.schema import init_database


class TestInitDatabase:
    """Tests for init_database function."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Test that init_database creates the database file."""
        db_path = tmp_path / "test.db"
        assert not db_path.exists()

        init_database(db_path)

        assert db_path.exists()

    def test_creates_all_tables(self, tmp_path: Path) -> None:
        """Test that all tables are created."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "memories",
            "session_journal",
            "sessions",
            "ghap_entries",
            "tasks",
            "workers",
            "reviews",
            "test_runs",
            "counters",
            "phase_transitions",
            "gate_passes",
            "indexed_files",
            "git_index_state",
            "projects",
        }

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

    def test_creates_all_indexes(self, tmp_path: Path) -> None:
        """Test that all indexes are created."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get list of indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        # Check for key indexes
        expected_indexes = [
            "idx_memories_category",
            "idx_memories_importance",
            "idx_ghap_status",
            "idx_tasks_phase",
        ]

        for index in expected_indexes:
            assert index in indexes, f"Index {index} not found"

        conn.close()

    def test_initializes_counters(self, tmp_path: Path) -> None:
        """Test that default counters are initialized."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name, value FROM counters ORDER BY name")
        counters = {row[0]: row[1] for row in cursor.fetchall()}

        assert counters["merge_lock"] == 0
        assert counters["merges_since_e2e"] == 0
        assert counters["merges_since_docs"] == 0

        conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Test that init_database is idempotent."""
        db_path = tmp_path / "test.db"

        # Initialize twice
        init_database(db_path)
        init_database(db_path)

        # Should not raise and should still work
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM counters")
        count = cursor.fetchone()[0]
        assert count == 3  # Three default counters
        conn.close()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that init_database creates parent directories."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        assert not db_path.parent.exists()

        init_database(db_path)

        assert db_path.exists()


class TestTableConstraints:
    """Tests for table constraints."""

    def test_memories_category_constraint(self, tmp_path: Path) -> None:
        """Test that memories category constraint is enforced."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Valid category should work
        cursor.execute(
            "INSERT INTO memories (id, content, category, created_at) "
            "VALUES ('m1', 'test', 'fact', '2024-01-01')"
        )
        conn.commit()

        # Invalid category should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO memories (id, content, category, created_at) "
                "VALUES ('m2', 'test', 'invalid', '2024-01-01')"
            )

        conn.close()

    def test_ghap_status_constraint(self, tmp_path: Path) -> None:
        """Test that ghap_entries status constraint is enforced."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Valid status should work
        cursor.execute(
            "INSERT INTO ghap_entries "
            "(id, domain, strategy, goal, hypothesis, action, prediction, status, created_at) "
            "VALUES ('g1', 'debugging', 'trial', 'goal', 'hyp', 'act', 'pred', 'active', '2024-01-01')"
        )
        conn.commit()

        # Invalid status should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO ghap_entries "
                "(id, domain, strategy, goal, hypothesis, action, prediction, status, created_at) "
                "VALUES ('g2', 'debugging', 'trial', 'goal', 'hyp', 'act', 'pred', 'invalid', '2024-01-01')"
            )

        conn.close()

    def test_importance_range_constraint(self, tmp_path: Path) -> None:
        """Test that memories importance is constrained to 0.0-1.0."""
        db_path = tmp_path / "test.db"
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Valid importance should work
        cursor.execute(
            "INSERT INTO memories (id, content, category, importance, created_at) "
            "VALUES ('m1', 'test', 'fact', 0.5, '2024-01-01')"
        )
        conn.commit()

        # Importance > 1.0 should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO memories (id, content, category, importance, created_at) "
                "VALUES ('m2', 'test', 'fact', 1.5, '2024-01-01')"
            )

        conn.close()
