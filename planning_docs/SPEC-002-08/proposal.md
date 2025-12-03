# Technical Proposal: ObservationCollector

## Problem Statement

We need a local GHAP (Goal-Hypothesis-Action-Prediction) state machine to track agent working state during Claude Code sessions. The component must:

1. **Operate entirely on local files** - No server dependencies, enabling standalone operation and testing
2. **Persist across process restarts** - State survives crashes and session interruptions
3. **Handle state transitions** - Track GHAP lifecycle from creation through resolution
4. **Support session management** - Separate entries across distinct Claude Code sessions
5. **Enable check-in prompts** - Track tool calls to determine when to prompt for GHAP updates
6. **Recover from corruption** - Gracefully handle corrupted files from crashes

## Proposed Solution

### Architecture Overview

```
observation/
├── __init__.py          # Public exports (see below)
├── collector.py         # ObservationCollector class
├── models.py            # Dataclasses (GHAPEntry, Outcome, etc.)
├── exceptions.py        # Custom exceptions
└── utils.py             # ID generation, atomic writes

**`__init__.py` exports:**
```python
"""Observation collection module for GHAP state tracking."""

from .collector import ObservationCollector
from .models import (
    Domain,
    Strategy,
    OutcomeStatus,
    ConfidenceTier,
    RootCause,
    Lesson,
    HistoryEntry,
    Outcome,
    GHAPEntry,
)
from .exceptions import (
    GHAPError,
    GHAPAlreadyActiveError,
    NoActiveGHAPError,
    JournalCorruptedError,
)

__all__ = [
    "ObservationCollector",
    "Domain",
    "Strategy",
    "OutcomeStatus",
    "ConfidenceTier",
    "RootCause",
    "Lesson",
    "HistoryEntry",
    "Outcome",
    "GHAPEntry",
    "GHAPError",
    "GHAPAlreadyActiveError",
    "NoActiveGHAPError",
    "JournalCorruptedError",
]
```

The solution implements a **file-based state machine** using JSON for persistence. All operations are async using `aiofiles` for non-blocking I/O, consistent with the existing codebase patterns.

### File Organization

#### Module Structure

**`models.py`** - Core data structures
- `Domain`, `Strategy`, `OutcomeStatus`, `ConfidenceTier` enums
- `RootCause`, `Lesson`, `HistoryEntry` dataclasses
- `Outcome`, `GHAPEntry` dataclasses
- JSON serialization/deserialization methods (from_dict, to_dict)
- DateTime handling: **UTC timezone-aware throughout**

**Datetime Strategy**:
All datetime fields use UTC timezone-aware datetimes:
```python
from datetime import datetime, timezone

# Creation
created_at = datetime.now(timezone.utc)

# Serialization (ISO 8601 with 'Z' suffix)
def to_dict(self) -> dict:
    return {"created_at": self.created_at.isoformat().replace("+00:00", "Z")}

# Deserialization
def from_dict(cls, data: dict) -> Self:
    # Handle both 'Z' suffix and '+00:00' format
    ts = data["created_at"].replace("Z", "+00:00")
    return cls(created_at=datetime.fromisoformat(ts))
