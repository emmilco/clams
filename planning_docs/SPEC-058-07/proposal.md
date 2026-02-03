# SPEC-058-07 Proposal: CALM Cutover - Switch from Old to New System

## 1. Overview

This proposal describes the implementation of `scripts/cutover.py`, a one-off migration script that performs the atomic switch from CLAMS/CLAWS to CALM. The script handles data migration from two source databases, configuration updates, and verification. It also covers the CLAUDE.md rewrite and the test suite.

## 2. Module Structure

The cutover logic lives in a single self-contained script at `scripts/cutover.py`. It does **not** create a new Python module or package - it is a standalone script that imports from `src/calm/` for reusable utilities. This keeps the cutover disposable (easy to delete in SPEC-058-08) while still leveraging tested infrastructure.

```
scripts/
  cutover.py           # Main cutover script (~400-500 lines)

tests/
  test_cutover.py      # Integration tests (~300-400 lines)

CLAUDE.md              # Rewritten for CALM workflow
```

### Internal Organization of `cutover.py`

The script is structured as a sequence of clearly named functions, each handling one phase of the cutover. A `main()` function orchestrates them in order. No classes are needed - the operations are sequential and stateless between phases.

```
cutover.py
  ├── Imports and constants
  ├── Dataclass: CutoverOptions
  ├── Dataclass: CutoverResult
  ├── Phase functions:
  │   ├── stop_old_server()
  │   ├── create_backups()
  │   ├── ensure_calm_infrastructure()
  │   ├── migrate_clams_data()
  │   ├── migrate_claws_data()
  │   ├── update_configuration()
  │   ├── start_calm_server()
  │   └── verify_migration()
  ├── run_cutover() - orchestrator
  └── main() - CLI entry point (argparse)
```

## 3. Function Signatures

### 3.1 Data Classes

```python
@dataclass
class CutoverOptions:
    """Options controlling cutover behavior."""
    dry_run: bool = False
    verbose: bool = False
    skip_server: bool = False       # Skip server start/stop (for testing)
    clams_home: Path = Path.home() / ".clams"
    calm_home: Path = Path.home() / ".calm"
    claws_db: Path | None = None    # Auto-detected from git root if None
    repo_root: Path | None = None   # Auto-detected if None
    claude_json: Path = Path.home() / ".claude.json"
    settings_json: Path = Path.home() / ".claude" / "settings.json"
    dev_mode: bool = True           # Use uv run for MCP server (dev install)
```

```python
@dataclass
class CutoverResult:
    """Result of cutover attempt."""
    success: bool = True
    steps_completed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    # counts maps table_name -> {"source": N, "migrated": N}
```

### 3.2 Phase Functions

