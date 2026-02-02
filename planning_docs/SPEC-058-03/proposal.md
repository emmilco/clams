# SPEC-058-03: CALM Orchestration CLI - Technical Proposal

## Overview

This proposal describes the implementation of Python CLI commands that replace the existing bash-based CLAWS orchestration scripts (`.claude/bin/claws-*`). The new CLI is built on Click and shares a business logic layer with future MCP tools, providing consistent behavior across interfaces.

The implementation follows the pattern established in SPEC-058-01: thin CLI wrappers over business logic modules in `src/calm/orchestration/`.

## CLI Structure

### Command Groups

The `calm` CLI extends its existing structure with new command groups:

```
calm
├── init          # (existing from SPEC-058-01)
├── server        # (existing from SPEC-058-01)
├── status        # Extended with orchestration views
├── task          # Task CRUD and transitions
├── gate          # Gate checks for phase transitions
├── worktree      # Git worktree management
├── worker        # Worker registration and tracking
├── review        # Review recording and checks
├── counter       # System counters for batch triggers
├── backup        # Database backup/restore
└── session       # Session handoff management
```

### Click Implementation Pattern

Each command group is a Click group registered on the main CLI:

```python
# src/calm/cli/main.py
from calm.cli.task import task
from calm.cli.gate import gate
from calm.cli.worktree import worktree
from calm.cli.worker import worker
from calm.cli.review import review
from calm.cli.counter import counter
from calm.cli.backup import backup
from calm.cli.session import session

cli.add_command(task)
cli.add_command(gate)
cli.add_command(worktree)
cli.add_command(worker)
cli.add_command(review)
cli.add_command(counter)
cli.add_command(backup)
cli.add_command(session)
```

### Command Example

```python
# src/calm/cli/task.py
import click
from calm.orchestration import tasks as task_ops

@click.group()
def task() -> None:
    """Task management commands."""
    pass

@task.command()
@click.argument("task_id")
@click.argument("title")
@click.option("--spec", help="Parent spec ID")
@click.option("--type", "task_type", type=click.Choice(["feature", "bug"]),
              default="feature", help="Task type")
def create(task_id: str, title: str, spec: str | None, task_type: str) -> None:
    """Create a new task."""
    result = task_ops.create_task(
        task_id=task_id,
        title=title,
        spec_id=spec,
        task_type=task_type,
    )
    click.echo(f"Created {task_type}: {task_id} (phase: {result.phase})")
```

## Business Logic Layer

### Module Structure

```
src/calm/orchestration/
├── __init__.py       # Public API exports
├── tasks.py          # Task CRUD and transitions
├── gates.py          # Gate checking and recording
├── worktrees.py      # Git worktree lifecycle
├── workers.py        # Worker tracking
├── reviews.py        # Review recording and checking
├── counters.py       # Counter management
├── sessions.py       # Session handoff storage
├── phases.py         # Phase definitions and validation
└── project.py        # Project path detection and filtering
```

### Design Principles

1. **Pure functions where possible**: Business logic functions take explicit arguments, return results, and avoid side effects beyond database writes.

2. **Database connection management**: Functions accept an optional `conn` parameter. If not provided, they create a connection using `calm.db.connection.get_connection()`.

3. **Project-aware filtering**: All queries filter by `project_path` to support multi-project usage.

4. **Typed return values**: Functions return dataclasses or named tuples rather than raw dictionaries.

### Key Types

```python
# src/calm/orchestration/tasks.py
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TaskType = Literal["feature", "bug"]
FeaturePhase = Literal["SPEC", "DESIGN", "IMPLEMENT", "CODE_REVIEW",
                       "TEST", "INTEGRATE", "VERIFY", "DONE"]
BugPhase = Literal["REPORTED", "INVESTIGATED", "FIXED", "REVIEWED",
                   "TESTED", "MERGED", "DONE"]

@dataclass
class Task:
    id: str
    title: str
    spec_id: str | None
    task_type: TaskType
    phase: str
    specialist: str | None
    notes: str | None
    blocked_by: list[str]
    worktree_path: str | None
    project_path: str
    created_at: datetime
    updated_at: datetime
```

### Core Functions

#### tasks.py

