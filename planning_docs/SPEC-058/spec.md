# SPEC-058: CALM - Claude Agent Learning & Management

## Vision

Unify CLAWS (workflow orchestration) and CLAMS (learning/memory) into a single system called **CALM** - Claude Agent Learning & Management.

CALM provides Claude Code agents with:
- **Memory**: Persistent knowledge that improves over time
- **Learning**: Structured capture of experiences and insights
- **Orchestration**: Task tracking, phase gates, and workflow management (opt-in)

## Core Principles

1. **Simple mental model**: One system, one namespace, one install
2. **Zero project footprint**: All data in `~/.calm/`, nothing in user's repos
3. **Always-on memory**: Memory features work everywhere, no setup
4. **Opt-in orchestration**: Full workflow available per-session via `/orchestrate`
5. **Stable memories**: Extract durable abstractions, not brittle specifics

## Two Modes

| Mode | Activation | Features |
|------|------------|----------|
| **Memory** | Always on | Memory, GHAP, sessions, /wrapup, /reflection, context assembly |
| **Orchestration** | `/orchestrate` per session | + Tasks, phases, gates, worktrees, workers, reviews |

---

## Architecture

### Directory Structure

```
~/.calm/
├── config.yaml              # User preferences
├── metadata.db              # SQLite: memories, sessions, tasks, GHAP, reviews
├── workflows/
│   └── default.md           # Full orchestration instructions (~500 lines)
├── roles/
│   ├── architect.md
│   ├── backend.md
│   ├── frontend.md
│   ├── reviewer.md
│   ├── qa.md
│   ├── planning.md
│   ├── spec-reviewer.md
│   ├── proposal-reviewer.md
│   ├── bug-investigator.md
│   ├── infra.md
│   ├── doc-writer.md
│   └── ai-dl.md
├── sessions/
│   └── <timestamp>_<uuid>.jsonl   # Copied session logs for reflection
├── server.pid
├── server.log
└── config.env               # Runtime config (written by server)
```

### Database Schema (`metadata.db`)

```sql
-- ===================
-- MEMORY TABLES
-- ===================

CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('preference', 'fact', 'event', 'workflow', 'context', 'error', 'decision')),
    importance REAL DEFAULT 0.5 CHECK (importance >= 0.0 AND importance <= 1.0),
    tags TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    embedding_id TEXT  -- Reference to vector store
);

CREATE INDEX idx_memories_category ON memories(category);
CREATE INDEX idx_memories_importance ON memories(importance);

-- ===================
-- SESSION TABLES
-- ===================

CREATE TABLE session_journal (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    working_directory TEXT NOT NULL,
    project_name TEXT,  -- Last component of path
    session_log_path TEXT,  -- Path to copied log in ~/.calm/sessions/
    summary TEXT NOT NULL,
    friction_points TEXT,  -- JSON array
    next_steps TEXT,  -- JSON array
    reflected_at TEXT,  -- NULL if unreflected
    memories_created INTEGER DEFAULT 0
);

CREATE INDEX idx_journal_reflected ON session_journal(reflected_at);
CREATE INDEX idx_journal_project ON session_journal(project_name);
CREATE INDEX idx_journal_directory ON session_journal(working_directory);

-- ===================
-- GHAP TABLES
-- ===================

CREATE TABLE ghap_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    domain TEXT NOT NULL,
    strategy TEXT NOT NULL,
    goal TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    action TEXT NOT NULL,
    prediction TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'confirmed', 'falsified', 'abandoned')),
    result TEXT,
    surprise TEXT,
    root_cause_category TEXT,
    root_cause_description TEXT,
    lesson_what_worked TEXT,
    lesson_takeaway TEXT,
    iteration_count INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    project_path TEXT
);

CREATE INDEX idx_ghap_status ON ghap_entries(status);
CREATE INDEX idx_ghap_project ON ghap_entries(project_path);

-- ===================
-- ORCHESTRATION TABLES
-- ===================

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    spec_id TEXT,  -- Parent spec if this is a subtask
    task_type TEXT DEFAULT 'feature' CHECK (task_type IN ('feature', 'bug')),
    phase TEXT NOT NULL,
    specialist TEXT,
    notes TEXT,
    blocked_by TEXT,  -- JSON array of task IDs
    worktree_path TEXT,
    project_path TEXT NOT NULL,  -- Associates task with project
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_tasks_phase ON tasks(phase);
CREATE INDEX idx_tasks_project ON tasks(project_path);
CREATE INDEX idx_tasks_type ON tasks(task_type);

CREATE TABLE workers (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed', 'session_ended')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    project_path TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_workers_status ON workers(status);
CREATE INDEX idx_workers_task ON workers(task_id);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    review_type TEXT NOT NULL CHECK (review_type IN ('spec', 'proposal', 'code', 'bugfix')),
    result TEXT NOT NULL CHECK (result IN ('approved', 'changes_requested')),
    worker_id TEXT,
    reviewer_notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_reviews_task ON reviews(task_id);
CREATE INDEX idx_reviews_type ON reviews(review_type);

CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    skipped INTEGER DEFAULT 0,
    duration_seconds REAL,
    failed_tests TEXT,  -- JSON array
    run_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE counters (
    name TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);

-- Initialize counters
INSERT INTO counters (name, value) VALUES ('merge_lock', 0);
INSERT INTO counters (name, value) VALUES ('merges_since_e2e', 0);
INSERT INTO counters (name, value) VALUES ('merges_since_docs', 0);
```

