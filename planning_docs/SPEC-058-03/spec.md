# SPEC-058-03: CALM Orchestration CLI - Python CLI replacing bash scripts

## Overview

Replace the current bash-based CLAWS orchestration scripts (`.claude/bin/claws-*`) with a Python CLI implemented in the calm package. This provides task management, worktree handling, gate checks, worker tracking, and review recording through the `calm` command.

## Background

The current orchestration system uses 15+ bash scripts in `.claude/bin/claws-*`. These work but:
- Are difficult to test
- Have inconsistent error handling
- Duplicate logic that could be shared with MCP tools
- Require shell execution from Claude Code

Moving to Python allows:
- Shared code between CLI and MCP tools
- Proper error handling and typing
- Testable business logic
- Cleaner maintenance

## Scope

### In Scope

1. **Task Commands** (`calm task`)
   - `calm task create <id> <title> [--spec <spec_id>] [--type feature|bug]`
   - `calm task list [--phase <phase>] [--type feature|bug]`
   - `calm task show <id>`
   - `calm task update <id> --phase|--specialist|--notes|--blocked-by <value>`
   - `calm task transition <id> <phase> [--gate-result pass|fail] [--gate-details <text>]`
   - `calm task delete <id>`

2. **Gate Commands** (`calm gate`)
   - `calm gate check <task_id> <transition>` - Run gate checks
   - `calm gate list` - List gate requirements

3. **Worktree Commands** (`calm worktree`)
   - `calm worktree create <task_id>` - Create isolated worktree
   - `calm worktree list` - List all worktrees
   - `calm worktree path <task_id>` - Get worktree path
   - `calm worktree merge <task_id>` - Merge to main and cleanup
   - `calm worktree remove <task_id>` - Remove without merge

4. **Worker Commands** (`calm worker`)
   - `calm worker start <task_id> <role>` - Register worker start
   - `calm worker complete <worker_id>` - Mark worker completed
   - `calm worker fail <worker_id>` - Mark worker failed
   - `calm worker list` - List workers
   - `calm worker context <task_id> <role>` - Get worker context
   - `calm worker prompt <role>` - Get role prompt

5. **Review Commands** (`calm review`)
   - `calm review record <task_id> <type> <result> [--worker <id>]` - Record review
   - `calm review list <task_id>` - List reviews for task
   - `calm review check <task_id> <type>` - Check if reviews pass gate
   - `calm review clear <task_id> [<type>]` - Clear reviews

6. **Counter Commands** (`calm counter`)
   - `calm counter list` - Show all counters
   - `calm counter get <name>` - Get counter value
   - `calm counter set <name> <value>` - Set counter value
   - `calm counter increment <name>` - Increment by 1
   - `calm counter add <name> [value]` - Create new counter
   - `calm counter reset <name>` - Reset to 0

7. **Status Commands** (extend existing)
   - `calm status` - Full system status (tasks, health, counters)
   - `calm status health` - System health check
   - `calm status worktrees` - Active worktrees

8. **Backup Commands** (`calm backup`)
   - `calm backup create [name]` - Create named backup
   - `calm backup list` - List available backups
   - `calm backup restore <name>` - Restore from backup
   - `calm backup auto` - Auto-backup (keeps last 10)

9. **Session Commands** (`calm session`)
   - `calm session save [--continue]` - Save handoff from stdin
   - `calm session list` - List recent sessions
   - `calm session show <id>` - Show session's handoff

### Out of Scope

- MCP tool implementations for orchestration - those use CLI internally
- Gate check scripts themselves (pytest, mypy, etc.) - existing scripts continue
- Session journaling for `/wrapup` - covered in SPEC-058-04
- `/reflection` skill - covered in SPEC-058-04
- Memory/GHAP CLI commands - covered in SPEC-058-02
- `calm init` - Already implemented in SPEC-058-01
- `calm migrate` - One-off migration script, not a permanent CLI command (see SPEC-058-07)

## Technical Approach

### Architecture