```

**Note**: The existing codebase uses timezone-naive datetimes in some places (e.g., metadata.py).
This module establishes UTC-aware as the standard for new code. Conversion happens at boundaries
if needed when integrating with existing components.

**`exceptions.py`** - Error types
- `GHAPError` (base)
- `GHAPAlreadyActiveError`
- `NoActiveGHAPError`
- `JournalCorruptedError`

**`utils.py`** - Helper functions
- `generate_ghap_id()` - Format: `ghap_{YYYYMMDD}_{HHMMSS}_{random6}`
- `generate_session_id()` - Format: `session_{YYYYMMDD}_{HHMMSS}_{random6}`
- `compute_confidence_tier(entry)` - Tier assignment logic
- `atomic_write(path, content)` - Safe file writes
- `truncate_text(text, max_length)` - Validation helper

**`collector.py`** - Main class
- `ObservationCollector` implementation
- All async methods from spec interface
- Internal helpers: `_load_current_ghap()`, `_save_current_ghap()`, etc.
- Structured logging using `structlog`

### Key Design Decisions

#### 1. Atomic File Writes

All file writes use a temp-file-and-rename pattern to prevent corruption:

```python
async def atomic_write(path: Path, content: str) -> None:
    """Write atomically: temp file → fsync → rename."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            await f.write(content)
            await f.flush()
            os.fsync(f.fileno())
        os.rename(temp_path, path)
    except Exception:
        if temp_path.exists():
            os.unlink(temp_path)
        raise
```

**Rationale**: The rename operation is atomic on POSIX systems, ensuring readers never see partial writes. If a crash occurs during write, the original file remains intact.

#### 2. JSON Line Format for Entries

Resolved entries are stored in JSONL (JSON Lines) format - one complete JSON object per line:

```python
# session_entries.jsonl
{"id": "ghap_...", "session_id": "...", ...}\n
{"id": "ghap_...", "session_id": "...", ...}\n
```

**Rationale**:
- **Append efficiency** - No need to read/parse entire file for appends
- **Corruption isolation** - Single corrupt line doesn't invalidate entire file
- **Stream processing** - Can process entries line-by-line without loading all into memory
- **Standard format** - Well-supported, simple parsing

#### 3. Separate Files for Different Concerns

```
.claude/journal/
├── current_ghap.json      # Active state (single entry)
├── session_entries.jsonl  # Resolved entries (append-only)
├── .session_id            # Current session (single line)
├── .tool_count            # Tool counter (single integer)
└── archive/               # Past sessions
```

**Rationale**:
- **Current state** needs frequent read/write → separate file
- **Session entries** are append-only → JSONL optimized for this
- **Metadata files** (session_id, tool_count) are tiny → separate for clarity
- **Archive** keeps historical data without cluttering active files

#### 4. Corruption and I/O Error Recovery Strategy

```python
async def _load_current_ghap(self) -> GHAPEntry | None:
    """Load with automatic corruption and I/O error recovery."""
    try:
        # Normal load path
        async with aiofiles.open(path) as f:
            content = await f.read()
        return GHAPEntry.from_json(content)
    except FileNotFoundError:
        return None  # No active GHAP
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Backup corrupted file and reset
        backup = path.with_suffix(f".corrupted.{int(time.time())}")
        os.rename(path, backup)
        logger.error("Corrupted GHAP backed up", backup=str(backup), error=str(e))
        return None
    except PermissionError as e:
        logger.error("Permission denied reading GHAP", path=str(path), error=str(e))
        raise JournalCorruptedError(f"Cannot read journal: {e}")
    except OSError as e:
        # Disk full, I/O error, etc.
        logger.error("I/O error reading GHAP", path=str(path), error=str(e))
        raise JournalCorruptedError(f"Journal I/O error: {e}")
```

**I/O Error Handling Strategy**:
- **FileNotFoundError**: Normal case (no active GHAP), return None
- **PermissionError**: Raise `JournalCorruptedError` - user must fix permissions
- **OSError (disk full, etc.)**: Raise `JournalCorruptedError` - user must free space
- **JSON corruption**: Backup file, reset to clean state, log error
- All errors logged with structured context for debugging

**Rationale**:
- **Fail-safe** - Corruption doesn't crash the system
- **Evidence preservation** - Corrupted files saved for debugging
- **Automatic recovery** - System continues with clean state
- **Logging** - All corruption events logged for investigation

#### 5. Session Management

Sessions provide isolation between different Claude Code sessions:

```python
async def start_session(self) -> str:
    """
    1. Generate unique session ID
    2. Archive previous session's entries (if any)
    3. Write new session ID
    4. Return session ID
    """

async def end_session(self) -> list[GHAPEntry]:
    """
    End session and archive entries.

    Archive filename format: {YYYYMMDD}_{session_id}.jsonl
    Example: 20251203_session_20251203_140000_abc123.jsonl

    Steps:
    1. If current GHAP exists, abandon with reason "session ended"
    2. Read all entries from session_entries.jsonl
    3. Write to archive/{YYYYMMDD}_{session_id}.jsonl
    4. Clear session_entries.jsonl
    5. Clear .session_id
    6. Return all archived entries
    """
```

**Rationale**:
- **Isolation** - Entries from different sessions kept separate
- **Continuity** - Can detect orphaned entries from crashed sessions
- **Auditability** - Complete history preserved in archive
- **Recovery** - Orphaned entries can be adopted or abandoned

#### 6. Tool Count Tracking

```python
async def increment_tool_count(self) -> int:
    """Increment counter, persist to .tool_count file."""

async def should_check_in(self, frequency: int = 10) -> bool:
    """Returns True when count >= frequency AND GHAP active."""
```

**Rationale**:
- **Decoupled** - Collector doesn't trigger prompts, just provides signal
- **Persistent** - Count survives process restarts within session
- **Configurable** - Frequency adjustable per deployment
- **Conditional** - Only prompts when there's actually a GHAP to update

### Implementation Details

#### JSON Serialization

All dataclasses implement:

```python
@dataclass
class GHAPEntry:
    # ... fields ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),  # ISO 8601 with 'Z'
            "domain": self.domain.value,
            "strategy": self.strategy.value,
            # ... etc
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GHAPEntry":
        """Parse from dict with validation."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            domain=Domain(data["domain"]),
            # ... etc
        )