```python
def create_task(
    task_id: str,
    title: str,
    task_type: TaskType = "feature",
    spec_id: str | None = None,
    project_path: str | None = None,
    conn: Connection | None = None,
) -> Task:
    """Create a new task in the database."""

def get_task(
    task_id: str,
    project_path: str | None = None,
    conn: Connection | None = None,
) -> Task | None:
    """Get a task by ID."""

def list_tasks(
    phase: str | None = None,
    task_type: TaskType | None = None,
    project_path: str | None = None,
    include_done: bool = False,
    conn: Connection | None = None,
) -> list[Task]:
    """List tasks with optional filtering."""

def update_task(
    task_id: str,
    phase: str | None = None,
    specialist: str | None = None,
    notes: str | None = None,
    blocked_by: list[str] | None = None,
    worktree_path: str | None = None,
    conn: Connection | None = None,
) -> Task:
    """Update task fields."""

def transition_task(
    task_id: str,
    to_phase: str,
    gate_result: Literal["pass", "fail"] | None = None,
    gate_details: str | None = None,
    conn: Connection | None = None,
) -> Task:
    """Transition task to a new phase with validation."""

def delete_task(
    task_id: str,
    conn: Connection | None = None,
) -> None:
    """Delete a task and related records."""
```

#### gates.py

```python
@dataclass
class GateResult:
    passed: bool
    checks: list[GateCheck]
    commit_sha: str | None

@dataclass
class GateCheck:
    name: str
    passed: bool
    message: str
    duration_seconds: float | None

def check_gate(
    task_id: str,
    transition: str,
    worktree_path: str,
    project_path: str | None = None,
    conn: Connection | None = None,
) -> GateResult:
    """Run gate checks for a phase transition."""

def record_gate_pass(
    task_id: str,
    transition: str,
    commit_sha: str,
    conn: Connection | None = None,
) -> None:
    """Record a successful gate pass anchored to a commit."""

def verify_gate_pass(
    task_id: str,
    transition: str,
    current_sha: str,
    conn: Connection | None = None,
) -> bool:
    """Verify a gate was passed at the current commit."""

def list_gates() -> list[GateRequirement]:
    """List all gate requirements by transition."""
```

#### worktrees.py

```python
@dataclass
class WorktreeInfo:
    task_id: str
    path: Path
    branch: str
    task_type: TaskType
    phase: str

def create_worktree(
    task_id: str,
    base_dir: Path | None = None,
    conn: Connection | None = None,
) -> WorktreeInfo:
    """Create a git worktree for a task."""

def remove_worktree(
    task_id: str,
    conn: Connection | None = None,
) -> None:
    """Remove a worktree without merging."""

def list_worktrees(
    project_path: str | None = None,
    conn: Connection | None = None,
) -> list[WorktreeInfo]:
    """List all worktrees."""

def get_worktree_path(
    task_id: str,
    conn: Connection | None = None,
) -> Path | None:
    """Get the worktree path for a task."""

def merge_worktree(
    task_id: str,
    skip_sync: bool = False,
    force: bool = False,
    conn: Connection | None = None,
) -> str:
    """Merge worktree to main and cleanup. Returns merge commit SHA."""

def check_merge_conflicts(
    task_id: str,
) -> list[str]:
    """Check for merge conflicts without merging. Returns conflicting files."""

def health_check(
    fix: bool = False,
    dry_run: bool = False,
    conn: Connection | None = None,
) -> WorktreeHealthReport:
    """Audit worktree health and optionally fix issues."""
```

#### workers.py

```python
@dataclass
class Worker:
    id: str
    task_id: str
    role: str
    status: Literal["active", "completed", "failed", "session_ended", "stale"]
    started_at: datetime
    ended_at: datetime | None
    project_path: str | None

def start_worker(
    task_id: str,
    role: str,
    project_path: str | None = None,
    conn: Connection | None = None,
) -> str:
    """Register a worker and return its ID."""

def complete_worker(
    worker_id: str,
    conn: Connection | None = None,
) -> None:
    """Mark a worker as completed."""

def fail_worker(
    worker_id: str,
    reason: str | None = None,
    conn: Connection | None = None,
) -> None:
    """Mark a worker as failed."""

def list_workers(
    status: str | None = None,
    project_path: str | None = None,
    conn: Connection | None = None,
) -> list[Worker]:
    """List workers with optional filtering."""

def get_worker_context(
    task_id: str,
    role: str,
    roles_dir: Path | None = None,
    conn: Connection | None = None,
) -> str:
    """Generate full context for a worker including role prompt and task info."""

def get_role_prompt(
    role: str,
    roles_dir: Path | None = None,
) -> str:
    """Get the role prompt markdown for a given role."""

def cleanup_stale_workers(
    max_age_hours: int = 2,
    conn: Connection | None = None,
) -> int:
    """Mark workers active for too long as stale. Returns count marked."""
```