```python
def stop_old_server(options: CutoverOptions) -> tuple[bool, str]:
    """Stop the old CLAMS MCP server process.

    Attempts to kill processes matching 'clams.server'.
    Returns (success, message). Always succeeds (warning if already stopped).
    """

def create_backups(options: CutoverOptions) -> tuple[bool, list[str]]:
    """Create backups of all source files before modification.

    Backs up:
      - clams_home/metadata.db -> clams_home/metadata.db.pre-cutover
      - claws_db -> claws_db.pre-cutover
      - claude_json -> claude_json.pre-cutover
      - settings_json -> settings_json.pre-cutover

    Skips backup if .pre-cutover file already exists (preserves original).
    In dry_run mode, reports what would be backed up.
    Returns (success, messages).
    """

def ensure_calm_infrastructure(options: CutoverOptions) -> tuple[bool, list[str]]:
    """Set up CALM target directory and database.

    Reuses:
      - create_directory_structure() from calm.install.templates
      - init_database() from calm.db.schema
      - copy_all_templates() from calm.install.templates

    Returns (success, messages).
    """

def migrate_clams_data(
    options: CutoverOptions,
    target_db: Path,
) -> tuple[bool, dict[str, dict[str, int]]]:
    """Migrate CLAMS metadata.db tables to CALM metadata.db.

    Tables migrated:
      - indexed_files (direct copy)
      - projects (direct copy)
      - git_index_state (direct copy)

    Also migrates session journal JSONL if present.
    Uses INSERT OR REPLACE for idempotency.
    Returns (success, counts_per_table).
    """

def migrate_claws_data(
    options: CutoverOptions,
    target_db: Path,
) -> tuple[bool, dict[str, dict[str, int]]]:
    """Migrate CLAWS orchestration data to CALM metadata.db.

    Tables migrated with column mappings:
      - tasks (assigned_specialist -> specialist, + project_path)
      - workers (specialist_type -> role, current_task_id -> task_id, status mapping)
      - reviews (artifact_type -> review_type, reviewer_worker_id -> worker_id,
                 issues_found -> reviewer_notes, review_num dropped)
      - test_runs (execution_time_seconds -> duration_seconds, columns dropped)
      - system_counters -> counters (table rename, MAX merge)
      - phase_transitions (NULL from_phase -> '')
      - gate_passes (direct copy)
      - sessions (direct copy)

    Uses INSERT OR REPLACE for most tables. Counters use MAX(old, new).
    Returns (success, counts_per_table).
    """

def update_configuration(options: CutoverOptions) -> tuple[bool, list[str]]:
    """Update MCP server and hook configuration.

    Reuses:
      - register_mcp_server() from calm.install.config_merge
      - register_hooks() from calm.install.config_merge
    Also:
      - Removes old "clams" key from mcpServers in claude.json

    Returns (success, messages).
    """

def start_calm_server(options: CutoverOptions) -> tuple[bool, str]:
    """Start the CALM MCP server daemon and verify it responds.

    Reuses ensure_qdrant_running() from calm.install.docker.
    Reuses start_daemon() from calm.server.daemon.
    Checks health via ping.
    Returns (success, message).
    """

def verify_migration(
    options: CutoverOptions,
    counts: dict[str, dict[str, int]],
) -> tuple[bool, list[str]]:
    """Verify migration by comparing source and target counts.

    For each migrated table, compares source count to target count.
    Prints comparison table. Warnings for mismatches (not errors,
    since idempotent reruns may show differences).
    Returns (success, messages).
    """

def run_cutover(options: CutoverOptions) -> CutoverResult:
    """Run the full cutover process.

    Orchestrates all phases in order:
      1. stop_old_server
      2. create_backups
      3. ensure_calm_infrastructure
      4. migrate_clams_data
      5. migrate_claws_data
      6. update_configuration
      7. start_calm_server (unless skip_server)
      8. verify_migration

    Returns CutoverResult with status and details.
    """
```

### 3.3 Helper Functions

```python
def _detect_repo_root() -> Path:
    """Detect the git repository root from cwd.

    Runs 'git rev-parse --show-toplevel'. Falls back to cwd.
    """

def _detect_claws_db(repo_root: Path) -> Path:
    """Locate the CLAWS database relative to repo root.

    Returns repo_root / '.claude' / 'claws.db'.
    """

def _resolve_worktree_path(path: str, repo_root: Path) -> str:
    """Convert a relative worktree path to absolute.

    If path starts with '.worktrees/' or is relative,
    resolve it against repo_root. Otherwise return as-is.
    """

def _map_worker_status(old_status: str) -> str:
    """Map old worker status values to new.

    'idle' -> 'completed', 'stale' -> 'session_ended'.
    All others pass through.
    """

def _migrate_journal_entries(
    jsonl_path: Path,
    target_conn: sqlite3.Connection,
) -> int:
    """Parse JSONL session entries and insert into session_journal table.

    Returns count of entries migrated.
    """

def _remove_old_mcp_server(config: dict[str, Any]) -> dict[str, Any]:
    """Remove the old 'clams' key from mcpServers in config.

    Returns updated config (does not mutate original).
    """

def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count rows in a table. Returns 0 if table doesn't exist."""

def output(message: str, verbose: bool = False, force: bool = False) -> None:
    """Print a message. If verbose=False and force=False, suppress."""
```

