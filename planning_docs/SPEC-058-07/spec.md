# SPEC-058-07: CALM Cutover - Switch from Old to New System

## Overview

Switch the active system from CLAMS/CLAWS to CALM. This involves migrating existing data, updating configuration to point to the new MCP server and hooks, updating CLAUDE.md to document the new system, and verifying everything works end-to-end.

**Precondition**: CALM is fully implemented (SPEC-058-01 through 058-06 complete). The old CLAMS server and CLAWS bash scripts are still active and in use.

**Postcondition**: CALM is the active system. Old CLAMS/CLAWS still exists in the codebase (removal is SPEC-058-08) but is no longer referenced by any configuration.

## Scope

### In Scope

1. **Data migration script** - One-off script to migrate existing state
2. **Configuration update** - MCP server registration, hook registration
3. **CLAUDE.md update** - Document the new CALM-based workflow
4. **Verification** - Test that migrated data is accessible and all features work

### Out of Scope

- Removing old code (`src/clams/`, `.claude/bin/claws-*`, `clams_scripts/`) - That's SPEC-058-08
- Building `calm migrate` as a permanent CLI feature - This is a one-off operation
- Public distribution or packaging

## Detailed Requirements

### 1. Migration Script (`scripts/cutover.py`)

A one-off Python script that performs the atomic cutover. Must be idempotent (safe to run multiple times).

#### 1.1 Stop Old Server

- Stop the old CLAMS MCP server process (`pkill -f "clams.server"` or equivalent)
- Verify it's stopped

#### 1.2 Migrate CLAMS Data (`~/.clams/` → `~/.calm/`)

Source: `~/.clams/metadata.db` (memories, GHAP entries, session data)
Target: `~/.calm/metadata.db`

**Tables to migrate:**
- `memories` - Copy all rows. Schema is identical between old and new.
- `ghap_entries` - Copy all rows. Add `project_path` field (set to current working directory if NULL).
- `session_journal` - Copy all rows if table exists.

**Session logs:**
- Copy `~/.clams/sessions/*.jsonl` → `~/.calm/sessions/`

**Config:**
- Do NOT migrate `~/.clams/config.yaml` - the new system has its own defaults and the install script handles config creation.

#### 1.3 Migrate CLAWS Data (`.claude/claws.db` → `~/.calm/metadata.db`)

Source: `.claude/claws.db` (orchestration state - tasks, workers, reviews, test runs, counters)
Target: `~/.calm/metadata.db`

**Tables to migrate:**
- `tasks` - Copy all rows. Add `project_path` field (set to absolute path of current git repo root).
- `workers` - Copy all rows. Add `project_path` field.
- `reviews` - Copy all rows directly (schema is compatible).
- `test_runs` - Copy all rows directly (schema is compatible).
- `counters` - Copy all rows. If counter already exists in target (from `calm init`), use the maximum value.
- `phase_history` - Copy if exists (informational, not critical).

**Worktree paths:**
- Convert relative `.worktrees/TASK-ID` paths to absolute paths in task records.

#### 1.4 Ensure CALM Infrastructure

- Run `calm install` logic (or equivalent) to ensure:
  - `~/.calm/` directory structure exists
  - `~/.calm/metadata.db` schema is up to date
  - Role files and workflow templates are copied
  - Qdrant container is running

#### 1.5 Register CALM in Configuration

Use the existing `calm install` config merge functionality:

- Register CALM MCP server in `~/.claude.json`
- Register CALM hooks in `~/.claude/settings.json`
- Remove old CLAMS hook references from `~/.claude/settings.json`
- Remove old CLAMS MCP server from `~/.claude.json` (if present)

#### 1.6 Start CALM Server

- Start the CALM MCP server daemon
- Verify it responds to ping

#### 1.7 Verification

After migration:
- Verify task count matches between old and new databases
- Verify memory count matches
- Verify counter values match
- Verify GHAP entries migrated
- Print summary of migrated data

### 2. CLAUDE.md Update

Replace the current CLAUDE.md (which documents `.claude/bin/claws-*` commands) with a new version that:

- Documents the CALM system and how to activate orchestration via `/orchestrate`
- References `calm` CLI commands instead of `claws-*` bash scripts
- Keeps all the workflow documentation (phases, gates, roles, etc.)
- Documents the `/wrapup` and `/reflection` skills
- Removes all references to `.claude/bin/claws-*` scripts
- Updates specialist role file paths (`.claude/roles/` → `~/.calm/roles/`)
- Removes the "Available Tools" section listing bash scripts and replaces with CALM CLI reference
- Updates the session continuity section to use CALM session tools

The CLAUDE.md should clearly indicate that:
- Running `/orchestrate` at session start activates full workflow mode
- Memory features (GHAP, memories, context assembly) are always active
- The `calm` CLI is available for direct command-line operations

### 3. Verification Test Suite

Add integration tests that verify:
- Migration script correctly transfers data between database schemas
- Counter values are preserved
- Task phase history is maintained
- Memories and GHAP entries survive migration
- Configuration files are updated correctly (MCP server, hooks)

Use temporary directories and mock databases (do not touch real `~/.clams/` or `~/.calm/` in tests).

### 4. Dry Run Mode

The migration script must support `--dry-run` flag that:
- Reports what would be migrated (counts per table)
- Reports what configuration changes would be made
- Does NOT modify any files or databases
- Prints a clear summary

### 5. Backup Before Migration

Before any data modification:
- Create backup of `~/.clams/metadata.db` → `~/.clams/metadata.db.pre-cutover`
- Create backup of `.claude/claws.db` → `.claude/claws.db.pre-cutover`
- Create backup of `~/.claude.json` → `~/.claude.json.pre-cutover`
- Create backup of `~/.claude/settings.json` → `~/.claude/settings.json.pre-cutover`

## Acceptance Criteria

- [ ] Migration script exists at `scripts/cutover.py`
- [ ] Script migrates all CLAMS data (memories, GHAP, sessions) from `~/.clams/` to `~/.calm/`
- [ ] Script migrates all CLAWS data (tasks, workers, reviews, test runs, counters) from `.claude/claws.db` to `~/.calm/metadata.db`
- [ ] Script backs up all source databases and config files before modifying anything
- [ ] Script supports `--dry-run` flag
- [ ] Script is idempotent (running twice produces the same result)
- [ ] Script removes old CLAMS MCP server and hooks from configuration
- [ ] Script registers CALM MCP server and hooks in configuration
- [ ] CLAUDE.md updated to document CALM workflow (no references to `claws-*` scripts)
- [ ] Integration tests verify migration correctness with mock data
- [ ] All existing tests continue to pass
- [ ] After running the script, `calm task list` shows migrated tasks
- [ ] After running the script, `calm memory list` shows migrated memories

## Non-Goals

- Building a reusable migration framework
- Supporting rollback (backups are sufficient)
- Migrating Qdrant vector data (embeddings will be regenerated by the new system)
- Removing old code (SPEC-058-08)

## Technical Notes

- The `calm install` module (`src/calm/install/`) already has config merge utilities (`register_mcp_server`, `register_hooks`, `_clean_old_hooks`). Reuse these.
- The database schemas between old and new are largely compatible. The main difference is the addition of `project_path` columns in the new schema.
- Qdrant vector embeddings do NOT need migration. The new system will re-index as needed. Only the SQLite metadata needs to move.
- The script should be runnable with `python scripts/cutover.py` (no special dependencies beyond what's already in the project).
