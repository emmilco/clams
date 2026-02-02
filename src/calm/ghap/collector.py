"""ObservationCollector for tracking GHAP state locally."""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import structlog

from .exceptions import (
    GHAPActiveError,
    GHAPNotFoundError,
    JournalCorruptedError,
)
from .models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    HistoryEntry,
    Lesson,
    Outcome,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from .utils import (
    atomic_write,
    compute_confidence_tier,
    generate_ghap_id,
    generate_session_id,
    truncate_text,
)

logger = structlog.get_logger(__name__)


class ObservationCollector:
    """Local GHAP state machine using file-based persistence."""

    def __init__(self, journal_dir: Path) -> None:
        """Initialize collector with journal directory path.

        Creates directory if it doesn't exist.
        Uses aiofiles for all file I/O operations.

        Args:
            journal_dir: Path to journal directory
        """
        self.journal_dir = Path(journal_dir).expanduser()
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.journal_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # === GHAP Lifecycle ===

    async def create_ghap(
        self,
        domain: Domain,
        strategy: Strategy,
        goal: str,
        hypothesis: str,
        action: str,
        prediction: str,
    ) -> GHAPEntry:
        """Create a new GHAP entry.

        Args:
            domain: Problem domain
            strategy: Strategy being used
            goal: What we're trying to achieve
            hypothesis: Current hypothesis
            action: Action being taken
            prediction: Expected outcome

        Returns:
            The created GHAP entry

        Raises:
            GHAPActiveError: If a GHAP entry is already active
        """
        # Check if already active
        current = await self.get_current()
        if current is not None:
            logger.warning("ghap_already_active", current_id=current.id)
            raise GHAPActiveError(
                f"GHAP entry {current.id} is already active"
            )

        # Get current session ID
        session_id = await self.get_session_id()
        if session_id is None:
            # Auto-start session if not started
            session_id = await self.start_session()

        # Create entry
        entry = GHAPEntry(
            id=generate_ghap_id(),
            session_id=session_id,
            created_at=datetime.now(UTC),
            domain=domain,
            strategy=strategy,
            goal=truncate_text(goal),
            hypothesis=truncate_text(hypothesis),
            action=truncate_text(action),
            prediction=truncate_text(prediction),
        )

        # Save to current_ghap.json
        await self._save_current_ghap(entry)

        logger.info(
            "ghap_created",
            ghap_id=entry.id,
            domain=entry.domain.value,
            strategy=entry.strategy.value,
        )

        return entry

    async def update_ghap(
        self,
        hypothesis: str | None = None,
        action: str | None = None,
        prediction: str | None = None,
        strategy: Strategy | None = None,
        note: str | None = None,
    ) -> GHAPEntry:
        """Update the current GHAP entry.

        State transition logic:
        - If any of hypothesis/action/prediction change:
          1. Push current (hypothesis, action, prediction) to history
          2. Update current values with new ones
          3. Increment iteration_count
        - If only note is provided, append to notes list
        - If only strategy changes, update strategy (no history entry)

        Args:
            hypothesis: New hypothesis (optional)
            action: New action (optional)
            prediction: New prediction (optional)
            strategy: New strategy (optional)
            note: Note to append (optional)

        Returns:
            The updated GHAP entry

        Raises:
            GHAPNotFoundError: If no GHAP entry is active
        """
        current = await self.get_current()
        if current is None:
            logger.warning("no_active_ghap_for_update")
            raise GHAPNotFoundError("No active GHAP entry to update")

        # Check if H/A/P are changing
        hap_changing = (
            (hypothesis is not None and hypothesis != current.hypothesis)
            or (action is not None and action != current.action)
            or (prediction is not None and prediction != current.prediction)
        )

        if hap_changing:
            # Push current state to history
            history_entry = HistoryEntry(
                timestamp=datetime.now(UTC),
                hypothesis=current.hypothesis,
                action=current.action,
                prediction=current.prediction,
            )
            current.history.append(history_entry)
            current.iteration_count += 1

            # Update current values
            if hypothesis is not None:
                current.hypothesis = truncate_text(hypothesis)
            if action is not None:
                current.action = truncate_text(action)
            if prediction is not None:
                current.prediction = truncate_text(prediction)

        # Update strategy if provided
        if strategy is not None:
            current.strategy = strategy

        # Append note if provided
        if note is not None:
            current.notes.append(truncate_text(note))

        # Save updated entry
        await self._save_current_ghap(current)

        logger.info(
            "ghap_updated",
            ghap_id=current.id,
            iteration=current.iteration_count,
            hap_changed=hap_changing,
        )

        return current

    async def resolve_ghap(
        self,
        status: OutcomeStatus,
        result: str,
        surprise: str | None = None,
        root_cause: RootCause | None = None,
        lesson: Lesson | None = None,
        auto_captured: bool = False,
    ) -> GHAPEntry:
        """Resolve the current GHAP entry.

        Steps:
        1. Set outcome with status, result, captured_at, auto_captured
        2. Compute confidence tier
        3. Append entry to session_entries.jsonl
        4. Clear current_ghap.json
        5. Return the resolved entry

        Args:
            status: Outcome status (CONFIRMED, FALSIFIED, ABANDONED)
            result: Description of the result
            surprise: Surprising aspect (optional)
            root_cause: Root cause analysis (optional)
            lesson: Lesson learned (optional)
            auto_captured: Whether this was auto-captured (default: False)

        Returns:
            The resolved GHAP entry

        Raises:
            GHAPNotFoundError: If no GHAP entry is active
        """
        current = await self.get_current()
        if current is None:
            logger.warning("no_active_ghap_for_resolve")
            raise GHAPNotFoundError("No active GHAP entry to resolve")

        # Set outcome
        current.outcome = Outcome(
            status=status,
            result=truncate_text(result),
            captured_at=datetime.now(UTC),
            auto_captured=auto_captured,
        )

        # Set optional fields
        if surprise is not None:
            current.surprise = truncate_text(surprise)
        if root_cause is not None:
            current.root_cause = root_cause
        if lesson is not None:
            current.lesson = lesson

        # Compute confidence tier
        current.confidence_tier = compute_confidence_tier(current)

        # Append to session entries
        await self._append_session_entry(current)

        # Clear current GHAP
        await self._clear_current_ghap()

        logger.info(
            "ghap_resolved",
            ghap_id=current.id,
            status=status.value,
            tier=current.confidence_tier.value,
            iterations=current.iteration_count,
        )

        return current

    async def abandon_ghap(self, reason: str) -> GHAPEntry:
        """Abandon the current GHAP without resolution.

        Sets outcome.status = ABANDONED, outcome.result = reason,
        confidence_tier = ABANDONED.

        Args:
            reason: Reason for abandonment

        Returns:
            The abandoned GHAP entry

        Raises:
            GHAPNotFoundError: If no GHAP entry is active
        """
        return await self.resolve_ghap(
            status=OutcomeStatus.ABANDONED,
            result=reason,
            auto_captured=False,
        )

    # === State Access ===

    async def get_current(self) -> GHAPEntry | None:
        """Get the current active GHAP entry, or None if none active.

        Returns:
            Current GHAP entry or None
        """
        return await self._load_current_ghap()

    async def get_session_entries(self) -> list[GHAPEntry]:
        """Get all resolved entries from current session.

        Returns:
            List of resolved GHAP entries
        """
        return await self._load_session_entries()

    async def has_orphaned_entry(self) -> bool:
        """Check if there's an unresolved entry from a previous session.

        An entry is orphaned if current_ghap.json exists but its session_id
        doesn't match the current session.

        Returns:
            True if orphaned entry exists, False otherwise
        """
        current = await self.get_current()
        if current is None:
            return False

        current_session = await self.get_session_id()
        return current.session_id != current_session

    async def get_orphaned_entry(self) -> GHAPEntry | None:
        """Get the orphaned entry if one exists.

        Returns:
            Orphaned GHAP entry or None
        """
        if await self.has_orphaned_entry():
            return await self.get_current()
        return None

    async def adopt_orphan(self) -> GHAPEntry | None:
        """Adopt an orphaned entry as the current entry.

        - Updates session_id to current session
        - Preserves all other fields including timestamps
        - Returns the adopted entry, or None if no orphan exists

        Returns:
            Adopted GHAP entry or None
        """
        orphan = await self.get_orphaned_entry()
        if orphan is None:
            return None

        current_session = await self.get_session_id()
        if current_session is None:
            current_session = await self.start_session()

        # Update session_id
        orphan.session_id = current_session

        # Save updated entry
        await self._save_current_ghap(orphan)

        logger.info(
            "orphan_adopted",
            ghap_id=orphan.id,
            new_session_id=current_session,
        )

        return orphan

    async def abandon_orphan(self, reason: str) -> GHAPEntry | None:
        """Abandon an orphaned entry without adopting it.

        - Sets outcome to ABANDONED with given reason
        - Archives to previous session's archive file
        - Clears current_ghap.json
        - Returns the abandoned entry, or None if no orphan exists

        Args:
            reason: Reason for abandonment

        Returns:
            Abandoned GHAP entry or None
        """
        orphan = await self.get_orphaned_entry()
        if orphan is None:
            return None

        # Set outcome
        orphan.outcome = Outcome(
            status=OutcomeStatus.ABANDONED,
            result=truncate_text(reason),
            captured_at=datetime.now(UTC),
            auto_captured=False,
        )
        orphan.confidence_tier = ConfidenceTier.ABANDONED

        # Archive to original session
        await self._archive_entry_to_session(orphan, orphan.session_id)

        # Clear current GHAP
        await self._clear_current_ghap()

        logger.info(
            "orphan_abandoned",
            ghap_id=orphan.id,
            original_session_id=orphan.session_id,
        )

        return orphan

    # === Session Management ===

    async def start_session(self) -> str:
        """Start a new session.

        - Generates session_id: "session_{YYYYMMDD}_{HHMMSS}_{random6}"
        - Archives previous session's entries if any
        - Writes session_id to .session_id file
        - Returns the new session_id

        Returns:
            New session ID
        """
        # Check if previous session exists
        old_session_id = await self.get_session_id()

        # Archive previous session if entries exist
        if old_session_id is not None:
            entries = await self.get_session_entries()
            if entries:
                await self._archive_session(old_session_id, entries)
                await self._clear_session_entries()

        # Generate new session ID
        new_session_id = generate_session_id()

        # Write to .session_id file
        session_path = self.journal_dir / ".session_id"
        await atomic_write(session_path, new_session_id)

        logger.info("session_started", session_id=new_session_id)

        return new_session_id

    async def get_session_id(self) -> str | None:
        """Get current session ID, or None if no session started.

        Returns:
            Current session ID or None
        """
        session_path = self.journal_dir / ".session_id"
        if not session_path.exists():
            return None

        try:
            async with aiofiles.open(
                session_path, encoding="utf-8", errors="replace"
            ) as f:
                session_id = (await f.read()).strip()
                return session_id if session_id else None
        except (OSError, PermissionError) as e:
            logger.error("error_reading_session_id", error=str(e))
            return None

    async def end_session(self) -> list[GHAPEntry]:
        """End the current session.

        - If current GHAP exists, abandon it with reason "session ended"
        - Archive session entries to archive/{date}_{session_id}.jsonl
        - Clear session_entries.jsonl
        - Clear .session_id
        - Return all entries from this session (including abandoned)

        Returns:
            All entries from this session
        """
        # Abandon current GHAP if exists
        current = await self.get_current()
        if current is not None:
            await self.abandon_ghap("session ended")

        # Get all session entries
        entries = await self.get_session_entries()

        # Archive if session ID exists
        session_id = await self.get_session_id()
        if session_id is not None and entries:
            await self._archive_session(session_id, entries)

        # Clear session files
        await self._clear_session_entries()

        session_path = self.journal_dir / ".session_id"
        if session_path.exists():
            os.unlink(session_path)

        # Clear tool count
        tool_count_path = self.journal_dir / ".tool_count"
        if tool_count_path.exists():
            os.unlink(tool_count_path)

        logger.info(
            "session_ended",
            session_id=session_id,
            entries_archived=len(entries),
        )

        return entries

    # === Tool Check-in ===

    async def increment_tool_count(self) -> int:
        """Increment tool call counter. Returns new count.

        Tool count persists across process restarts within a session.
        Count resets when session ends.

        Returns:
            New tool count
        """
        tool_count_path = self.journal_dir / ".tool_count"

        # Read current count
        current_count = 0
        if tool_count_path.exists():
            try:
                async with aiofiles.open(
                    tool_count_path, encoding="utf-8", errors="replace"
                ) as f:
                    content = (await f.read()).strip()
                    current_count = int(content) if content else 0
            except (ValueError, OSError):
                current_count = 0

        # Increment and save
        new_count = current_count + 1
        await atomic_write(tool_count_path, str(new_count))

        return new_count

    async def should_check_in(self, frequency: int = 10) -> bool:
        """Check if it's time for a GHAP check-in.

        Returns True if tool_count >= frequency AND a GHAP is active.

        Args:
            frequency: Check-in frequency (default: 10)

        Returns:
            True if check-in should happen, False otherwise
        """
        # Must have active GHAP
        current = await self.get_current()
        if current is None:
            return False

        # Check tool count
        tool_count_path = self.journal_dir / ".tool_count"
        if not tool_count_path.exists():
            return False

        try:
            async with aiofiles.open(
                tool_count_path, encoding="utf-8", errors="replace"
            ) as f:
                content = (await f.read()).strip()
                count = int(content) if content else 0
                return count >= frequency
        except (ValueError, OSError):
            return False

    async def reset_tool_count(self) -> None:
        """Reset tool counter to 0 (call after check-in prompt shown)."""
        tool_count_path = self.journal_dir / ".tool_count"
        await atomic_write(tool_count_path, "0")

    # === Internal Helpers ===

    async def _load_current_ghap(self) -> GHAPEntry | None:
        """Load current GHAP with corruption recovery."""
        path = self.journal_dir / "current_ghap.json"

        if not path.exists():
            return None

        try:
            async with aiofiles.open(
                path, encoding="utf-8", errors="replace"
            ) as f:
                content = await f.read()
            return GHAPEntry.from_dict(json.loads(content))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            # Corrupted file - backup and reset
            backup_path = path.with_suffix(f".corrupted.{int(time.time())}")
            os.rename(path, backup_path)
            logger.error(
                "corrupted_ghap_backed_up",
                file=str(path),
                backup=str(backup_path),
                error=str(e),
            )
            return None
        except PermissionError as e:
            logger.error("permission_denied_reading_ghap", path=str(path), error=str(e))
            raise JournalCorruptedError(f"Cannot read journal: {e}")
        except OSError as e:
            logger.error("io_error_reading_ghap", path=str(path), error=str(e))
            raise JournalCorruptedError(f"Journal I/O error: {e}")

    async def _save_current_ghap(self, entry: GHAPEntry) -> None:
        """Save current GHAP with error handling."""
        path = self.journal_dir / "current_ghap.json"
        try:
            await atomic_write(path, json.dumps(entry.to_dict(), indent=2))
            logger.debug("ghap_saved", ghap_id=entry.id)
        except PermissionError as e:
            logger.error(
                "permission_denied_writing_ghap", path=str(path), error=str(e)
            )
            raise JournalCorruptedError(f"Cannot write journal: {e}")
        except OSError as e:
            logger.error("io_error_writing_ghap", path=str(path), error=str(e))
            raise JournalCorruptedError(f"Journal write failed: {e}")

    async def _clear_current_ghap(self) -> None:
        """Clear current GHAP file."""
        path = self.journal_dir / "current_ghap.json"
        if path.exists():
            os.unlink(path)

    async def _load_session_entries(self) -> list[GHAPEntry]:
        """Load entries from JSONL with line-level error recovery."""
        entries: list[GHAPEntry] = []
        path = self.journal_dir / "session_entries.jsonl"

        if not path.exists():
            return []

        try:
            async with aiofiles.open(
                path, encoding="utf-8", errors="replace"
            ) as f:
                line_num = 0
                async for line in f:
                    line_num += 1
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(GHAPEntry.from_dict(json.loads(line)))
                    except (
                        json.JSONDecodeError,
                        KeyError,
                        ValueError,
                        TypeError,
                    ) as e:
                        logger.warning(
                            "corrupt_entry_skipped",
                            line_num=line_num,
                            error=str(e),
                        )
        except (OSError, PermissionError) as e:
            logger.error("error_reading_session_entries", error=str(e))
            # Return what we have so far
            return entries

        return entries

    async def _append_session_entry(self, entry: GHAPEntry) -> None:
        """Append entry to session_entries.jsonl."""
        path = self.journal_dir / "session_entries.jsonl"
        try:
            # Append mode - no need for atomic write since JSONL is append-only
            async with aiofiles.open(
                path, "a", encoding="utf-8", errors="replace"
            ) as f:
                await f.write(json.dumps(entry.to_dict()) + "\n")
        except (OSError, PermissionError) as e:
            logger.error("error_appending_session_entry", error=str(e))
            raise JournalCorruptedError(f"Cannot append to session entries: {e}")

    async def _clear_session_entries(self) -> None:
        """Clear session_entries.jsonl."""
        path = self.journal_dir / "session_entries.jsonl"
        if path.exists():
            os.unlink(path)

    async def _archive_session(
        self, session_id: str, entries: list[GHAPEntry]
    ) -> None:
        """Archive session entries to archive directory."""
        if not entries:
            return

        # Extract date from session_id (session_{YYYYMMDD}_...)
        parts = session_id.split("_")
        date_str = parts[1] if len(parts) > 1 else datetime.now(UTC).strftime("%Y%m%d")

        # Create archive filename
        archive_filename = f"{date_str}_{session_id}.jsonl"
        archive_path = self.archive_dir / archive_filename

        try:
            # Write entries as JSONL
            async with aiofiles.open(
                archive_path, "w", encoding="utf-8", errors="replace"
            ) as f:
                for entry in entries:
                    await f.write(json.dumps(entry.to_dict()) + "\n")

            logger.info(
                "session_archived",
                session_id=session_id,
                archive_file=archive_filename,
                entry_count=len(entries),
            )
        except (OSError, PermissionError) as e:
            logger.error(
                "error_archiving_session",
                session_id=session_id,
                error=str(e),
            )
            raise JournalCorruptedError(f"Cannot archive session: {e}")

    async def _archive_entry_to_session(
        self, entry: GHAPEntry, session_id: str
    ) -> None:
        """Archive a single entry to a specific session's archive file."""
        # Extract date from session_id
        parts = session_id.split("_")
        date_str = parts[1] if len(parts) > 1 else datetime.now(UTC).strftime("%Y%m%d")

        # Create archive filename
        archive_filename = f"{date_str}_{session_id}.jsonl"
        archive_path = self.archive_dir / archive_filename

        try:
            # Append to archive file
            async with aiofiles.open(
                archive_path, "a", encoding="utf-8", errors="replace"
            ) as f:
                await f.write(json.dumps(entry.to_dict()) + "\n")

            logger.info(
                "entry_archived_to_session",
                ghap_id=entry.id,
                session_id=session_id,
                archive_file=archive_filename,
            )
        except (OSError, PermissionError) as e:
            logger.error(
                "error_archiving_entry",
                ghap_id=entry.id,
                error=str(e),
            )
            raise JournalCorruptedError(f"Cannot archive entry: {e}")