```

**Rationale**:
- **Type safety** - Validation at parse time
- **Standard format** - ISO 8601 timestamps
- **Extensibility** - Easy to add fields with defaults
- **Testability** - Clear contract for serialization

#### Update Logic (State Transitions)

```python
async def update_ghap(
    self,
    hypothesis: str | None = None,
    action: str | None = None,
    prediction: str | None = None,
    strategy: Strategy | None = None,
    note: str | None = None,
) -> GHAPEntry:
    """
    If H/A/P changes:
      1. Push current (H, A, P) to history with timestamp
      2. Update current values
      3. Increment iteration_count

    If only note: append to notes list
    If only strategy: update strategy field
    """
```

**Rationale**: History preserves the complete reasoning chain, enabling:
- **Retrospective analysis** - See how thinking evolved
- **Pattern detection** - Identify common iteration paths
- **Quality assessment** - Detect thrashing or convergence

#### Confidence Tier Assignment

```python
def compute_confidence_tier(entry: GHAPEntry) -> ConfidenceTier:
    """
    Simple rule-based assignment:
    - ABANDONED if outcome.status == ABANDONED
    - GOLD if outcome.auto_captured == True
    - SILVER otherwise (all manual resolutions start as SILVER)

    BRONZE tier is NOT assigned here. It is assigned later by
    ObservationPersister (SPEC-002-14) during quality assessment:
    - Persister uses embeddings to detect tautologies (hypothesis ≈ prediction)
    - Persister may downgrade SILVER → BRONZE based on semantic analysis
    - This keeps Collector simple and server-independent
    """

    if entry.outcome.status == OutcomeStatus.ABANDONED:
        return ConfidenceTier.ABANDONED

    if entry.outcome.auto_captured:
        return ConfidenceTier.GOLD

    # All manual resolutions start as SILVER
    # May be downgraded to BRONZE by Persister during quality assessment
    return ConfidenceTier.SILVER
```

**Tier Assignment Summary**:
| Tier | Assigned By | Criteria |
|------|-------------|----------|
| ABANDONED | Collector | `outcome.status == ABANDONED` |
| GOLD | Collector | `outcome.auto_captured == True` |
| SILVER | Collector | All other resolutions (default) |
| BRONZE | Persister | SILVER entries with poor quality (tautology, vague) |

**Rationale**:
- **Separation of concerns** - Collector captures data, Persister assesses quality
- **No dependencies** - Collector has no need for embeddings or semantic analysis
- **Fast** - Simple boolean checks at collection time
- **Upgradeable** - Can refine quality heuristics in Persister without changing Collector

#### Orphan Handling

```python
async def has_orphaned_entry(self) -> bool:
    """Entry is orphaned if session_id doesn't match current."""

async def adopt_orphan(self) -> GHAPEntry | None:
    """Update session_id to current, preserve all other fields."""

async def abandon_orphan(self, reason: str) -> GHAPEntry | None:
    """Mark as abandoned, archive to original session."""
```

**Rationale**:
- **Explicit recovery** - Caller decides whether to continue or abandon
- **Preserve context** - Adopted entries keep original timestamps
- **Auditability** - Orphans archived with clear resolution

### Testing Strategy

#### Unit Tests (Fast, No I/O Mocking)

Use `pytest-asyncio` with `tmp_path` fixtures for real file I/O:

```python
@pytest.fixture
async def journal_dir(tmp_path: Path) -> Path:
    """Create isolated journal directory."""
    return tmp_path / "journal"

@pytest.fixture
async def collector(journal_dir: Path) -> ObservationCollector:
    """Create collector with temp directory."""
    return ObservationCollector(journal_dir)

async def test_create_ghap(collector: ObservationCollector):
    """Test GHAP creation."""
    entry = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test failure",
        hypothesis="Cache pollution",
        action="Add teardown",
        prediction="Test passes consistently"
    )

    assert entry.id.startswith("ghap_")
    assert entry.iteration_count == 1
    assert await collector.get_current() == entry