## 4. Data Flow

### 4.1 Execution Sequence

```
main() parses args
  |
  v
run_cutover(options)
  |
  v
[1] stop_old_server()
  |  pkill -f "clams.server" (best-effort, warn on failure)
  |
  v
[2] create_backups()
  |  For each source file:
  |    if .pre-cutover exists: skip (preserve original backup)
  |    else: shutil.copy2(source, source.pre-cutover)
  |  (In dry_run: report only)
  |
  v
[3] ensure_calm_infrastructure()
  |  create_directory_structure(calm_home)     # from calm.install.templates
  |  init_database(calm_home / "metadata.db")  # from calm.db.schema
  |  copy_all_templates(calm_home)             # from calm.install.templates
  |
  v
[4] migrate_clams_data(target_db=calm_home/metadata.db)
  |  Open source: clams_home/metadata.db (read-only)
  |  Open target: calm_home/metadata.db
  |  For each table (indexed_files, projects, git_index_state):
  |    SELECT * from source
  |    INSERT OR REPLACE into target
  |  Parse journal JSONL if present:
  |    Read session_entries.jsonl line by line
  |    JSON parse each line -> INSERT OR REPLACE into session_journal
  |  Record counts
  |
  v
[5] migrate_claws_data(target_db=calm_home/metadata.db)
  |  Open source: repo_root/.claude/claws.db (read-only)
  |  Open target: calm_home/metadata.db
  |  For each table:
  |    SELECT * from source with old column names
  |    Transform row: rename columns, map values, add defaults
  |    INSERT OR REPLACE into target with new column names
  |  Special handling:
  |    - counters: INSERT OR IGNORE, then UPDATE SET value=MAX(value, ?)
  |    - tasks.worktree_path: resolve relative -> absolute
  |    - tasks.project_path: set to repo_root
  |    - workers.status: map 'idle'->'completed', 'stale'->'session_ended'
  |    - workers.project_path: set to repo_root
  |    - phase_transitions.from_phase: NULL -> ''
  |    - reviews.review_num: dropped (not in target schema)
  |    - test_runs: several columns dropped
  |  Record counts
  |
  v
[6] update_configuration()
  |  # Remove old CLAMS server
  |  config = read_json_config(claude_json)
  |  config = _remove_old_mcp_server(config)
  |  atomic_write_json(claude_json, config)
  |
  |  # Register CALM server
  |  register_mcp_server(claude_json, dev_mode=options.dev_mode)
  |
  |  # Register CALM hooks (also cleans old clams hooks)
  |  register_hooks(settings_json)
  |
  v
[7] start_calm_server() (unless skip_server)
  |  ensure_qdrant_running()  # from calm.install.docker
  |  start_daemon()           # from calm.server.daemon
  |  Wait up to 10s for health check
  |
  v
[8] verify_migration()
     For each migrated table:
       source_count = count rows in source db
       target_count = count rows in target db
       Print comparison
       If mismatch: add WARNING
     Print summary
```

### 4.2 Database Connection Strategy

The script opens each source database in **read-only mode** to prevent accidental corruption:

```python
source_conn = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
```

The target database is opened in normal read-write mode. All writes are wrapped in transactions for atomicity.

### 4.3 Row Migration Pattern

Each table migration follows this pattern:

```python
# Read all rows from source
source_rows = source_conn.execute("SELECT col1, col2, ... FROM old_table").fetchall()

# Transform and write to target
for row in source_rows:
    target_conn.execute(
        "INSERT OR REPLACE INTO new_table (new_col1, new_col2, ...) VALUES (?, ?, ...)",
        (transform_col1(row[0]), transform_col2(row[1]), ...),
    )
target_conn.commit()
```

For counters (which use MAX merge):

```python
for name, value in source_rows:
    target_conn.execute(
        "INSERT INTO counters (name, value) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET value = MAX(value, excluded.value)",
        (name, value),
    )
```

## 5. Reuse Strategy