#### reviews.py

```python
@dataclass
class Review:
    id: int
    task_id: str
    review_type: Literal["spec", "proposal", "code", "bugfix"]
    result: Literal["approved", "changes_requested"]
    worker_id: str | None
    reviewer_notes: str | None
    created_at: datetime

def record_review(
    task_id: str,
    review_type: str,
    result: str,
    worker_id: str | None = None,
    notes: str | None = None,
    conn: Connection | None = None,
) -> Review:
    """Record a review result. Clears previous reviews if changes_requested."""

def list_reviews(
    task_id: str,
    review_type: str | None = None,
    conn: Connection | None = None,
) -> list[Review]:
    """List reviews for a task."""

def check_reviews(
    task_id: str,
    review_type: str,
    required: int = 2,
    conn: Connection | None = None,
) -> tuple[bool, int]:
    """Check if review requirements are met. Returns (passed, count)."""

def clear_reviews(
    task_id: str,
    review_type: str | None = None,
    conn: Connection | None = None,
) -> int:
    """Clear reviews for a task. Returns count cleared."""
```

#### counters.py

```python
def list_counters(
    conn: Connection | None = None,
) -> dict[str, int]:
    """List all counters with their values."""

def get_counter(
    name: str,
    conn: Connection | None = None,
) -> int:
    """Get a counter value."""

def set_counter(
    name: str,
    value: int,
    conn: Connection | None = None,
) -> None:
    """Set a counter to a specific value."""

def increment_counter(
    name: str,
    conn: Connection | None = None,
) -> int:
    """Increment a counter by 1. Returns new value."""

def reset_counter(
    name: str,
    conn: Connection | None = None,
) -> None:
    """Reset a counter to 0."""

def add_counter(
    name: str,
    initial_value: int = 0,
    conn: Connection | None = None,
) -> None:
    """Create a new counter."""
```

#### sessions.py

```python
@dataclass
class Session:
    id: str
    created_at: datetime
    handoff_content: str
    needs_continuation: bool
    resumed_at: datetime | None

def save_session(
    content: str,
    needs_continuation: bool = False,
    auto_commit_worktrees: bool = True,
    conn: Connection | None = None,
) -> str:
    """Save session handoff. Returns session ID."""

def list_sessions(
    limit: int = 10,
    conn: Connection | None = None,
) -> list[Session]:
    """List recent sessions."""

def get_session(
    session_id: str,
    conn: Connection | None = None,
) -> Session | None:
    """Get a session by ID."""

def get_pending_handoff(
    conn: Connection | None = None,
) -> Session | None:
    """Get the pending handoff (needs_continuation and not resumed)."""

def mark_session_resumed(
    session_id: str,
    conn: Connection | None = None,
) -> None:
    """Mark a session as resumed."""

def generate_next_commands(
    conn: Connection | None = None,
) -> str:
    """Generate next commands markdown for active tasks."""
```

## Database Schema Updates

### New Tables

The following tables need to be added to `src/calm/db/schema.py`:

#### sessions

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    handoff_content TEXT,  -- Base64 encoded markdown
    needs_continuation INTEGER DEFAULT 0,
    resumed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_pending
    ON sessions(needs_continuation, resumed_at);
```

#### phase_transitions

```sql
CREATE TABLE IF NOT EXISTS phase_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    gate_result TEXT,  -- 'pass' or 'fail'
    gate_details TEXT,
    transitioned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_transitions_task ON phase_transitions(task_id);