```
src/calm/cli/
├── main.py           # Root CLI group (exists from SPEC-058-01)
├── task.py           # Task subcommands
├── gate.py           # Gate subcommands
├── worktree.py       # Worktree subcommands
├── worker.py         # Worker subcommands
├── review.py         # Review subcommands
├── counter.py        # Counter subcommands
├── backup.py         # Backup subcommands
├── session.py        # Session subcommands
└── status.py         # Status subcommands (extend existing)

src/calm/orchestration/
├── tasks.py          # Task business logic
├── gates.py          # Gate checking logic
├── worktrees.py      # Git worktree management
├── workers.py        # Worker tracking
├── reviews.py        # Review tracking
├── counters.py       # Counter management
└── phases.py         # Phase definitions and transitions
```

### Database Tables

The tables were already created in SPEC-058-01:
- `tasks` - Task tracking with phase, type, blocked_by
- `workers` - Worker registration and status
- `reviews` - Review results
- `test_runs` - Test run history
- `counters` - System counters
- `sessions` - Session handoff storage (note: separate from `session_journal` which is for memory/reflection in SPEC-058-04)

#### Phase Transitions Table

Need to add this table for phase history tracking:

```sql
CREATE TABLE phase_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    gate_result TEXT,  -- 'pass' or 'fail'
    gate_details TEXT,
    transitioned_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_transitions_task ON phase_transitions(task_id);
```

#### Sessions vs Session Journal

- `sessions` table: Stores **orchestration handoffs** (task status snapshots, next commands) - used by this task
- `session_journal` table: Stores **memory/learning journal entries** (summaries, friction points, session logs) - used by SPEC-058-04

These are distinct purposes: orchestration continuity vs. memory extraction.

#### Backups

Backup metadata will be stored in the filesystem (`~/.calm/backups/`) rather than a database table. Each backup is a timestamped copy of `metadata.db`.

### Project Path Handling

Orchestration is project-specific. The CLI will:
1. Detect `project_path` from current working directory
2. Filter tasks/workers/etc. to that project
3. Store `project_path` when creating tasks

This allows CALM to manage multiple projects from a single `~/.calm/metadata.db`.

### Gate Check Integration

The `calm gate check` command will:
1. Determine gate requirements from phase transition
2. Execute existing gate check scripts (pytest, mypy, ruff, etc.)
3. Parse and log results to database
4. Return pass/fail status

Gate check scripts can be reused from current CLAWS or converted to Python later.

### Worktree Management

Uses git's worktree feature:
- `git worktree add .worktrees/<task_id> -b <task_id>`
- `git worktree remove .worktrees/<task_id>`
- Merge via `git merge <task_id>` on main

### CLI Framework

Uses Click (already a dependency from SPEC-058-01):
- Subcommand groups for organization
- Consistent error handling
- Help text auto-generation

## Acceptance Criteria

1. [ ] `calm task` commands all functional (create, list, show, update, transition, delete)
2. [ ] `calm gate` commands all functional (check, list)
3. [ ] `calm worktree` commands all functional (create, list, path, merge, remove)
4. [ ] `calm worker` commands all functional (start, complete, fail, list, context, prompt)
5. [ ] `calm review` commands all functional (record, list, check, clear)
6. [ ] `calm counter` commands all functional (list, get, set, increment, add, reset)
7. [ ] `calm status` extended with health, worktrees
8. [ ] `calm backup` commands all functional (create, list, restore, auto)
9. [ ] `calm session` commands all functional (save, list, show)
10. [ ] All commands use `~/.calm/metadata.db`
11. [ ] Commands are project-aware (filter by current directory)
12. [ ] Existing claws scripts unchanged (runs in parallel)
13. [ ] Tests for all CLI commands
14. [ ] All code passes mypy --strict

## Dependencies

- **SPEC-058-01**: Foundation must be complete (DONE)
- **Git**: For worktree operations
- **Role files**: `calm worker prompt` and `calm worker context` require role files in `~/.calm/roles/`. These are copied from the repo during installation (SPEC-058-06) or can be manually placed for testing.

## Migration Path

The CLI will coexist with claws scripts during development:
1. Implement calm CLI commands
2. Test thoroughly
3. In SPEC-058-07 (Cutover), update CLAUDE.md to use `calm` commands
4. In SPEC-058-08 (Cleanup), remove `.claude/bin/claws-*` scripts

## Risks

1. **Gate check compatibility** - Need to ensure gate checks work from new paths
2. **Worktree path consistency** - Current scripts expect `.worktrees/` in project root

## Notes

- Focus on parity first, improvements later
- Keep claws scripts running during development
- Gate check scripts can remain as bash (subprocess from Python)