---

## MCP Tools Inventory

### Memory Tools
| Tool | Description |
|------|-------------|
| `store_memory` | Store a memory with category, importance, tags |
| `retrieve_memories` | Semantic search for memories |
| `list_memories` | List memories with filters (non-semantic) |
| `delete_memory` | Delete a memory by ID |

### Session Tools
| Tool | Description |
|------|-------------|
| `store_journal_entry` | Save session summary + copy log |
| `list_journal_entries` | List entries, optionally unreflected only |
| `get_journal_entry` | Get entry details, optionally with full log |
| `mark_entries_reflected` | Mark as reflected, record memory count, delete logs |

### GHAP Tools
| Tool | Description |
|------|-------------|
| `start_ghap` | Begin tracking a hypothesis |
| `update_ghap` | Update active GHAP (hypothesis, prediction, etc.) |
| `resolve_ghap` | Mark as confirmed/falsified/abandoned with learnings |
| `get_active_ghap` | Get current active GHAP if any |
| `list_ghap_entries` | List past GHAP entries with filters |

### Code Tools
| Tool | Description |
|------|-------------|
| `index_codebase` | Index directory for semantic search |
| `search_code` | Semantic code search |
| `find_similar_code` | Find code similar to snippet |

### Git Tools
| Tool | Description |
|------|-------------|
| `index_commits` | Index git commits for search |
| `search_commits` | Semantic commit search |
| `get_file_history` | Get commit history for file |
| `get_churn_hotspots` | Find high-change-frequency files |
| `get_code_authors` | Get author stats for file |

### Learning Tools
| Tool | Description |
|------|-------------|
| `search_experiences` | Search past GHAP experiences |
| `get_clusters` | Get experience clusters by axis |
| `get_cluster_members` | Get experiences in a cluster |
| `validate_value` | Check if value statement fits cluster |
| `store_value` | Store validated value statement |
| `list_values` | List stored values |

### Context Tools
| Tool | Description |
|------|-------------|
| `assemble_context` | Build context from memories + experiences |