```

#### gate_passes

```sql
CREATE TABLE IF NOT EXISTS gate_passes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    passed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, transition, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_gate_passes_task ON gate_passes(task_id, transition);
```

### Schema Migration

Add these tables to `ALL_TABLES` and `ALL_INDEXES` in `schema.py`. The `init_database()` function is idempotent, so running `calm init` will create any missing tables.

## Command Implementations

### Task Commands

```
calm task create <id> <title> [--spec <spec_id>] [--type feature|bug]
calm task list [--phase <phase>] [--type feature|bug]
calm task show <id>
calm task update <id> [--phase <phase>] [--specialist <spec>] [--notes <text>] [--blocked-by <ids>]
calm task transition <id> <phase> [--gate-result pass|fail] [--gate-details <text>]
calm task delete <id>
```

The `transition` command:
1. Validates the transition is valid for the task type (feature vs bug)
2. For certain transitions, verifies a gate pass exists at the current commit
3. For review-gated transitions, checks that 2 approved reviews exist
4. For IMPLEMENT->CODE_REVIEW, checks implementation code exists
5. Records the transition in `phase_transitions` table
6. Updates the task's phase

### Gate Commands

```
calm gate check <task_id> <transition>
calm gate list
```

The `check` command:
1. Gets the worktree path from the task
2. Determines required checks based on transition type
3. Runs each check (tests, linter, types, TODOs, code exists, reviews, etc.)
4. Records test results in `test_runs` table
5. If all pass, records in `gate_passes` table with commit SHA
6. Returns pass/fail with detailed output

Gate checks are implemented by calling existing gate scripts via subprocess or reimplementing them in Python. Initially, we'll use subprocess to call the existing bash gate scripts, allowing gradual migration.

### Worktree Commands

```
calm worktree create <task_id> [--check-overlaps] [--force]
calm worktree list
calm worktree path <task_id>
calm worktree merge <task_id> [--skip-sync] [--check-only] [--force]
calm worktree remove <task_id>
calm worktree health [--fix] [--dry-run]
```

Git operations use `subprocess.run()` to call git commands. The worktree is created at `.worktrees/<task_id>` relative to the main repo.

The `create` command:
1. Verifies the task exists and gets its type
2. Creates the worktree: `git worktree add .worktrees/<task_id> -b <task_id>`
3. Creates appropriate directories (planning_docs/ for features, bug_reports/ for bugs)
4. Updates the task's worktree_path in the database

The `merge` command:
1. Checks merge lock counter
2. Checks for merge conflicts
3. Switches to main and pulls
4. Merges with `--no-ff`
5. Records merge in database and increments counters
6. Syncs dependencies if uv.lock/requirements.txt exists
7. Removes worktree and branch
8. Updates task phase (to VERIFY for features, DONE for bugs)

### Worker Commands

```
calm worker start <task_id> <role>
calm worker complete <worker_id>
calm worker fail <worker_id> [--reason <text>]
calm worker list
calm worker context <task_id> <role>
calm worker prompt <role>
```

Role files are read from `~/.calm/roles/` (configured in settings). If not found, fall back to `.claude/roles/` in the current project for compatibility.

The `context` command outputs:
1. Base role norms from `_base.md`
2. Role-specific prompt from `<role>.md`
3. Task information from database
4. Working environment details (worktree path, branch, directories)
5. Planning documents list if present

### Review Commands

```
calm review record <task_id> <type> <result> [--worker <id>] [--notes <text>]
calm review list <task_id> [<type>]
calm review check <task_id> <type>
calm review clear <task_id> [<type>]
```

Review types: spec, proposal, code, bugfix
Results: approved, changes_requested

When `changes_requested` is recorded, all previous reviews for that artifact are cleared to restart the review cycle.

### Counter Commands

```
calm counter list
calm counter get <name>
calm counter set <name> <value>
calm counter increment <name>
calm counter add <name> [<value>]
calm counter reset <name>
```

Standard counters initialized during `calm init`:
- `merge_lock`: 0 = inactive, >0 = merges blocked
- `merges_since_e2e`: triggers E2E at 12
- `merges_since_docs`: triggers doc update at 12

### Status Commands (Extended)

```
calm status              # Full overview with orchestration data
calm status health       # System health check
calm status worktrees    # Active worktrees
calm status tasks        # Tasks grouped by phase
calm status workers      # Active workers
calm status counters     # System counters
```

The base `calm status` command already exists. We extend it with subcommands for orchestration views:

```python
@status.command()
def health() -> None:
    """Show system health status."""

@status.command()
def worktrees() -> None:
    """Show active worktrees."""
```

### Backup Commands

```
calm backup create [<name>]
calm backup list
calm backup restore <name>
calm backup auto
```

Backups are stored in `~/.calm/backups/` as SQLite database copies. The `auto` command keeps the last 10 auto-backups with rotation.

### Session Commands

```
calm session save [--continue] [--no-auto-commit]
calm session list
calm session show <id>
```

The `save` command reads handoff content from stdin, optionally auto-commits staged changes in worktrees, and stores the base64-encoded content in the sessions table.

## Project Path Handling

### Detection

The current project path is detected from the working directory by finding the git root:

```python
# src/calm/orchestration/project.py
from pathlib import Path
import subprocess