### 5.1 Direct Reuse from `src/calm/install/`

| Function | Source Module | Purpose in Cutover |
|----------|-------------|-------------------|
| `create_directory_structure()` | `calm.install.templates` | Create `~/.calm/` directory tree |
| `copy_all_templates()` | `calm.install.templates` | Copy role files, workflows, skills, config |
| `init_database()` | `calm.db.schema` | Create all CALM tables in target database |
| `register_mcp_server()` | `calm.install.config_merge` | Register CALM MCP server in `~/.claude.json` |
| `register_hooks()` | `calm.install.config_merge` | Register CALM hooks in `~/.claude/settings.json` |
| `read_json_config()` | `calm.install.config_merge` | Read JSON config for old server removal |
| `atomic_write_json()` | `calm.install.config_merge` | Write JSON config atomically |
| `ensure_qdrant_running()` | `calm.install.docker` | Ensure Qdrant container is up |
| `start_daemon()` | `calm.server.daemon` | Start CALM server daemon |

### 5.2 What the Script Implements Itself

| Functionality | Reason |
|--------------|--------|
| Old server stopping | Unique to migration (pkill logic) |
| Backup creation | Simple shutil.copy2, not needed elsewhere |
| CLAMS data migration | One-off SQL transformations |
| CLAWS data migration | One-off SQL transformations with column mappings |
| Journal JSONL parsing | One-off format conversion |
| Old MCP server removal | Simple dict key deletion |
| Verification / count comparison | One-off validation logic |

## 6. Error Handling

### 6.1 Strategy

The cutover follows a **fail-forward with warnings** approach:

- **Fatal errors** (stop the cutover): Target database creation fails, source database not found when expected.
- **Warnings** (continue with warning): Old server already stopped, a backup target already exists, count mismatches during verification, journal JSONL empty.
- **Graceful degradation**: If `~/.clams/metadata.db` does not exist, skip CLAMS data migration entirely (nothing to migrate). If `.claude/claws.db` does not exist, skip CLAWS data migration entirely.

### 6.2 Error Cases

| Scenario | Behavior |
|----------|----------|
| `~/.clams/` doesn't exist | Skip CLAMS migration, warn |
| `.claude/claws.db` doesn't exist | Skip CLAWS migration, warn |
| Old server won't stop | Warn, continue |
| Backup target exists | Skip backup (preserve original), info message |
| Source DB has corrupt rows | Log warning per row, continue with remaining rows |
| Target DB write fails | Fatal error, stop cutover |
| Config file missing | `read_json_config` returns `{}`, safe to proceed |
| Server fails to start | Error message, non-zero exit. Migration data is still intact. |
| Qdrant not running | Warn, skip server start |
| Count mismatch in verification | Warning (not error), idempotent reruns may differ |

### 6.3 Dry Run Behavior

When `--dry-run` is specified:

- All source databases are opened read-only and queried for counts.
- Target databases are NOT created, modified, or written to.
- Config files are NOT modified.
- No processes are started or stopped.
- Each step prints what it **would** do with counts.
- Output includes column mapping summary for each table.

Example dry-run output:
```
CALM Cutover (dry run)

[1/8] Would stop old CLAMS server
[2/8] Would create backups:
  - ~/.clams/metadata.db -> ~/.clams/metadata.db.pre-cutover
  - .claude/claws.db -> .claude/claws.db.pre-cutover
  - ~/.claude.json -> ~/.claude.json.pre-cutover
  - ~/.claude/settings.json -> ~/.claude/settings.json.pre-cutover
[3/8] Would create CALM directories and initialize database
[4/8] Would migrate CLAMS data:
  - indexed_files: 42 rows
  - projects: 1 rows
  - git_index_state: 1 rows
  - session_journal: 0 rows (JSONL empty)
[5/8] Would migrate CLAWS data:
  - tasks: 15 rows (assigned_specialist -> specialist, + project_path)
  - workers: 30 rows (specialist_type -> role, current_task_id -> task_id)
  - reviews: 25 rows (artifact_type -> review_type, reviewer_worker_id -> worker_id)
  - test_runs: 40 rows (execution_time_seconds -> duration_seconds)
  - counters: 3 rows (system_counters -> counters, MAX merge)
  - phase_transitions: 50 rows (NULL from_phase -> '')
  - gate_passes: 20 rows (direct copy)
  - sessions: 5 rows (direct copy)
[6/8] Would update configuration:
  - Remove "clams" from mcpServers in ~/.claude.json
  - Register "calm" in mcpServers in ~/.claude.json
  - Register CALM hooks in ~/.claude/settings.json
  - Remove old clams_scripts hooks
[7/8] Would start CALM server
[8/8] Verification skipped (dry run)

No changes made.
```