### Orchestration Tools (require `/orchestrate`)
| Tool | Description |
|------|-------------|
| `task_create` | Create a task |
| `task_list` | List tasks for current project |
| `task_show` | Show task details |
| `task_update` | Update task fields |
| `task_transition` | Transition task to new phase |
| `task_delete` | Delete a task |
| `gate_check` | Run gate checks for transition |
| `gate_list` | List gate requirements |
| `worktree_create` | Create git worktree for task |
| `worktree_list` | List worktrees |
| `worktree_path` | Get worktree path for task |
| `worktree_merge` | Merge worktree to main |
| `worktree_remove` | Remove worktree without merge |
| `worker_start` | Register worker start |
| `worker_complete` | Mark worker completed |
| `worker_fail` | Mark worker failed |
| `worker_list` | List workers |
| `review_record` | Record a review result |
| `review_list` | List reviews for task |
| `review_check` | Check if reviews pass gate |
| `counter_get` | Get counter value |
| `counter_set` | Set counter value |
| `counter_increment` | Increment counter |

### Session Tools
| Tool | Description |
|------|-------------|
| `ping` | Health check |
| `start_session` | Initialize session |
| `get_orphaned_ghap` | Check for orphaned GHAP from previous session |
| `get_project_tasks` | Get tasks for current working directory |

---

## CLI Commands

All commands implemented in Python, sharing code with MCP server.

```bash
# Memory
calm memory store "content" --category fact --importance 0.8
calm memory search "query"
calm memory list --category error

# Sessions
calm session list
calm session show <id>

# GHAP
calm ghap status
calm ghap list --domain debugging

# Tasks (orchestration)
calm task list
calm task create SPEC-001 "Feature title"
calm task show SPEC-001
calm task update SPEC-001 --phase DESIGN
calm task transition SPEC-001 IMPLEMENT --gate-result pass
calm task delete SPEC-001

# Gates
calm gate check SPEC-001 IMPLEMENT-CODE_REVIEW
calm gate list

# Worktrees
calm worktree create SPEC-001
calm worktree list
calm worktree path SPEC-001
calm worktree merge SPEC-001
calm worktree remove SPEC-001

# Workers
calm worker start SPEC-001 backend
calm worker complete W-123
calm worker list

# Reviews
calm review record SPEC-001 code approved
calm review list SPEC-001
calm review check SPEC-001 code

# Counters
calm counter list
calm counter get merges_since_e2e
calm counter set merge_lock 1

# Server
calm server start
calm server stop
calm server status

# System
calm status          # Overall system status
calm init            # First-time setup (creates ~/.calm/)
calm migrate         # Migrate from claws/clams
```

---

## Hooks

### SessionStart Hook

**Trigger**: New Claude Code session starts

**Behavior**:
1. Ensure CALM daemon is running (start if needed)
2. Check for orphaned GHAP from previous session
3. Query tasks for current `$PWD`
4. Inject lightweight context

**Output** (~50-100 tokens):
```
CALM (Claude Agent Learning & Management) is available.

Always active: /wrapup, /reflection, memory tools

This project: 3 active tasks (SPEC-058 DESIGN, BUG-042 FIXED, SPEC-059 IMPLEMENT)
Run /orchestrate to manage tasks and enable full workflow.
```

Or if no tasks:
```
CALM is available.

Always active: /wrapup, /reflection, memory tools
Run /orchestrate to enable task tracking and workflow tools.
```

### UserPromptSubmit Hook

**Trigger**: User submits a prompt

**Behavior**:
1. Call `assemble_context` with user prompt
2. Inject relevant memories and experiences

**Output**: Relevant context from past experiences (memories, GHAP learnings, values).

### PreToolUse Hook

**Trigger**: Before any tool execution

**Behavior**:
1. Check if GHAP is active and reminder is due
2. If so, inject reminder to check/update GHAP

**Output** (when reminder due):
```
GHAP Check-in: You have an active hypothesis. Is it still valid? Consider updating or resolving.
```

### PostToolUse Hook

**Trigger**: After test commands (pytest, npm test, cargo test)

**Behavior**:
1. Parse test results
2. If GHAP active, compare prediction to outcome
3. Suggest confirming/falsifying hypothesis