```

**Test Categories**:

1. **State Machine** - All valid transitions
2. **Error Cases** - Creating when active, updating when none active
3. **Persistence** - State survives collector recreation
4. **History** - Updates push to history correctly
5. **Sessions** - Start, end, archive, orphan detection
6. **Tool Counting** - Increment, check-in logic, reset
7. **Corruption Recovery** - Invalid JSON, missing fields
8. **Edge Cases** - Empty strings, very long text, unicode

#### Integration Tests (Full Lifecycle)

```python
async def test_full_session_lifecycle(journal_dir: Path):
    """Test complete session from start to end."""
    collector = ObservationCollector(journal_dir)

    # Start session
    session_id = await collector.start_session()

    # Create and resolve multiple GHAPs
    for i in range(3):
        entry = await collector.create_ghap(...)
        await collector.resolve_ghap(
            status=OutcomeStatus.CONFIRMED,
            result=f"Success {i}"
        )

    # End session
    entries = await collector.end_session()
    assert len(entries) == 3

    # Verify archive created
    archives = list((journal_dir / "archive").glob("*.jsonl"))
    assert len(archives) == 1
```

#### Property-Based Tests (Optional)

Use `hypothesis` for property testing:

```python
@given(
    text=st.text(min_size=1, max_size=20000),
    domain=st.sampled_from(Domain),
    strategy=st.sampled_from(Strategy)
)
async def test_create_with_arbitrary_inputs(
    collector, text, domain, strategy
):
    """Test creation with arbitrary valid inputs."""
    entry = await collector.create_ghap(
        domain=domain,
        strategy=strategy,
        goal=text,
        hypothesis=text,
        action=text,
        prediction=text
    )

    # Should never raise, text should be truncated if needed
    assert len(entry.goal) <= 10000
```

### Performance Considerations

#### Expected Load
- Typical session: 5-20 GHAP entries
- Maximum expected: 200 entries/session
- Archive size: ~1MB/session typical
- File ops: ~10-50/session (creation, updates, resolution)

#### Optimization Strategies
1. **Lazy loading** - Only load current GHAP on demand
2. **No caching** - Single process, fresh reads ensure consistency
3. **Async I/O** - All operations non-blocking via `aiofiles`
4. **Minimal parsing** - JSONL allows appending without parsing entire file

#### Scalability Notes
- **Single process only** - No file locking in v1
- **No concurrent writers** - One Claude Code session per journal
- **Archive growth** - Unbounded in v1 (manual cleanup)
- **Future: Multi-process** - Could add file locking with `fcntl`

### Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "aiofiles>=23.0.0",
]
```

No additional dependencies needed - `structlog` already present.

### Logging Strategy

Use structured logging with `structlog` (consistent with existing code):

```python
import structlog

logger = structlog.get_logger(__name__)

# Log key events
logger.info("ghap_created",
    ghap_id=entry.id,
    domain=entry.domain.value,
    strategy=entry.strategy.value
)

logger.warning("ghap_already_active", current_id=current.id)

logger.error("journal_corrupted",
    file=str(path),
    error=str(e),
    backup=str(backup_path)
)
```

**Rationale**: Structured logs enable:
- **Querying** - Filter by ghap_id, domain, etc.
- **Analysis** - Track patterns across sessions
- **Debugging** - Rich context for troubleshooting
- **Consistency** - Matches existing codebase patterns

### Migration Path

Initial implementation (v1):
- Single process only
- No file locking
- Manual archive cleanup
- Simple tier assignment

Future enhancements (v2+):
- File locking for multi-process safety
- Automatic archive rotation/compression
- Enhanced quality assessment at collection time
- Streaming API for large session histories
- SQLite index for fast session queries

### Alternatives Considered

#### 1. SQLite Instead of JSON Files

**Pros**:
- ACID transactions
- Concurrent access with locking
- Indexed queries
- Compact storage

**Cons**:
- More complex setup
- Harder to inspect/debug
- Requires migration tooling
- Overkill for single-process access

**Decision**: JSON files for v1 (simpler, inspectable, sufficient for current needs). SQLite can be added in v2 if multi-process support is needed.

#### 2. Single JSON File for All Entries

**Pros**:
- Simple structure
- Atomic reads/writes of entire state

**Cons**:
- Must parse entire file for appends
- Large files slow to parse
- Corruption affects all entries

