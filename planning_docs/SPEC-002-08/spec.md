# SPEC-002-08: ObservationCollector

## Overview

Implement the local GHAP (Goal-Hypothesis-Action-Prediction) state machine for the Learning Memory Server. This component tracks agent working state during sessions, operating entirely on local JSON files with NO server dependencies.

## Dependencies

- `aiofiles` package (add to pyproject.toml)

## Key Design Decision

**ObservationCollector has NO dependency on the server.** It operates entirely on local files in `.claude/journal/`. This allows:
- Testing the GHAP state machine independently
- Operation even when server is unavailable
- Clear separation between collection (local) and persistence (server)

The separate `ObservationPersister` (SPEC-002-14) handles embedding and storing resolved entries to the server.

## Concurrency Model

**Single-process only in v1.** The ObservationCollector assumes only one Claude Code session accesses the journal directory at a time. No file locking is implemented. If multiple processes access the same journal:
- Race conditions may occur during file writes
- Data may be lost or corrupted

Future versions may add file locking if multi-process support is needed.

## Components

### ObservationCollector

**Purpose**: Track GHAP state locally during agent sessions.

**Interface**:
```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import secrets

class Domain(Enum):
    """Domain values match parent spec SPEC-001 exactly."""
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    FEATURE = "feature"
    TESTING = "testing"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"

class Strategy(Enum):
    """Strategy values match parent spec SPEC-001 exactly."""
    SYSTEMATIC_ELIMINATION = "systematic-elimination"
    TRIAL_AND_ERROR = "trial-and-error"
    RESEARCH_FIRST = "research-first"
    DIVIDE_AND_CONQUER = "divide-and-conquer"
    ROOT_CAUSE_ANALYSIS = "root-cause-analysis"
    COPY_FROM_SIMILAR = "copy-from-similar"
    CHECK_ASSUMPTIONS = "check-assumptions"
    READ_THE_ERROR = "read-the-error"
    ASK_USER = "ask-user"

class OutcomeStatus(Enum):
    CONFIRMED = "confirmed"
    FALSIFIED = "falsified"
    ABANDONED = "abandoned"

class ConfidenceTier(Enum):
    GOLD = "gold"      # Auto-captured outcome (test/build triggered resolution)
    SILVER = "silver"  # Manual resolution (agent explicitly resolved)
    BRONZE = "bronze"  # Poor quality hypothesis (assigned by Persister, not Collector)
    ABANDONED = "abandoned"  # Goal abandoned before resolution

@dataclass
class RootCause:
    category: str  # wrong-assumption, missing-knowledge, oversight, etc.
    description: str

@dataclass
class Lesson:
    what_worked: str
    takeaway: Optional[str] = None

@dataclass
class HistoryEntry:
    timestamp: datetime  # UTC, timezone-aware
    hypothesis: str
    action: str
    prediction: str

@dataclass
class Outcome:
    status: OutcomeStatus
    result: str
    captured_at: datetime  # UTC, timezone-aware
    auto_captured: bool = False

@dataclass
class GHAPEntry:
    id: str
    session_id: str
    created_at: datetime  # UTC, timezone-aware
    domain: Domain
    strategy: Strategy
    goal: str

    # Current state
    hypothesis: str
    action: str
    prediction: str

    # History of iterations
    history: list[HistoryEntry] = field(default_factory=list)
    iteration_count: int = 1

    # Resolution (filled when resolved)
    outcome: Optional[Outcome] = None
    surprise: Optional[str] = None
    root_cause: Optional[RootCause] = None
    lesson: Optional[Lesson] = None

    # Metadata
    confidence_tier: Optional[ConfidenceTier] = None
    notes: list[str] = field(default_factory=list)


class ObservationCollector:
    def __init__(self, journal_dir: Path):
        """
        Initialize collector with journal directory path.

        Creates directory if it doesn't exist.
        Uses aiofiles for all file I/O operations.
        """
        ...

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
        """
        Create a new GHAP entry.

        Raises:
            GHAPAlreadyActiveError: If a GHAP entry is already active
        """
        pass

    async def update_ghap(
        self,
        hypothesis: str | None = None,
        action: str | None = None,
        prediction: str | None = None,
        strategy: Strategy | None = None,
        note: str | None = None,
    ) -> GHAPEntry:
        """
        Update the current GHAP entry.

        State transition logic:
        - If any of hypothesis/action/prediction change:
          1. Push current (hypothesis, action, prediction) to history
          2. Update current values with new ones
          3. Increment iteration_count
        - If only note is provided, append to notes list
        - If only strategy changes, update strategy (no history entry)

        Raises:
            NoActiveGHAPError: If no GHAP entry is active
        """
        pass

    async def resolve_ghap(
        self,
        status: OutcomeStatus,
        result: str,
        surprise: str | None = None,
        root_cause: RootCause | None = None,
        lesson: Lesson | None = None,
        auto_captured: bool = False,
    ) -> GHAPEntry:
        """
        Resolve the current GHAP entry.

        Steps:
        1. Set outcome with status, result, captured_at, auto_captured
        2. Compute confidence tier
        3. Append entry to session_entries.jsonl
        4. Clear current_ghap.json
        5. Return the resolved entry

        Raises:
            NoActiveGHAPError: If no GHAP entry is active
        """
        pass

    async def abandon_ghap(self, reason: str) -> GHAPEntry:
        """
        Abandon the current GHAP without resolution.

        Sets outcome.status = ABANDONED, outcome.result = reason,
        confidence_tier = ABANDONED.

        Raises:
            NoActiveGHAPError: If no GHAP entry is active
        """
        pass

    # === State Access ===

    async def get_current(self) -> GHAPEntry | None:
        """Get the current active GHAP entry, or None if none active."""
        pass

    async def get_session_entries(self) -> list[GHAPEntry]:
        """Get all resolved entries from current session."""
        pass

    async def has_orphaned_entry(self) -> bool:
        """
        Check if there's an unresolved entry from a previous session.

        An entry is orphaned if current_ghap.json exists but its session_id
        doesn't match the current session.
        """
        pass

    async def get_orphaned_entry(self) -> GHAPEntry | None:
        """Get the orphaned entry if one exists."""
        pass

    async def adopt_orphan(self) -> GHAPEntry | None:
        """
        Adopt an orphaned entry as the current entry.

        - Updates session_id to current session
        - Preserves all other fields including timestamps
        - Returns the adopted entry, or None if no orphan exists
        """
        pass

    async def abandon_orphan(self, reason: str) -> GHAPEntry | None:
        """
        Abandon an orphaned entry without adopting it.

        - Sets outcome to ABANDONED with given reason
        - Archives to previous session's archive file
        - Clears current_ghap.json
        - Returns the abandoned entry, or None if no orphan exists
        """
        pass

    # === Session Management ===

    async def start_session(self) -> str:
        """
        Start a new session.

        - Generates session_id: "session_{YYYYMMDD}_{HHMMSS}_{random6}"
        - Archives previous session's entries if any
        - Writes session_id to .session_id file
        - Returns the new session_id
        """
        pass

    async def get_session_id(self) -> str | None:
        """Get current session ID, or None if no session started."""
        pass

    async def end_session(self) -> list[GHAPEntry]:
        """
        End the current session.

        - If current GHAP exists, abandon it with reason "session ended"
        - Archive session entries to archive/{date}_{session_id}.jsonl
        - Clear session_entries.jsonl
        - Clear .session_id
        - Return all entries from this session (including abandoned)
        """
        pass

    # === Tool Check-in ===

    async def increment_tool_count(self) -> int:
        """
        Increment tool call counter. Returns new count.

        Tool count persists across process restarts within a session.
        Count resets when session ends.
        """
        pass

    async def should_check_in(self, frequency: int = 10) -> bool:
        """
        Check if it's time for a GHAP check-in.

        Returns True if tool_count >= frequency AND a GHAP is active.
        """
        pass

    async def reset_tool_count(self) -> None:
        """Reset tool counter to 0 (call after check-in prompt shown)."""
        pass
```