**Output**:
```
Test PASSED. Your prediction was: "Tests will pass after fixing the await."
Does this confirm your hypothesis? Consider resolving GHAP as CONFIRMED.
```

---

## Skills

### `/orchestrate` Skill

**Trigger**: User runs `/orchestrate`

**Behavior**:
1. Read `~/.calm/workflows/default.md`
2. Inject full orchestration instructions into context
3. List current tasks for project

**Output**:
```
Orchestration mode activated.

[Full workflow instructions injected - phases, gates, roles, commands]

Current tasks for /Users/you/project:
- SPEC-058: DESIGN - Waiting for proposal review
- BUG-042: FIXED - Ready for code review

Use `calm task`, `calm gate`, `calm worktree` commands to manage work.
```

### `/wrapup` Skill

**Trigger**: User runs `/wrapup` or `/wrapup continue`

**Behavior**:
1. Analyze conversation for summary, friction points, next steps
2. Identify current session log file:
   - Map `$PWD` to Claude project path format
   - Find most recent `.jsonl` in `~/.claude/projects/<mapped>/`
3. Copy session log to `~/.calm/sessions/<timestamp>_<uuid>.jsonl`
4. Call `store_journal_entry` MCP tool
5. If orchestration active:
   - Auto-commit staged changes in worktrees
   - Generate next-commands based on task phases
6. Report to user

**Output**:
```
## Session Wrapped Up

**Summary**: Designed CALM unified system, wrote SPEC-058...

**Friction Points**:
- Hook paths mismatched after rename
- Design iterations needed for clean model

**Next Steps**:
- Enrich SPEC-058 with technical details
- Create migration plan

Journal entry saved: 2026-02-01T11-30-00_abc123

[If orchestration active:]
**Auto-committed**: SPEC-058 (3 files)
**Next commands**:
  calm gate check SPEC-058 DESIGN-IMPLEMENT
```

### `/reflection` Skill

**Trigger**: User runs `/reflection`

**Behavior**:
1. Load unreflected journal entries via `list_journal_entries(unreflected_only=True)`
2. For each entry, load session log via `get_journal_entry(include_log=True)`
3. Dispatch 4 analysis agents in parallel (see below)
4. Collect and deduplicate proposals (semantic similarity > 0.85 = duplicate)
5. Present batch approval UI
6. Store approved memories via `store_memory`
7. Mark entries reflected via `mark_entries_reflected`

**Batch Approval UI**:
```
## Proposed Memories from 5 Sessions

### Debugging Insights (3)
[x] 1. [error] When async tests hang, check for missing `await` on database calls
    Source: Session 2026-02-01 (clams project)

[x] 2. [error] Import errors after refactoring often indicate circular dependencies
    Source: Session 2026-01-30 (clams project)

[ ] 3. [decision] (Skipped - too specific)

### Codebase Knowledge (2)
[x] 4. [fact] MCP tools are registered via a dispatcher pattern, not direct server methods
    Source: Session 2026-02-01 (clams project)

[x] 5. [fact] Pydantic-settings classes read from environment variables automatically
    Source: Session 2026-01-29 (clams project)

### Workflow Patterns (1)
[x] 6. [workflow] Run type checker before tests to catch errors faster
    Source: Session 2026-01-30 (clams project)

---
Enter numbers to toggle, 'a' to select all, 'n' to select none, or 'done':
```

---

## Reflection Analysis Agents

### Agent 1: Debugging Analyst

**Focus**: Root causes, misleading symptoms, what fixed things

