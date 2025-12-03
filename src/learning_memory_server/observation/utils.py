"""Utility functions for observation collection."""

import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import structlog

from .models import ConfidenceTier, GHAPEntry, OutcomeStatus

logger = structlog.get_logger(__name__)


def generate_ghap_id() -> str:
    """
    Generate unique GHAP entry ID.

    Format: ghap_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: ghap_20251203_143022_a1b2c3
    """
    now = datetime.now(UTC)
    random_suffix = secrets.token_hex(3)  # 6 hex chars
    return f"ghap_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{random_suffix}"


def generate_session_id() -> str:
    """
    Generate unique session ID.

    Format: session_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: session_20251203_140000_x7y8z9
    """
    now = datetime.now(UTC)
    random_suffix = secrets.token_hex(3)
    return f"session_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{random_suffix}"


def compute_confidence_tier(entry: GHAPEntry) -> ConfidenceTier:
    """
    Compute confidence tier for a resolved GHAP entry.

    Simple tier assignment based on capture method:
    - ABANDONED: outcome.status is ABANDONED
    - GOLD: auto-captured outcome (test/build result triggered resolution)
    - SILVER: manual resolution (agent explicitly resolved)

    Note: Hypothesis quality assessment is NOT done here. Quality is assessed
    later by ObservationPersister (SPEC-002-14) using embeddings to detect
    semantic similarity between hypothesis and prediction (tautology detection)
    and other quality signals. This keeps the Collector simple and fast.

    If quality issues are discovered during retrospectives, adjustments can be
    made at retro time to elicit better observation data going forward.
    """
    if entry.outcome is None:
        raise ValueError("Cannot compute confidence tier for unresolved entry")

    if entry.outcome.status == OutcomeStatus.ABANDONED:
        return ConfidenceTier.ABANDONED

    if entry.outcome.auto_captured:
        return ConfidenceTier.GOLD

    return ConfidenceTier.SILVER


async def atomic_write(path: Path, content: str) -> None:
    """
    Write content to file atomically.

    Steps:
    1. Write to temporary file in same directory
    2. Sync to disk (fsync)
    3. Atomic rename to target path

    If process crashes during write, temp file is orphaned but original is intact.

    Args:
        path: Target file path
        content: Content to write

    Raises:
        JournalCorruptedError: On I/O errors (disk full, permissions, etc.)
    """
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        async with aiofiles.open(
            temp_path, "w", encoding="utf-8", errors="replace"
        ) as f:
            await f.write(content)
            await f.flush()
            os.fsync(f.fileno())
        os.rename(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            os.unlink(temp_path)
        raise


def truncate_text(text: str, max_length: int = 10000) -> str:
    """
    Truncate text to maximum length with warning.

    Args:
        text: Text to truncate
        max_length: Maximum allowed length (default: 10000)

    Returns:
        Truncated text if necessary
    """
    if len(text) <= max_length:
        return text

    logger.warning(
        "text_truncated",
        original_len=len(text),
        max_len=max_length,
    )
    return text[:max_length]