## 7. CLAUDE.md Approach

### 7.1 Strategy

The existing `CLAUDE.md` is a ~600-line document that serves as the orchestrator's operational manual. The new version must:

1. **Preserve all workflow knowledge** - phases, gates, roles, review model, bug workflow, batch jobs, escalation rules.
2. **Replace all tool references** - `.claude/bin/claws-*` commands become `calm` CLI commands.
3. **Update path references** - `.claude/roles/` becomes `~/.calm/roles/`.
4. **Add CALM activation model** - document that `/orchestrate` activates full workflow mode.
5. **Document CALM features** - memory tools, GHAP, `/wrapup`, `/reflection`.
6. **Remove stale sections** - "Available Tools" section with bash scripts, "always run from main repo" warning (no longer needed since DB is centralized at `~/.calm/metadata.db`).

### 7.2 Implementation

The CLAUDE.md rewrite is done directly by the cutover script's implementer as a file replacement. It is NOT generated programmatically - it is a hand-authored markdown document checked into the repo.

The new CLAUDE.md structure:

```
# CALM Orchestrator

## Your Role
  (same core responsibilities)

## Activation
  - /orchestrate -> enables full workflow mode
  - Memory features always active

## CALM CLI Reference
  - calm task create|list|show|update|transition|delete
  - calm gate check|list
  - calm worktree create|list|path|merge|remove
  - calm worker start|complete|fail|list
  - calm review record|list|check|clear
  - calm counter list|get|set|increment
  - calm session list|show
  - calm status
  - calm backup create|list|restore

## Specialist Roles
  (same table, paths updated to ~/.calm/roles/)

## Phase Model
  (same content)

## Workflow
  (same content, commands updated to calm CLI)

## Bug Workflow
  (same content, commands updated to calm CLI)

## Batch Jobs / System States / Merge Lock
  (same content, commands updated)

## Human Interaction / Session Continuity
  (updated for CALM session tools and /wrapup skill)

## Principles
  (same content)
```

Key differences from old CLAUDE.md:
- No "run commands from main repo" warning (centralized DB eliminates this)
- All `claws-*` commands become `calm` subcommands
- Role files referenced at `~/.calm/roles/` instead of `.claude/roles/`
- New section explaining memory/learning features are always active
- New section explaining `/orchestrate` activation model
- Removed the detailed bash script listings (replaced with CLI reference)

## 8. Testing Strategy

### 8.1 Test File

All cutover tests go in `tests/test_cutover.py`. Tests use `tmp_path` fixtures to create isolated filesystem environments with mock databases.

### 8.2 Test Fixtures

