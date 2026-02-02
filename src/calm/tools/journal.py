"""Session journal tools for MCP server."""

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import structlog

from calm.orchestration import journal as journal_ops

from .errors import MCPError
from .validation import ValidationError, validate_uuid

logger = structlog.get_logger()

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


def get_journal_tools(
    db_path: Path | None = None,
) -> dict[str, ToolFunc]:
    """Get journal tool implementations for the dispatcher.

    Args:
        db_path: Optional database path (for testing)

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def store_journal_entry(
        summary: str,
        working_directory: str,
        friction_points: list[str] | None = None,
        next_steps: list[str] | None = None,
        session_log_content: str | None = None,
    ) -> dict[str, Any]:
        """Store a new session journal entry with optional log capture."""
        logger.info("journal.store", working_directory=working_directory)

        # Validate inputs
        if not summary or not summary.strip():
            raise ValidationError("Summary is required and cannot be empty")
        if len(summary) > 10000:
            raise ValidationError(
                f"Summary too long ({len(summary)} chars). Maximum is 10000."
            )
        if not working_directory or not working_directory.strip():
            raise ValidationError("Working directory is required")
        if friction_points and len(friction_points) > 50:
            raise ValidationError("Maximum 50 friction points allowed")
        if next_steps and len(next_steps) > 50:
            raise ValidationError("Maximum 50 next steps allowed")

        try:
            entry_id, session_log_path = journal_ops.store_journal_entry(
                summary=summary,
                working_directory=working_directory,
                friction_points=friction_points,
                next_steps=next_steps,
                session_log_content=session_log_content,
                db_path=db_path,
            )

            logger.info("journal.stored", entry_id=entry_id)

            return {
                "id": entry_id,
                "session_log_path": session_log_path,
            }

        except Exception as e:
            logger.error("journal.store_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to store journal entry: {e}") from e

    async def list_journal_entries(
        unreflected_only: bool = False,
        project_name: str | None = None,
        working_directory: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List session journal entries with optional filters."""
        logger.info(
            "journal.list", unreflected_only=unreflected_only, limit=limit
        )

        # Validate limit
        if not 1 <= limit <= 200:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 200."
            )

        try:
            entries = journal_ops.list_journal_entries(
                unreflected_only=unreflected_only,
                project_name=project_name,
                working_directory=working_directory,
                limit=limit,
                db_path=db_path,
            )

            formatted = [
                {
                    "id": e.id,
                    "created_at": e.created_at.isoformat(),
                    "working_directory": e.working_directory,
                    "project_name": e.project_name,
                    "summary": e.summary,
                    "reflected_at": (
                        e.reflected_at.isoformat() if e.reflected_at else None
                    ),
                }
                for e in entries
            ]

            logger.info("journal.listed", count=len(formatted))

            return {"entries": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("journal.list_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to list journal entries: {e}") from e

    async def get_journal_entry(
        entry_id: str,
        include_log: bool = False,
    ) -> dict[str, Any]:
        """Get full details of a journal entry."""
        logger.info(
            "journal.get", entry_id=entry_id, include_log=include_log
        )

        # Validate UUID format
        validate_uuid(entry_id, "entry_id")

        try:
            entry = journal_ops.get_journal_entry(
                entry_id=entry_id,
                include_log=include_log,
                db_path=db_path,
            )

            if not entry:
                raise ValidationError(f"Entry {entry_id} not found")

            result: dict[str, Any] = {
                "id": entry.id,
                "created_at": entry.created_at.isoformat(),
                "working_directory": entry.working_directory,
                "project_name": entry.project_name,
                "session_log_path": entry.session_log_path,
                "summary": entry.summary,
                "friction_points": entry.friction_points,
                "next_steps": entry.next_steps,
                "reflected_at": (
                    entry.reflected_at.isoformat() if entry.reflected_at else None
                ),
                "memories_created": entry.memories_created,
            }

            if include_log and entry.session_log:
                result["session_log"] = entry.session_log

            logger.info("journal.got", entry_id=entry_id)

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error("journal.get_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to get journal entry: {e}") from e

    async def mark_entries_reflected(
        entry_ids: list[str],
        memories_created: int | None = None,
        delete_logs: bool = True,
    ) -> dict[str, Any]:
        """Mark entries as reflected and optionally delete their logs."""
        logger.info(
            "journal.mark_reflected",
            count=len(entry_ids),
            delete_logs=delete_logs,
        )

        # Validate inputs
        if not entry_ids:
            raise ValidationError("At least one entry ID is required")
        for eid in entry_ids:
            validate_uuid(eid, "entry_id")
        if memories_created is not None and memories_created < 0:
            raise ValidationError("memories_created must be >= 0")

        try:
            marked_count, logs_deleted = journal_ops.mark_entries_reflected(
                entry_ids=entry_ids,
                memories_created=memories_created,
                delete_logs=delete_logs,
                db_path=db_path,
            )

            logger.info(
                "journal.marked_reflected",
                marked_count=marked_count,
                logs_deleted=logs_deleted,
            )

            return {
                "marked_count": marked_count,
                "logs_deleted": logs_deleted,
            }

        except Exception as e:
            logger.error(
                "journal.mark_reflected_failed", error=str(e), exc_info=True
            )
            raise MCPError(f"Failed to mark entries reflected: {e}") from e

    return {
        "store_journal_entry": store_journal_entry,
        "list_journal_entries": list_journal_entries,
        "get_journal_entry": get_journal_entry,
        "mark_entries_reflected": mark_entries_reflected,
    }