**Prompt**:
```
You are analyzing coding session logs to extract debugging insights.

Focus on:
- What was the root cause of problems encountered?
- What symptoms were misleading or red herrings?
- What approaches worked vs. didn't work?
- What would help diagnose similar issues faster?

CRITICAL: Extract STABLE insights, not brittle specifics.
- BAD: "The bug was on line 234 of user.py"
- GOOD: "Async context managers must be awaited even in decorator usage"
- BAD: "Fixed by changing the config port"
- GOOD: "Port conflicts often indicate stale processes; check with lsof"

For each insight, provide:
- content: The memory text (principle/pattern, not specifics)
- category: "error" or "decision"
- importance: 0.0-1.0 (higher = more broadly applicable)
- reasoning: Why this is worth remembering

Session summary: {summary}
Friction points: {friction_points}
Full log: {session_log}
```

### Agent 2: Codebase Cartographer

**Focus**: Stable architectural knowledge

**Prompt**:
```
You are analyzing coding session logs to extract codebase knowledge.

Focus on:
- How do major systems/components work?
- What are the architectural patterns in use?
- What conventions does the codebase follow?
- What mental models help navigate the code?

CRITICAL: Extract STABLE abstractions only.
- BAD: "Config is in src/config.py with 5 settings"
- GOOD: "Configuration uses pydantic-settings; env vars override defaults"
- BAD: "The User class has 12 methods"
- GOOD: "Domain models in models/, business logic in services/"
- BAD: "Function foo() calls bar() then baz()"
- GOOD: "Request lifecycle: middleware → router → handler → response"

Avoid:
- File paths, line numbers, counts
- Implementation details that change frequently
- Version numbers or dependency specifics

For each insight, provide:
- content: The memory text (architectural pattern or convention)
- category: "fact"
- importance: 0.0-1.0 (higher = more foundational)
- reasoning: Why this abstraction is stable and useful

Session summary: {summary}
Friction points: {friction_points}
Full log: {session_log}
```

### Agent 3: Process Observer

**Focus**: Workflow patterns, efficiency insights

**Prompt**:
```
You are analyzing coding session logs to extract workflow insights.

Focus on:
- What workflows or processes were efficient?
- What caused friction or wasted time?
- What tool usage patterns were effective?
- What order of operations worked well?

For each insight, provide:
- content: The memory text (process or workflow pattern)
- category: "workflow" or "preference"
- importance: 0.0-1.0 (higher = more time saved)
- reasoning: Why this workflow insight matters

Session summary: {summary}
Friction points: {friction_points}
Full log: {session_log}
```

### Agent 4: Pattern Detector

**Focus**: Recurring themes, anti-patterns to avoid

**Prompt**:
```
You are analyzing coding session logs to detect patterns and anti-patterns.

Focus on:
- What themes or issues recur across the session(s)?
- What mistakes were made that should be avoided?
- What approaches consistently work well?
- What "rules of thumb" emerge from this experience?

CRITICAL: Look for GENERALIZABLE patterns.
- BAD: "Don't forget to update the config file"
- GOOD: "After adding settings, verify they load by checking startup logs"
- BAD: "The test was flaky"
- GOOD: "Flaky tests often indicate shared state; check for missing isolation"

For each insight, provide:
- content: The memory text (pattern or anti-pattern)
- category: "decision" or "fact"
- importance: 0.0-1.0 (higher = more likely to recur)
- reasoning: Why this pattern is worth encoding

Session summary: {summary}
Friction points: {friction_points}
Full log: {session_log}
```

---

## Configuration

### User Config (`~/.calm/config.yaml`)

```yaml
# User preferences
default_importance: 0.5
reflection_batch_size: 10  # Max sessions per reflection

# Server settings
server:
  host: 127.0.0.1
  port: 6335
  log_level: info

# Embedding settings
embedding:
  code_model: sentence-transformers/all-MiniLM-L6-v2
  semantic_model: nomic-ai/nomic-embed-text-v1.5

# Qdrant settings
qdrant:
  url: http://localhost:6333
```

---

## Installation

### Prerequisites
- Python 3.12+
- Docker (for Qdrant)
- uv (Python package manager)
- jq (JSON processor)

### Install Script (`scripts/install.sh`)