```python
@pytest.fixture
def mock_clams_home(tmp_path: Path) -> Path:
    """Create a mock ~/.clams/ with sample data."""
    clams = tmp_path / ".clams"
    clams.mkdir()
    # Create metadata.db with old schema and sample rows
    # Create journal/ with sample JSONL
    return clams

@pytest.fixture
def mock_claws_db(tmp_path: Path) -> Path:
    """Create a mock .claude/claws.db with sample data."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    db_path = claude_dir / "claws.db"
    # Create DB with old schema and sample rows
    return db_path

@pytest.fixture
def mock_calm_home(tmp_path: Path) -> Path:
    """Target directory for CALM."""
    return tmp_path / ".calm"

@pytest.fixture
def cutover_options(
    tmp_path: Path,
    mock_clams_home: Path,
    mock_claws_db: Path,
    mock_calm_home: Path,
) -> CutoverOptions:
    """CutoverOptions pointing to all mock paths."""
    return CutoverOptions(
        dry_run=False,
        skip_server=True,  # Never start real servers in tests
        clams_home=mock_clams_home,
        calm_home=mock_calm_home,
        claws_db=mock_claws_db,
        repo_root=tmp_path,
        claude_json=tmp_path / ".claude.json",
        settings_json=tmp_path / ".claude" / "settings.json",
    )
```

### 8.3 Test Cases

```python
class TestCreateBackups:
    """Tests for backup creation."""

    def test_creates_backups_for_existing_files(self, cutover_options)
    def test_skips_backup_if_pre_cutover_exists(self, cutover_options)
    def test_skips_missing_source_files(self, cutover_options)
    def test_dry_run_no_files_created(self, cutover_options)


class TestEnsureInfrastructure:
    """Tests for CALM infrastructure setup."""

    def test_creates_directory_structure(self, cutover_options)
    def test_initializes_database_with_all_tables(self, cutover_options)
    def test_idempotent_on_rerun(self, cutover_options)


class TestMigrateClamsData:
    """Tests for CLAMS metadata migration."""

    def test_migrates_indexed_files(self, cutover_options, mock_clams_home)
    def test_migrates_projects(self, cutover_options, mock_clams_home)
    def test_migrates_git_index_state(self, cutover_options, mock_clams_home)
    def test_skips_call_graph(self, cutover_options, mock_clams_home)
    def test_migrates_journal_jsonl(self, cutover_options, mock_clams_home)
    def test_skips_empty_journal(self, cutover_options, mock_clams_home)
    def test_skips_when_source_missing(self, cutover_options)
    def test_idempotent_on_rerun(self, cutover_options, mock_clams_home)


class TestMigrateClawsData:
    """Tests for CLAWS orchestration data migration."""

    def test_tasks_column_rename(self, cutover_options, mock_claws_db)
        # assigned_specialist -> specialist, + project_path
    def test_tasks_worktree_path_absolute(self, cutover_options, mock_claws_db)
        # Relative paths converted to absolute
    def test_workers_column_rename(self, cutover_options, mock_claws_db)
        # specialist_type -> role, current_task_id -> task_id
    def test_workers_status_mapping(self, cutover_options, mock_claws_db)
        # 'idle' -> 'completed', 'stale' -> 'session_ended'
    def test_reviews_column_rename(self, cutover_options, mock_claws_db)
        # artifact_type -> review_type, reviewer_worker_id -> worker_id,
        # issues_found -> reviewer_notes, review_num dropped
    def test_test_runs_column_rename(self, cutover_options, mock_claws_db)
        # execution_time_seconds -> duration_seconds, dropped columns
    def test_counters_table_rename(self, cutover_options, mock_claws_db)
        # system_counters -> counters
    def test_counters_max_merge(self, cutover_options, mock_claws_db)
        # Pre-existing counter: result is MAX(old, new)
    def test_phase_transitions_null_from_phase(self, cutover_options, mock_claws_db)
        # NULL from_phase -> ''
    def test_gate_passes_direct_copy(self, cutover_options, mock_claws_db)
    def test_sessions_direct_copy(self, cutover_options, mock_claws_db)
    def test_skips_merge_log(self, cutover_options, mock_claws_db)
    def test_skips_violations(self, cutover_options, mock_claws_db)
    def test_skips_when_source_missing(self, cutover_options)
    def test_idempotent_on_rerun(self, cutover_options, mock_claws_db)


class TestUpdateConfiguration:
    """Tests for config file updates."""

    def test_removes_old_clams_server(self, cutover_options)
    def test_registers_calm_server(self, cutover_options)
    def test_registers_calm_hooks(self, cutover_options)
    def test_removes_old_clams_hooks(self, cutover_options)
    def test_preserves_other_servers(self, cutover_options)
    def test_preserves_other_hooks(self, cutover_options)
    def test_creates_files_if_missing(self, cutover_options)
    def test_dry_run_no_changes(self, cutover_options)


class TestVerifyMigration:
    """Tests for migration verification."""

    def test_reports_matching_counts(self, cutover_options)
    def test_warns_on_mismatched_counts(self, cutover_options)


class TestDryRun:
    """Tests for dry run mode."""

    def test_reports_counts_without_modifying(self, cutover_options)
    def test_no_target_database_created(self, cutover_options)
    def test_no_config_files_modified(self, cutover_options)


class TestIdempotency:
    """Tests for idempotent execution."""

    def test_running_twice_same_result(self, cutover_options)
        # Run cutover twice, assert same row counts in target


class TestFullCutover:
    """End-to-end integration test."""

    def test_full_cutover_with_sample_data(self, cutover_options)
        # Populate mock DBs with representative data
        # Run cutover
        # Verify all tables migrated
        # Verify config updated
        # Verify backups created
```

