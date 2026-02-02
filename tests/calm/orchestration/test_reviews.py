"""Tests for CALM orchestration reviews module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.reviews import (
    check_reviews,
    clear_reviews,
    list_reviews,
    record_review,
)
from calm.orchestration.tasks import create_task


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def task_with_db(test_db: Path) -> tuple[str, Path]:
    """Create a task and return (task_id, db_path)."""
    create_task(
        task_id="SPEC-001",
        title="Test Task",
        project_path="/test/project",
        db_path=test_db,
    )
    return "SPEC-001", test_db


class TestRecordReview:
    """Tests for record_review function."""

    def test_record_approved_review(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test recording an approved review."""
        task_id, db_path = task_with_db

        review = record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            worker_id="W-123",
            db_path=db_path,
        )

        assert review.task_id == task_id
        assert review.review_type == "spec"
        assert review.result == "approved"
        assert review.worker_id == "W-123"

    def test_record_changes_requested_clears_previous(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test that changes_requested clears previous reviews."""
        task_id, db_path = task_with_db

        # Record first approval
        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )

        # Record changes requested
        record_review(
            task_id=task_id,
            review_type="spec",
            result="changes_requested",
            db_path=db_path,
        )

        # Should only have the changes_requested review
        reviews = list_reviews(task_id, review_type="spec", db_path=db_path)
        assert len(reviews) == 1
        assert reviews[0].result == "changes_requested"

    def test_invalid_review_type_raises(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test that invalid review type raises error."""
        task_id, db_path = task_with_db

        with pytest.raises(ValueError, match="Invalid review type"):
            record_review(
                task_id=task_id,
                review_type="invalid",
                result="approved",
                db_path=db_path,
            )

    def test_invalid_result_raises(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test that invalid result raises error."""
        task_id, db_path = task_with_db

        with pytest.raises(ValueError, match="Invalid result"):
            record_review(
                task_id=task_id,
                review_type="spec",
                result="invalid",
                db_path=db_path,
            )


class TestListReviews:
    """Tests for list_reviews function."""

    def test_list_all_reviews(self, task_with_db: tuple[str, Path]) -> None:
        """Test listing all reviews for a task."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )
        record_review(
            task_id=task_id,
            review_type="proposal",
            result="approved",
            db_path=db_path,
        )

        reviews = list_reviews(task_id, db_path=db_path)
        assert len(reviews) == 2

    def test_list_reviews_by_type(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test filtering reviews by type."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )
        record_review(
            task_id=task_id,
            review_type="proposal",
            result="approved",
            db_path=db_path,
        )

        reviews = list_reviews(task_id, review_type="spec", db_path=db_path)
        assert len(reviews) == 1
        assert reviews[0].review_type == "spec"


class TestCheckReviews:
    """Tests for check_reviews function."""

    def test_check_reviews_pass(self, task_with_db: tuple[str, Path]) -> None:
        """Test that 2 approved reviews pass."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )
        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )

        passed, count = check_reviews(task_id, "spec", db_path=db_path)
        assert passed is True
        assert count == 2

    def test_check_reviews_fail_not_enough(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test that 1 approved review fails."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )

        passed, count = check_reviews(task_id, "spec", db_path=db_path)
        assert passed is False
        assert count == 1


class TestClearReviews:
    """Tests for clear_reviews function."""

    def test_clear_all_reviews(self, task_with_db: tuple[str, Path]) -> None:
        """Test clearing all reviews."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )
        record_review(
            task_id=task_id,
            review_type="proposal",
            result="approved",
            db_path=db_path,
        )

        count = clear_reviews(task_id, db_path=db_path)
        assert count == 2

        reviews = list_reviews(task_id, db_path=db_path)
        assert len(reviews) == 0

    def test_clear_reviews_by_type(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test clearing reviews by type."""
        task_id, db_path = task_with_db

        record_review(
            task_id=task_id,
            review_type="spec",
            result="approved",
            db_path=db_path,
        )
        record_review(
            task_id=task_id,
            review_type="proposal",
            result="approved",
            db_path=db_path,
        )

        count = clear_reviews(task_id, review_type="spec", db_path=db_path)
        assert count == 1

        reviews = list_reviews(task_id, db_path=db_path)
        assert len(reviews) == 1
        assert reviews[0].review_type == "proposal"
