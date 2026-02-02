"""Tests for CALM orchestration counters module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.counters import (
    add_counter,
    get_counter,
    increment_counter,
    list_counters,
    reset_counter,
    set_counter,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


class TestListCounters:
    """Tests for list_counters function."""

    def test_list_default_counters(self, test_db: Path) -> None:
        """Test that default counters are initialized."""
        counters = list_counters(db_path=test_db)

        assert "merge_lock" in counters
        assert "merges_since_e2e" in counters
        assert "merges_since_docs" in counters
        assert counters["merge_lock"] == 0


class TestGetCounter:
    """Tests for get_counter function."""

    def test_get_existing_counter(self, test_db: Path) -> None:
        """Test getting an existing counter."""
        value = get_counter("merge_lock", db_path=test_db)
        assert value == 0

    def test_get_nonexistent_counter(self, test_db: Path) -> None:
        """Test getting a nonexistent counter returns 0."""
        value = get_counter("nonexistent", db_path=test_db)
        assert value == 0


class TestSetCounter:
    """Tests for set_counter function."""

    def test_set_existing_counter(self, test_db: Path) -> None:
        """Test setting an existing counter."""
        set_counter("merge_lock", 5, db_path=test_db)

        value = get_counter("merge_lock", db_path=test_db)
        assert value == 5

    def test_set_new_counter(self, test_db: Path) -> None:
        """Test setting a new counter creates it."""
        set_counter("new_counter", 10, db_path=test_db)

        value = get_counter("new_counter", db_path=test_db)
        assert value == 10


class TestIncrementCounter:
    """Tests for increment_counter function."""

    def test_increment_existing_counter(self, test_db: Path) -> None:
        """Test incrementing an existing counter."""
        new_value = increment_counter("merge_lock", db_path=test_db)
        assert new_value == 1

        new_value = increment_counter("merge_lock", db_path=test_db)
        assert new_value == 2

    def test_increment_new_counter(self, test_db: Path) -> None:
        """Test incrementing a new counter creates it."""
        new_value = increment_counter("new_counter", db_path=test_db)
        assert new_value == 1


class TestResetCounter:
    """Tests for reset_counter function."""

    def test_reset_counter(self, test_db: Path) -> None:
        """Test resetting a counter to 0."""
        set_counter("merge_lock", 10, db_path=test_db)
        reset_counter("merge_lock", db_path=test_db)

        value = get_counter("merge_lock", db_path=test_db)
        assert value == 0


class TestAddCounter:
    """Tests for add_counter function."""

    def test_add_new_counter(self, test_db: Path) -> None:
        """Test adding a new counter."""
        add_counter("custom_counter", 5, db_path=test_db)

        value = get_counter("custom_counter", db_path=test_db)
        assert value == 5

    def test_add_existing_counter_no_overwrite(self, test_db: Path) -> None:
        """Test that adding existing counter doesn't overwrite."""
        set_counter("test", 10, db_path=test_db)
        add_counter("test", 5, db_path=test_db)

        # Value should remain 10, not 5
        value = get_counter("test", db_path=test_db)
        assert value == 10
