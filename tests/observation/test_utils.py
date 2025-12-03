"""Tests for observation utilities."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from learning_memory_server.observation.models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    Outcome,
    OutcomeStatus,
    Strategy,
)
from learning_memory_server.observation.utils import (
    atomic_write,
    compute_confidence_tier,
    generate_ghap_id,
    generate_session_id,
    truncate_text,
)


def test_generate_ghap_id() -> None:
    """Test GHAP ID generation format."""
    ghap_id = generate_ghap_id()
    assert ghap_id.startswith("ghap_")

    parts = ghap_id.split("_")
    assert len(parts) == 4
    assert parts[0] == "ghap"
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 6  # HHMMSS
    assert len(parts[3]) == 6  # random hex


def test_generate_ghap_id_uniqueness() -> None:
    """Test that generated GHAP IDs are unique."""
    ids = {generate_ghap_id() for _ in range(100)}
    assert len(ids) == 100


def test_generate_session_id() -> None:
    """Test session ID generation format."""
    session_id = generate_session_id()
    assert session_id.startswith("session_")

    parts = session_id.split("_")
    assert len(parts) == 4
    assert parts[0] == "session"
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 6  # HHMMSS
    assert len(parts[3]) == 6  # random hex


def test_generate_session_id_uniqueness() -> None:
    """Test that generated session IDs are unique."""
    ids = {generate_session_id() for _ in range(100)}
    assert len(ids) == 100


def test_compute_confidence_tier_abandoned() -> None:
    """Test confidence tier for abandoned entries."""
    entry = GHAPEntry(
        id="test",
        session_id="test",
        created_at=datetime.now(timezone.utc),
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="goal",
        hypothesis="h",
        action="a",
        prediction="p",
        outcome=Outcome(
            status=OutcomeStatus.ABANDONED,
            result="reason",
            captured_at=datetime.now(timezone.utc),
            auto_captured=False,
        ),
    )

    assert compute_confidence_tier(entry) == ConfidenceTier.ABANDONED


def test_compute_confidence_tier_gold() -> None:
    """Test confidence tier for auto-captured entries."""
    entry = GHAPEntry(
        id="test",
        session_id="test",
        created_at=datetime.now(timezone.utc),
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="goal",
        hypothesis="h",
        action="a",
        prediction="p",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="success",
            captured_at=datetime.now(timezone.utc),
            auto_captured=True,
        ),
    )

    assert compute_confidence_tier(entry) == ConfidenceTier.GOLD


def test_compute_confidence_tier_silver() -> None:
    """Test confidence tier for manual resolutions."""
    entry = GHAPEntry(
        id="test",
        session_id="test",
        created_at=datetime.now(timezone.utc),
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="goal",
        hypothesis="h",
        action="a",
        prediction="p",
        outcome=Outcome(
            status=OutcomeStatus.CONFIRMED,
            result="success",
            captured_at=datetime.now(timezone.utc),
            auto_captured=False,
        ),
    )

    assert compute_confidence_tier(entry) == ConfidenceTier.SILVER


def test_compute_confidence_tier_no_outcome() -> None:
    """Test confidence tier raises for unresolved entry."""
    entry = GHAPEntry(
        id="test",
        session_id="test",
        created_at=datetime.now(timezone.utc),
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="goal",
        hypothesis="h",
        action="a",
        prediction="p",
    )

    with pytest.raises(ValueError, match="unresolved entry"):
        compute_confidence_tier(entry)


async def test_atomic_write(tmp_path: Path) -> None:
    """Test atomic file write."""
    path = tmp_path / "test.json"
    content = '{"key": "value"}'

    await atomic_write(path, content)

    assert path.exists()
    assert path.read_text() == content


async def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    """Test atomic write overwrites existing file."""
    path = tmp_path / "test.json"
    path.write_text("old content")

    new_content = '{"key": "new value"}'
    await atomic_write(path, new_content)

    assert path.read_text() == new_content


async def test_atomic_write_cleans_up_temp_on_error(tmp_path: Path) -> None:
    """Test temp file is cleaned up on write error."""
    # Create a read-only directory to cause write error
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    path = readonly_dir / "test.json"

    try:
        await atomic_write(path, "content")
    except (OSError, PermissionError):
        pass  # Expected

    # Check no temp files left behind
    temp_files = list(readonly_dir.glob("*.tmp"))
    assert len(temp_files) == 0

    # Cleanup
    readonly_dir.chmod(0o755)


def test_truncate_text_short() -> None:
    """Test truncate_text with short text."""
    text = "short"
    assert truncate_text(text, max_length=100) == "short"


def test_truncate_text_exact_limit() -> None:
    """Test truncate_text with text at exact limit."""
    text = "x" * 100
    assert truncate_text(text, max_length=100) == text


def test_truncate_text_too_long() -> None:
    """Test truncate_text with text exceeding limit."""
    text = "x" * 200
    result = truncate_text(text, max_length=100)
    assert len(result) == 100
    assert result == "x" * 100


def test_truncate_text_unicode() -> None:
    """Test truncate_text with unicode characters."""
    text = "Hello 世界 🌍" * 100
    result = truncate_text(text, max_length=50)
    assert len(result) == 50