**Decision**: JSONL format gives append efficiency with corruption isolation.

#### 3. Sync I/O Instead of Async

**Pros**:
- Simpler code
- No async/await complexity

**Cons**:
- Blocks event loop
- Inconsistent with existing codebase
- Poor performance with multiple operations

**Decision**: Async I/O matches existing patterns and enables future optimizations.

#### 4. Quality Assessment in Collector

**Pros**:
- Immediate feedback
- Single pass through data

**Cons**:
- Requires embedding service dependency
- Slower collection operations
- Couples collection with analysis

**Decision**: Defer quality assessment to ObservationPersister. Keeps Collector fast and focused on capture.

## Implementation Plan

### Phase 1: Core Data Models (Est: 2 hours)
- [ ] Create `models.py` with all dataclasses
- [ ] Implement `to_dict()` / `from_dict()` methods
- [ ] Add JSON serialization tests
- [ ] Validate enum values match parent spec

### Phase 2: Utilities (Est: 1 hour)
- [ ] Implement `utils.py` with ID generation
- [ ] Implement `atomic_write()` function
- [ ] Add `compute_confidence_tier()` logic
- [ ] Test ID uniqueness and atomic writes

### Phase 3: Collector Implementation (Est: 4 hours)
- [ ] Create `collector.py` with class structure
- [ ] Implement GHAP lifecycle methods
- [ ] Implement session management
- [ ] Add tool count tracking
- [ ] Implement orphan handling

### Phase 4: Error Handling (Est: 1 hour)
- [ ] Create `exceptions.py` with error types
- [ ] Add corruption recovery logic
- [ ] Test error conditions

### Phase 5: Testing (Est: 4 hours)
- [ ] Unit tests for all public methods
- [ ] Integration tests for full lifecycle
- [ ] Edge case tests (corruption, long text, etc.)
- [ ] Property-based tests (optional)

### Phase 6: Documentation (Est: 1 hour)
- [ ] Docstrings for all public APIs
- [ ] Update module `__init__.py` exports
- [ ] Add usage examples in docstrings

**Total Estimate**: ~13 hours

## Open Questions

1. **Archive Cleanup**: Should we implement automatic archive rotation/cleanup in v1, or defer to manual cleanup?
   - **Recommendation**: Defer to v2. Document manual cleanup process. Disk space unlikely to be an issue (<1MB/session).

2. **Tool Count Persistence**: Current plan stores in `.tool_count` file. Alternative is in-memory only (reset on restart).
   - **Recommendation**: Persist to file. Prevents spurious check-ins after restart when GHAP is still active.

3. **Validation Strictness**: Should we raise errors for very long text (>10k chars) or silently truncate?
   - **Recommendation**: Truncate with warning log. Better UX than failing the operation.

4. **Timestamp Precision**: ISO 8601 format includes microseconds. Needed for sorting?
   - **Recommendation**: Keep microseconds. Helps with debugging and uniqueness in rare cases.

## Success Criteria

Implementation is complete when:

1. ✅ All acceptance criteria from spec are met
2. ✅ Test coverage ≥ 90% for collector module
3. ✅ All tests pass in isolation and in suite
4. ✅ Code passes `ruff` linting
5. ✅ Code passes `mypy` type checking
6. ✅ Docstrings present for all public APIs
7. ✅ Manual testing: Can create, update, resolve GHAP in real journal directory
8. ✅ Manual testing: State survives process restart
9. ✅ Manual testing: Orphan detection works across sessions

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Race conditions in file writes | Data loss | Low (single process) | Document multi-process unsupported |
| Large session files slow parsing | Performance | Low (<200 entries) | Use JSONL streaming if needed in v2 |
| Corrupted files from crashes | Data loss | Medium | Atomic writes + corruption recovery |
| Clock skew affects timestamps | Incorrect ordering | Low | Use UTC consistently |
| Disk space exhaustion | Write failures | Low (<1MB/session) | Document archive cleanup |

## Conclusion

This proposal implements a simple, reliable, file-based GHAP state machine that:
- Operates entirely locally with no server dependencies
- Persists state across restarts with corruption recovery
- Provides clean separation between collection (Collector) and analysis (Persister)
- Follows existing codebase patterns (async I/O, structured logging, dataclasses)
- Enables comprehensive testing with real file I/O

The design prioritizes **simplicity** and **reliability** over advanced features, providing a solid foundation for future enhancements while meeting all current requirements.
