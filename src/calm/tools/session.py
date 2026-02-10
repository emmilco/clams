"""Session management tools for hooks.

These tools support the hook lifecycle without requiring heavy server resources.
Most operations are simple file I/O with in-memory counters.

Tools:
- start_session: Initialize a new session
- get_orphaned_ghap: Check for GHAP from previous session
- should_check_in: Check if GHAP reminder is due
- increment_tool_count: Increment tool counter
- reset_tool_count: Reset tool counter after reminder
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from calm.config import settings
from calm.ghap.utils import generate_session_id

from .validation import ValidationError

logger = structlog.get_logger()

# Module-level paths
CALM_DIR = settings.calm_dir
JOURNAL_DIR = settings.journal_dir


def get_session_id(session_id_file: Path | None = None) -> str | None:
    """Get the current session ID, checking env var first then file.

    Priority:
    1. CLAUDE_SESSION_ID environment variable (set by Claude Code)
    2. .session_id file in journal directory (set by ObservationCollector)

    Args:
        session_id_file: Override path to .session_id file (for testing).
            Defaults to JOURNAL_DIR / ".session_id".

    Returns:
        Session ID string, or None if not available from any source.
    """
    # Priority 1: Environment variable
    env_session = os.environ.get("CLAUDE_SESSION_ID")
    if env_session:
        return env_session

    # Priority 2: File-based session ID
    if session_id_file is None:
        session_id_file = JOURNAL_DIR / ".session_id"

    if session_id_file.exists():
        try:
            content = session_id_file.read_text().strip()
            return content if content else None
        except OSError:
            return None
    return None


def validate_frequency(value: int) -> None:
    """Validate frequency parameter.

    Args:
        value: Frequency value to validate

    Raises:
        ValidationError: If value is out of range
    """
    if not 1 <= value <= 1000:
        raise ValidationError(f"Frequency must be between 1 and 1000 (got {value})")


class SessionManager:
    """Manages session state for hooks.

    Tracks tool count in memory with file persistence for crash recovery.
    """

    def __init__(
        self,
        calm_dir: Path | None = None,
        journal_dir: Path | None = None,
    ) -> None:
        """Initialize session manager.

        Args:
            calm_dir: Override CALM directory (for testing)
            journal_dir: Override journal directory (for testing)
        """
        self.calm_dir = calm_dir or CALM_DIR
        self.journal_dir = journal_dir or JOURNAL_DIR
        self.session_id_file = self.journal_dir / ".session_id"
        self.tool_count_file = self.journal_dir / ".tool_count"
        self.current_ghap_file = self.journal_dir / "current_ghap.json"

        self._tool_count = 0
        self._load_tool_count()

    def _load_tool_count(self) -> None:
        """Load tool count from file."""
        if self.tool_count_file.exists():
            try:
                self._tool_count = int(self.tool_count_file.read_text().strip())
            except (ValueError, OSError):
                self._tool_count = 0

    def _save_tool_count(self) -> None:
        """Save tool count to file."""
        self.tool_count_file.parent.mkdir(parents=True, exist_ok=True)
        self.tool_count_file.write_text(str(self._tool_count))

    def get_current_session_id(self) -> str | None:
        """Get current session ID using unified resolution.

        Delegates to module-level get_session_id() which checks
        CLAUDE_SESSION_ID env var first, then falls back to file.

        Returns:
            Session ID or None if not set
        """
        return get_session_id(session_id_file=self.session_id_file)


def get_session_tools(session_manager: SessionManager) -> dict[str, Any]:
    """Get session tool implementations.

    Args:
        session_manager: SessionManager instance for state tracking

    Returns:
        Dictionary mapping tool names to async implementations
    """

    async def start_session() -> dict[str, Any]:
        """Initialize a new session.

        Uses CLAUDE_SESSION_ID env var if available, otherwise generates
        a session ID in ObservationCollector format (session_YYYYMMDD_HHMMSS_random6).

        Returns:
            Session info including session_id and started_at timestamp
        """
        # Use env var if available, otherwise generate in ObservationCollector format
        env_session = os.environ.get("CLAUDE_SESSION_ID")
        if env_session:
            session_id = env_session
        else:
            session_id = generate_session_id()

        # Write session ID to file (for ObservationCollector compatibility)
        session_manager.session_id_file.parent.mkdir(parents=True, exist_ok=True)
        session_manager.session_id_file.write_text(session_id)

        # Reset tool count for new session
        session_manager._tool_count = 0
        session_manager._save_tool_count()

        logger.info("session.started", session_id=session_id)
        return {
            "session_id": session_id,
            "started_at": datetime.now(UTC).isoformat(),
        }

    async def get_orphaned_ghap() -> dict[str, Any]:
        """Check for orphaned GHAP from previous session.

        A GHAP is considered orphaned if it belongs to a different session
        than the current one (i.e., the previous session ended without
        resolving the GHAP).

        Returns:
            Dict with has_orphan boolean, and if true, GHAP details
        """
        if not session_manager.current_ghap_file.exists():
            return {"has_orphan": False}

        try:
            ghap_data = json.loads(session_manager.current_ghap_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {"has_orphan": False}

        # Get current session ID
        current_session = session_manager.get_current_session_id()

        # Check if GHAP belongs to a different session
        ghap_session = ghap_data.get("session_id")
        if ghap_session and ghap_session != current_session:
            logger.info(
                "session.orphan_detected",
                ghap_session=ghap_session,
                current_session=current_session,
            )
            return {
                "has_orphan": True,
                "session_id": ghap_session,
                "goal": ghap_data.get("goal", "Unknown"),
                "hypothesis": ghap_data.get("hypothesis", "Unknown"),
                "action": ghap_data.get("action", "Unknown"),
                "prediction": ghap_data.get("prediction", "Unknown"),
                "created_at": ghap_data.get("created_at"),
            }

        return {"has_orphan": False}

    async def should_check_in(frequency: int = 10) -> dict[str, bool]:
        """Check if GHAP reminder is due.

        Args:
            frequency: Number of tool calls between reminders (default 10)

        Returns:
            Dict with should_check_in boolean

        Raises:
            ValidationError: If frequency is out of range (1-1000)
        """
        validate_frequency(frequency)
        should_remind = session_manager._tool_count >= frequency
        return {"should_check_in": should_remind}

    async def increment_tool_count() -> dict[str, int]:
        """Increment the tool counter.

        Called by hooks on each tool use to track progress toward
        GHAP check-in reminders.

        Returns:
            Dict with new tool_count
        """
        session_manager._tool_count += 1
        session_manager._save_tool_count()
        return {"tool_count": session_manager._tool_count}

    async def reset_tool_count() -> dict[str, int]:
        """Reset tool counter after showing reminder.

        Called after displaying a GHAP check-in reminder to restart
        the count for the next reminder cycle.

        Returns:
            Dict with tool_count (always 0)
        """
        session_manager._tool_count = 0
        session_manager._save_tool_count()
        return {"tool_count": 0}

    return {
        "start_session": start_session,
        "get_orphaned_ghap": get_orphaned_ghap,
        "should_check_in": should_check_in,
        "increment_tool_count": increment_tool_count,
        "reset_tool_count": reset_tool_count,
    }