def detect_project_path() -> str:
    """Detect the project path from current working directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return str(Path.cwd())

def detect_main_repo() -> str:
    """Detect the main repo path (not worktree)."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        first_line = result.stdout.split("\n")[0]
        if first_line.startswith("worktree "):
            return first_line[9:]
    return detect_project_path()
```

### Filtering

All database queries include a `project_path` filter:

```python
def list_tasks(
    project_path: str | None = None,
    ...
) -> list[Task]:
    if project_path is None:
        project_path = detect_project_path()

    query = "SELECT * FROM tasks WHERE project_path = ?"
    # ...
```

### Storage

When creating tasks, the project path is automatically recorded:

```python
def create_task(
    task_id: str,
    title: str,
    project_path: str | None = None,
    ...
) -> Task:
    if project_path is None:
        project_path = detect_project_path()

    # INSERT includes project_path column
```

## Gate Check Integration

### Strategy

Gate checks can be implemented in two ways:

1. **Subprocess to existing scripts**: Call `.claude/gates/*.sh` scripts via subprocess
2. **Native Python**: Reimplement gate logic in Python

For the initial implementation, we use approach #1 for complex checks (tests, linter, types) and native Python for simple checks (file existence, review counts).

### Implementation

```python
# src/calm/orchestration/gates.py
import subprocess
from pathlib import Path

def run_gate_script(
    script_name: str,
    worktree: Path,
    *args: str,
) -> tuple[bool, str]:
    """Run a gate script and return (passed, output)."""
    script_path = Path(".claude/gates") / script_name

    result = subprocess.run(
        [str(script_path), str(worktree), *args],
        capture_output=True,
        text=True,
        cwd=worktree,
    )

    return result.returncode == 0, result.stdout + result.stderr

def check_tests(worktree: Path) -> GateCheck:
    """Run test suite via gate script."""
    passed, output = run_gate_script("check_tests.sh", worktree)
    return GateCheck(
        name="Tests pass",
        passed=passed,
        message=output,
        duration_seconds=None,
    )

def check_implementation_exists(worktree: Path, task_id: str) -> GateCheck:
    """Check that implementation code exists (not just docs)."""
    result = subprocess.run(
        ["git", "diff", "main...HEAD", "--name-only"],
        capture_output=True,
        text=True,
        cwd=worktree,
    )

    impl_patterns = ["src/", "tests/", "clams/", "clams-visualizer/"]
    changed_files = result.stdout.strip().split("\n")
    impl_files = [f for f in changed_files if any(f.startswith(p) for p in impl_patterns)]

    return GateCheck(
        name="Implementation code exists",
        passed=len(impl_files) > 0,
        message=f"Changed files: {', '.join(impl_files[:5])}",
        duration_seconds=None,
    )
```

### Gate Requirements by Transition

The gate logic follows the phase model from CLAUDE.md:

**Feature Transitions:**
- SPEC->DESIGN: 2 spec reviews approved (human approval required)
- DESIGN->IMPLEMENT: proposal exists, 2 proposal reviews approved (human approval required)
- IMPLEMENT->CODE_REVIEW: tests pass, linter clean, types clean, no untracked TODOs, code exists
- CODE_REVIEW->TEST: 2 code reviews approved
- TEST->INTEGRATE: full test suite passes
- INTEGRATE->VERIFY: changelog exists (then merge)
- VERIFY->DONE: manual (on main)

**Bug Transitions:**
- REPORTED->INVESTIGATED: bug report complete, root cause documented
- INVESTIGATED->FIXED: tests pass, linter clean, types clean, regression test added
- FIXED->REVIEWED: 2 bugfix reviews approved
- REVIEWED->TESTED: full test suite passes, no skipped tests
- TESTED->MERGED: changelog exists (then merge)
- MERGED->DONE: manual (on main)

## Testing Strategy

### Unit Tests

Test the business logic modules with mocked database connections:

```python
# tests/test_calm/test_orchestration/test_tasks.py
import pytest
from calm.orchestration import tasks

def test_create_task(tmp_db):
    """Test task creation."""
    task = tasks.create_task(
        task_id="SPEC-001",
        title="Test Feature",
        task_type="feature",
        project_path="/test/project",
        conn=tmp_db,
    )

    assert task.id == "SPEC-001"
    assert task.phase == "SPEC"
    assert task.task_type == "feature"

def test_transition_validation(tmp_db):
    """Test that invalid transitions are rejected."""
    tasks.create_task(
        task_id="SPEC-001",
        title="Test",
        project_path="/test/project",
        conn=tmp_db,
    )

    with pytest.raises(ValueError, match="Invalid transition"):
        tasks.transition_task(
            task_id="SPEC-001",
            to_phase="IMPLEMENT",  # Can't skip DESIGN
            conn=tmp_db,
        )
```

### CLI Integration Tests

Test CLI commands with Click's test runner:

```python
# tests/test_calm/test_cli/test_task_cli.py
from click.testing import CliRunner
from calm.cli.main import cli

def test_task_create(tmp_db, monkeypatch):
    """Test calm task create command."""
    monkeypatch.setenv("CALM_DB_PATH", str(tmp_db))

    runner = CliRunner()
    result = runner.invoke(cli, ["task", "create", "SPEC-001", "Test Feature"])

    assert result.exit_code == 0
    assert "Created feature: SPEC-001" in result.output
```

### Fixtures

```python
# tests/conftest.py
import pytest
import sqlite3
from pathlib import Path
from calm.db.schema import init_database

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()
```

## Migration Notes

### Coexistence Period

During development, both CLI systems will coexist:
- `.claude/bin/claws-*` scripts continue to work
- `calm <cmd>` commands use the new implementation
- Both use the same database (`~/.calm/metadata.db`)

### Database Compatibility

The calm CLI reads from `~/.calm/metadata.db` while claws scripts read from `.claude/claws.db`. During the cutover (SPEC-058-07), the CLAUDE.md will be updated to use `calm` commands, and the database will be migrated.

### Backward Compatibility Considerations

1. **Role files**: `calm worker prompt` and `calm worker context` need role files. During transition, check both `~/.calm/roles/` and `.claude/roles/`.

2. **Gate scripts**: Gate checks initially call existing bash scripts. This allows gradual migration without breaking gate functionality.

3. **Worktree paths**: Both systems expect worktrees at `.worktrees/` in the project root.

4. **Table names**: Some table names differ between systems (e.g., `system_counters` vs `counters`). The new CLI uses the schema from SPEC-058-01 which has `counters`.

## Implementation Order

1. **Phase 1: Core modules**
   - `src/calm/orchestration/project.py` - project path detection
   - `src/calm/orchestration/phases.py` - phase definitions
   - `src/calm/orchestration/counters.py` - simple counter operations

2. **Phase 2: Task management**
   - `src/calm/orchestration/tasks.py` - CRUD and transitions
   - `src/calm/cli/task.py` - CLI wrapper
   - Database schema updates (phase_transitions table)

3. **Phase 3: Reviews and gates**
   - `src/calm/orchestration/reviews.py` - review recording
   - `src/calm/orchestration/gates.py` - gate checking
   - `src/calm/cli/review.py`, `src/calm/cli/gate.py`
   - Database schema updates (gate_passes table)

4. **Phase 4: Worktrees and workers**
   - `src/calm/orchestration/worktrees.py` - git worktree management
   - `src/calm/orchestration/workers.py` - worker tracking
   - `src/calm/cli/worktree.py`, `src/calm/cli/worker.py`

5. **Phase 5: Sessions and backup**
   - `src/calm/orchestration/sessions.py` - session handoffs
   - `src/calm/cli/session.py`, `src/calm/cli/backup.py`
   - Database schema updates (sessions table)

6. **Phase 6: Status and integration**
   - Extend `src/calm/cli/status.py` with orchestration views
   - Integration testing
   - Documentation updates

## Risks and Mitigations

1. **Gate check compatibility**
   - Risk: Gate checks may fail differently in Python vs bash
   - Mitigation: Use subprocess to call existing scripts initially; test thoroughly

2. **Project path detection edge cases**
   - Risk: Worktree detection may fail in unusual git configurations
   - Mitigation: Follow the exact logic from `claws-common.sh`

3. **Database schema evolution**
   - Risk: New tables may conflict with existing data
   - Mitigation: Use `CREATE TABLE IF NOT EXISTS`; test with existing databases

4. **Subprocess reliability**
   - Risk: Gate scripts may have different behavior when called via subprocess
   - Mitigation: Test in the same environment as bash scripts; preserve environment variables