## ID and Session ID Generation

```python
import secrets
from datetime import datetime, timezone

def generate_ghap_id() -> str:
    """
    Generate unique GHAP entry ID.

    Format: ghap_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: ghap_20251203_143022_a1b2c3
    """
    now = datetime.now(timezone.utc)
    random_suffix = secrets.token_hex(3)  # 6 hex chars
    return f"ghap_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{random_suffix}"

def generate_session_id() -> str:
    """
    Generate unique session ID.

    Format: session_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: session_20251203_140000_x7y8z9
    """
    now = datetime.now(timezone.utc)
    random_suffix = secrets.token_hex(3)
    return f"session_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{random_suffix}"
```

## Confidence Tier Calculation

```python
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
    if entry.outcome.status == OutcomeStatus.ABANDONED:
        return ConfidenceTier.ABANDONED

    if entry.outcome.auto_captured:
        return ConfidenceTier.GOLD

    return ConfidenceTier.SILVER
```

**Design Decision**: Hypothesis quality assessment is deferred to ObservationPersister.

The Collector's job is to accurately capture GHAP data. Quality assessment requires
semantic analysis (embedding similarity, tautology detection) which belongs in the
persistence layer where we have access to the EmbeddingService. This also allows
quality heuristics to evolve based on what we learn from retrospectives without
changing the Collector.