```bash
#!/bin/bash
# CALM Installation Script

set -euo pipefail

echo "Installing CALM..."

# 1. Create directory structure
mkdir -p ~/.calm/{workflows,roles,sessions}

# 2. Install Python package
uv pip install -e .

# 3. Start Qdrant (if not running)
if ! docker ps | grep -q qdrant; then
    docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
fi

# 4. Initialize database
calm init

# 5. Copy workflow and role files
cp -r workflows/* ~/.calm/workflows/
cp -r roles/* ~/.calm/roles/

# 6. Register MCP server in ~/.claude.json
# (Add calm server config)

# 7. Register hooks in ~/.claude/settings.json
# (Add SessionStart, UserPromptSubmit, PreToolUse, PostToolUse hooks)

# 8. Start server daemon
calm server start

echo "CALM installed successfully!"
echo "Run 'calm status' to verify."
```

---

## Migration

### From Current CLAWS/CLAMS State

```bash
#!/bin/bash
# Migration script: claws + clams → calm

echo "Migrating to CALM..."

# 1. Stop old server
pkill -f "clams.server" || true

# 2. Create new structure
mkdir -p ~/.calm/{workflows,roles,sessions}

# 3. Migrate CLAMS data
if [ -d ~/.clams ]; then
    # Copy metadata
    cp ~/.clams/metadata.db ~/.calm/ 2>/dev/null || true
    # Copy journals
    cp -r ~/.clams/journal/* ~/.calm/sessions/ 2>/dev/null || true
fi

# 4. Migrate CLAWS data (from any project)
# Tasks, workers, reviews get merged into ~/.calm/metadata.db
# (SQL migration script)

# 5. Update hooks
# Replace clams_scripts/hooks paths with calm paths

# 6. Update MCP server registration
# Change mcp__clams__* to mcp__calm__*

# 7. Rename Python package
# src/clams → src/calm

echo "Migration complete!"
```

### Rename Inventory

Files/locations requiring `clams`/`claws` → `calm` rename:

| Category | Items |
|----------|-------|
| **Python package** | `src/clams/` → `src/calm/`, all imports |
| **pyproject.toml** | Package name, entry points |
| **MCP tools** | All `mcp__clams__*` tool names |
| **Hook scripts** | `clams_scripts/hooks/` → `calm/hooks/` or `src/calm/hooks/` |
| **Hook config** | `~/.claude/settings.json` paths |
| **MCP config** | `~/.claude.json` server name |
| **Database** | `~/.clams/` → `~/.calm/` |
| **CLI scripts** | `.claude/bin/claws-*` → eliminated (Python CLI) |
| **Documentation** | README.md, all specs, CLAUDE.md |
| **Tests** | All test files importing clams |
| **Config files** | Any referencing old paths |

---

## Acceptance Criteria

### Consolidation
- [ ] Python package renamed `clams` → `calm`
- [ ] All MCP tools renamed `mcp__clams__*` → `mcp__calm__*`
- [ ] CLI implemented in Python (`calm task`, `calm gate`, etc.)
- [ ] All bash scripts eliminated or converted
- [ ] All data moved to `~/.calm/`
- [ ] No project-level files required
- [ ] pyproject.toml updated with new package name and entry points

### Memory Features
- [ ] Session journaling via `/wrapup`
- [ ] Session log capture to `~/.calm/sessions/`
- [ ] `/reflection` with multi-agent analysis
- [ ] Batch approval UI for memories
- [ ] Session logs deleted after reflection
- [ ] `assemble_context` includes memories and experiences

### Orchestration Features
- [ ] `/orchestrate` skill injects workflow context
- [ ] Tasks stored centrally with project_path
- [ ] Session start hook announces existing tasks
- [ ] Phases, gates, worktrees, workers, reviews all functional
- [ ] Counter system for batch job triggers

### Hooks
- [ ] SessionStart: CALM awareness + task count for project
- [ ] UserPromptSubmit: memory/experience context injection
- [ ] PreToolUse: GHAP check-in reminder
- [ ] PostToolUse: test outcome capture