### 8.4 Mock Database Setup

Each test fixture creates real SQLite databases with the old schemas and sample data. For example, the CLAWS mock:

```python
def _create_mock_claws_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    # Create old-schema tables (copy from actual claws.db schema)
    conn.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            spec_id TEXT,
            title TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT 'SPEC',
            assigned_specialist TEXT,
            worktree_path TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            blocked_by TEXT,
            notes TEXT,
            task_type TEXT NOT NULL DEFAULT 'feature'
        )
    """)
    # ... other tables ...

    # Insert sample data
    conn.execute("""
        INSERT INTO tasks VALUES (
            'SPEC-001', NULL, 'Test Task', 'IMPLEMENT',
            'backend', '.worktrees/SPEC-001',
            '2025-01-01', '2025-01-02', NULL, NULL, 'feature'
        )
    """)
    # ... more sample data ...
    conn.commit()
    conn.close()
```

## 9. CLI Interface

```
usage: cutover.py [-h] [--dry-run] [--verbose] [--skip-server]

CALM Cutover - Migrate from CLAMS/CLAWS to CALM

options:
  -h, --help      show this help message and exit
  --dry-run       Report what would be done without making changes
  --verbose       Show detailed output
  --skip-server   Skip starting/stopping servers
```

Invocation: `python scripts/cutover.py [--dry-run] [--verbose] [--skip-server]`

Exit codes:
- `0`: Success
- `1`: Fatal error (target DB creation failed, etc.)

## 10. Idempotency Design

The script achieves idempotency through:

1. **`INSERT OR REPLACE`**: Most tables use this to upsert rows. Running twice with the same source data produces the same result.
2. **Counter MAX merge**: `ON CONFLICT DO UPDATE SET value = MAX(value, excluded.value)` ensures counters never decrease.
3. **Backup skip**: `.pre-cutover` backups are only created if they don't already exist, preserving the original state from the first run.
4. **Infrastructure idempotency**: `CREATE TABLE IF NOT EXISTS`, `mkdir(exist_ok=True)`.
5. **Config merge idempotency**: `merge_hooks()` removes existing CALM hooks before re-adding, and `merge_mcp_server()` overwrites the existing `calm` key.

## 11. Dependencies

The script uses only packages already in the project:

- `sqlite3` (stdlib)
- `json` (stdlib)
- `argparse` (stdlib)
- `shutil` (stdlib)
- `subprocess` (stdlib)
- `pathlib` (stdlib)
- `dataclasses` (stdlib)
- `calm.db.schema` (project)
- `calm.install.config_merge` (project)
- `calm.install.templates` (project)
- `calm.install.docker` (project)
- `calm.server.daemon` (project)

No new dependencies are introduced.

## 12. Spec Refinements

After review, the spec is complete and no refinements are needed. The column mappings, table selections, and migration rules are well-specified and align exactly with the source and target database schemas.