## File Structure

```
.claude/journal/
├── current_ghap.json      # Active GHAP state (single entry, atomic writes)
├── session_entries.jsonl  # Resolved entries this session (append-only)
├── .session_id            # Current session identifier (single line)
├── .tool_count            # Tool call counter (single integer)
└── archive/               # Past session entries
    ├── 20251201_session_20251201_140000_abc123.jsonl
    └── 20251202_session_20251202_093000_def456.jsonl
```

## Atomic File Operations

All file writes use atomic write pattern to prevent corruption:

```python
import aiofiles
import os
from pathlib import Path

async def atomic_write(path: Path, content: str) -> None:
    """
    Write content to file atomically.

    Steps:
    1. Write to temporary file in same directory
    2. Sync to disk (fsync)
    3. Atomic rename to target path

    If process crashes during write, temp file is orphaned but original is intact.
    """
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        async with aiofiles.open(temp_path, "w") as f:
            await f.write(content)
            await f.flush()
            os.fsync(f.fileno())
        os.rename(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            os.unlink(temp_path)
        raise
```

## Error Handling and Recovery

```python
class GHAPError(Exception):
    """Base exception for GHAP operations."""
    pass

class GHAPAlreadyActiveError(GHAPError):
    """Raised when trying to create GHAP while one is active."""
    pass

class NoActiveGHAPError(GHAPError):
    """Raised when trying to update/resolve with no active GHAP."""
    pass

class JournalCorruptedError(GHAPError):
    """Raised when journal files are corrupted."""
    pass
```

**Recovery strategy for corrupted files**:

```python
async def _load_current_ghap(self) -> GHAPEntry | None:
    """Load current GHAP with corruption recovery."""
    path = self.journal_dir / "current_ghap.json"

    if not path.exists():
        return None

    try:
        async with aiofiles.open(path) as f:
            content = await f.read()
        return GHAPEntry.from_json(content)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Corrupted file - backup and reset
        backup_path = path.with_suffix(f".corrupted.{int(time.time())}")
        os.rename(path, backup_path)
        logger.error(f"Corrupted GHAP file backed up to {backup_path}: {e}")
        return None
```

## JSON Schemas

All datetimes are serialized as ISO 8601 strings with UTC timezone (ending in "Z").

### current_ghap.json
```json
{
  "id": "ghap_20251203_143022_a1b2c3",
  "session_id": "session_20251203_140000_x7y8z9",
  "created_at": "2025-12-03T14:30:22Z",
  "domain": "debugging",
  "strategy": "systematic-elimination",
  "goal": "Fix flaky test in test_cache.py",
  "hypothesis": "The flakiness is caused by test pollution from previous test leaving cache state",
  "action": "Adding teardown to clean cache state between tests",
  "prediction": "Test will pass consistently when run in isolation and in sequence",
  "history": [
    {
      "timestamp": "2025-12-03T14:30:22Z",
      "hypothesis": "Timing issue with cache expiry check running before cache actually expires",
      "action": "Adding explicit sleep to allow cache expiry",
      "prediction": "Test passes with the added delay"
    }
  ],
  "iteration_count": 2,
  "notes": ["Checked logs, no timing issues visible in timestamps"]
}
```