### Database
- [ ] All tables created per schema
- [ ] Indexes for performance
- [ ] Foreign keys enforced

### CLI
- [ ] All commands implemented
- [ ] Shares code with MCP server
- [ ] Proper error handling and output

---

## Implementation Strategy

### Build Alongside, Don't Replace

Since we use CLAWS/CLAMS to orchestrate this work, we cannot break those systems mid-implementation. The safe approach:

1. **Create `calm` as a new package** alongside `clams` (not a rename)
2. **Keep clams/claws running** throughout development
3. **Test calm thoroughly** before switching
4. **Cut over atomically** when calm is fully functional
5. **Remove old code** only after cutover is verified

This ensures zero risk of breaking our workflow during development.

### Implementation Phases

| Phase | Scope | Deliverables |
|-------|-------|--------------|
| **1. Foundation** | Package structure, core infrastructure | `src/calm/`, pyproject.toml entry points, `calm init`, `calm server start/stop/status`, `~/.calm/` directory structure |
| **2. Memory/GHAP** | Port memory and learning features | Memory CRUD, GHAP tracking, code/git indexing, semantic search, context assembly |
| **3. Orchestration CLI** | Replace bash scripts with Python CLI | `calm task`, `calm gate`, `calm worktree`, `calm worker`, `calm review`, `calm counter` |
| **4. Session & Reflection** | Session journaling and learning loop | `store_journal_entry`, `list_journal_entries`, `/wrapup` skill, `/reflection` skill with multi-agent analysis, batch approval UI |
| **5. Skills & Hooks** | Orchestration activation, hook scripts | `/orchestrate` skill, SessionStart hook, UserPromptSubmit hook, PreToolUse hook, PostToolUse hook |
| **6. Install Script** | Fresh installation support | `scripts/install.sh` (creates dirs, registers MCP server, registers hooks, starts daemon) |
| **7. Cutover** | Switch from old to new system | One-off migration script, update `~/.claude.json`, update `~/.claude/settings.json`, verification testing |
| **8. Cleanup** | Remove deprecated code | Delete `src/clams/`, `.claude/bin/claws-*`, `clams_scripts/`, old hook references |

### Phase Dependencies

```
Phase 1 (Foundation)
    ↓
Phase 2 (Memory/GHAP) ←──────┐
    ↓                        │
Phase 3 (Orchestration CLI)  │ (can parallelize 2 & 3)
    ↓                        │
Phase 4 (Session & Reflection)
    ↓
Phase 5 (Skills & Hooks)
    ↓
Phase 6 (Install Script)
    ↓
Phase 7 (Cutover)
    ↓
Phase 8 (Cleanup)
```

Phases 2 and 3 can potentially run in parallel since they're largely independent.

### Migration Approach

**Decision**: One-off script, not a feature.

Since this is a greenfield codebase with no external users, building `calm migrate` as a robust feature would be over-engineering. Instead:

1. Write a one-off migration script when ready for cutover
2. Script copies `~/.clams/` data → `~/.calm/`
3. Script merges `.claude/claws.db` → `~/.calm/metadata.db`
4. Run once, verify, delete the script

No need to handle edge cases, versioning, or hypothetical user scenarios.

---

## Out of Scope (Future)

- Public launch / distribution
- Multiple workflow definitions (just `default.md` for now)
- GUI / web interface
- Team/shared memory features
- Automatic orchestration activation (always manual via `/orchestrate`)

---

## Summary

CALM = CLAWS + CLAMS unified.

- **Memory always works, everywhere** - no setup needed
- **Orchestration opt-in per session** - `/orchestrate` when you need it
- **All data in `~/.calm/`** - zero project footprint
- **Python CLI + MCP server** - single codebase, well-tested
- **`/wrapup` → journal → `/reflection` → memories** - learning loop
- **Clean, simple, powerful**