### session_entries.jsonl (one complete JSON object per line)
```json
{"id": "ghap_20251203_141500_b2c3d4", "session_id": "session_20251203_140000_x7y8z9", "created_at": "2025-12-03T14:15:00Z", "domain": "feature", "strategy": "research-first", "goal": "Add pagination to API", "hypothesis": "...", "action": "...", "prediction": "...", "history": [], "iteration_count": 1, "outcome": {"status": "confirmed", "result": "Pagination works correctly", "captured_at": "2025-12-03T14:20:00Z", "auto_captured": false}, "confidence_tier": "silver", "notes": []}
```

## Input Validation

All text fields have the following constraints:
- Maximum length: 10,000 characters (truncated with warning if exceeded)
- Encoding: UTF-8 only (invalid sequences replaced with U+FFFD)
- Special characters: Preserved as-is (no sanitization needed for JSON)

## Acceptance Criteria

### Functional
1. Can create GHAP entry with all required fields
2. Update pushes old state to history, increments iteration (when H/A/P changes)
3. Update with only note/strategy doesn't create history entry
4. Resolve sets outcome, computes tier, moves to session entries
5. Abandon marks as abandoned with ABANDONED tier
6. Session management archives entries correctly
7. Orphan detection works across session boundaries
8. Orphan can be adopted (updates session_id) or abandoned
9. Tool count tracking works for check-in frequency
10. Tool count persists across process restarts within session

### State Machine
1. Cannot create GHAP when one is active (raises GHAPAlreadyActiveError)
2. Cannot update/resolve when none active (raises NoActiveGHAPError)
3. Cannot resolve already-resolved entry (it's no longer current)
4. Orphan from previous session can be adopted or abandoned

### Persistence
1. All state survives process restart
2. Atomic writes prevent corruption on crash
3. Corrupted files are backed up and reset
4. Archive files are append-only (via JSONL)
5. Journal directory created if missing

### Edge Cases
1. Missing journal directory: Created automatically
2. Corrupted current_ghap.json: Backed up, reset to no active GHAP
3. Corrupted session_entries.jsonl: Each line parsed independently, corrupt lines skipped
4. Very long text (>10k chars): Truncated with warning logged
5. Non-UTF8 in text: Invalid bytes replaced with U+FFFD

## Testing Strategy

### Unit Tests
- State machine transitions (create → update → resolve)
- Update with different field combinations (H/A/P vs note-only)
- Iteration counting and history tracking
- Confidence tier calculation (ABANDONED/GOLD/SILVER paths)
- Session management (start, end, archive)
- Orphan detection, adoption, and abandonment
- Tool count increment and check-in logic
- ID generation uniqueness

### Integration Tests
- Full session lifecycle (start → create → update → resolve → end)
- Process restart recovery (state persisted correctly)
- Crash recovery (atomic write verification)
- Archive file creation and format

### Test Fixtures
- Sample GHAP entries at various states
- Sample session archives
- Corrupted JSON files for recovery testing

## Expected Scale

- Typical session: 5-20 resolved GHAP entries
- Maximum expected: 200 entries per session
- Archive retention: Indefinite (no automatic cleanup in v1)
- Journal directory size: <1MB per session typically

## Out of Scope

- Server communication (that's ObservationPersister)
- Embedding generation
- Clustering
- Network operations
- Multi-process access (single-process only in v1)
- Archive cleanup/rotation

## Notes

- All file I/O via `aiofiles` for async operation
- All timestamps are UTC and timezone-aware (datetime with tzinfo=timezone.utc)
- Logging via `structlog` following existing codebase patterns
- Enum values match parent spec SPEC-001 exactly for compatibility
