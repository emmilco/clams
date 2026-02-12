# CALM System Audit

> Comprehensive audit of the CALM (Claude Agent Learning & Memory) codebase.
> Generated 2026-02-09. Covers all source files in `src/calm/`.

## Table of Contents

1. [Overview](#overview)
2. [Project Configuration](#project-configuration)
3. [Architecture](#architecture)
4. [Core Infrastructure](#core-infrastructure)
5. [Domain Packages](#domain-packages)
6. [MCP Server & Tools](#mcp-server--tools)
7. [CLI & Orchestration](#cli--orchestration)
8. [Hooks & Integration](#hooks--integration)
9. [Installation System](#installation-system)
10. [Test Suite](#test-suite)
11. [Data Flow](#data-flow)
12. [Configuration & Settings](#configuration--settings)

---

## Overview

CALM is a development productivity system that gives Claude Code persistent memory, structured problem-solving, and multi-agent orchestration capabilities. It consists of:

- **MCP Server**: HTTP server (port 6335) exposing 42 tools via the Model Context Protocol
- **CLI**: `calm` command for orchestration management (tasks, worktrees, gates, reviews, sessions)
- **Hooks**: 4 Claude Code hook points for automatic context injection and GHAP tracking
- **Vector Database**: Qdrant for semantic search across 8 collections
- **SQLite Database**: `~/.calm/metadata.db` for orchestration state (tasks, workers, reviews, sessions, counters)

**Language**: Python 3.12+, async-first architecture
**Package Manager**: uv
**Test Framework**: pytest (1852 tests passing)
**Source Layout**: `src/calm/` with 14 subpackages, ~100 Python modules

---

## Project Configuration

**File**: `pyproject.toml`

The project is named `calm` (formerly `clams`), version managed via `__init__.py`. Key dependencies:

| Category | Libraries |
|----------|-----------|
| Embedding | sentence-transformers, torch, numpy |
| Vector DB | qdrant-client |
| Code Parsing | tree-sitter + language grammars (python, typescript, javascript, rust, swift, java, c, cpp, sql) |
| Git | GitPython |
| Clustering | hdbscan, scikit-learn |
| Server | mcp, starlette, uvicorn, httpx |
| Async I/O | aiofiles |
| Logging | structlog |
| CLI | Click |
| Config | PyYAML, pydantic-settings |

Entry points:
- `calm` CLI → `calm.cli.main:cli`
- `python -m calm` → `calm.__main__`

---

## Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        Claude Code Session                       │
│                                                                  │
│  Hooks (stdin/stdout)              MCP Tools (HTTP)              │
│  ├─ SessionStart                   ├─ mcp__calm__store_memory    │
│  ├─ UserPromptSubmit               ├─ mcp__calm__search_code     │
│  ├─ PreToolUse                     ├─ mcp__calm__start_ghap      │
│  └─ PostToolUse                    └─ ... (42 tools total)       │
└────────┬──────────────────────────────────────┬──────────────────┘
         │                                      │
         │ (subprocess, stdin/stdout)            │ (HTTP POST /mcp)
         ▼                                      ▼
┌─────────────────────┐              ┌──────────────────────────────┐
│  Hook Scripts        │              │  MCP Server (port 6335)      │
│  calm.hooks.*        │              │  calm.server.app             │
│                      │              │                              │
│  Reads:              │              │  Services:                   │
│  - metadata.db       │              │  ├─ EmbeddingRegistry        │
│  - current_ghap.json │              │  │  ├─ MiniLM (code)         │
│  - tool_count        │              │  │  └─ Nomic (semantic)      │
│                      │              │  ├─ QdrantVectorStore        │
└─────────────────────┘              │  ├─ MetadataStore (SQLite)   │
                                      │  ├─ CodeIndexer              │
┌─────────────────────┐              │  ├─ GitAnalyzer              │
│  CLI (calm)          │              │  ├─ ExperienceClusterer      │
│  calm.cli.main       │              │  ├─ ValueStore               │
│                      │              │  ├─ Searcher                 │
│  Commands:           │              │  └─ ContextAssembler         │
│  - task, worker      │              └──────────┬───────────────────┘
│  - worktree, gate    │                         │
│  - review, session   │                         │
│  - backup, counter   │              ┌──────────┴───────────────────┐
│  - status, server    │              │                              │
└──────────┬──────────┘              │  ┌────────────┐  ┌─────────┐│
           │                          │  │  Qdrant    │  │ SQLite  ││
           │                          │  │  (6333)    │  │ meta.db ││
           └──────────────────────────┼─▶│  8 collect │  │         ││
                                      │  └────────────┘  └─────────┘│
                                      └──────────────────────────────┘
```

### Package Map

```
src/calm/
├── __init__.py          # Package version
├── __main__.py          # python -m calm entry point
├── config.py            # Pydantic settings (paths, ports, model names)
├── cli/                 # Click CLI commands (14 files)
├── clustering/          # HDBSCAN experience clustering (4 files)
├── context/             # Context assembly with token budgets (7 files)
├── db/                  # SQLite connection and schema (3 files)
├── embedding/           # Embedding models: MiniLM, Nomic, Mock (6 files)
├── ghap/                # Goal-Hypothesis-Action-Prediction tracking (6 files)
├── git/                 # GitPython reader + analyzer (4 files)
├── hooks/               # Claude Code hook scripts (7 files)
├── indexers/            # Tree-sitter code parsing + indexing (5 files)
├── install/             # 10-step installation system (6 files)
├── orchestration/       # Task/worker/gate/review management (12 files)
├── search/              # Unified semantic search across collections (4 files)
├── server/              # MCP HTTP server + daemon (4 files)
├── storage/             # Vector store (Qdrant) + metadata (SQLite) (5 files)
├── templates/           # Role/workflow/skill templates (28 files)
├── tools/               # MCP tool implementations (12 files)
├── utils/               # Platform detection (2 files)
└── values/              # Value store with cluster validation (3 files)
```

---

## Core Infrastructure

### Configuration (`calm/config.py`)

Pydantic settings loaded from `~/.calm/config.yaml` with environment variable overrides (`CALM_*`).

Key settings:
- **Paths**: `calm_dir` (~/.calm), `db_path`, `pid_file`, `log_file`, `journal_dir`, `roles_dir`
- **Server**: `server_host` (127.0.0.1), `server_port` (6335)
- **Qdrant**: `qdrant_url` (http://localhost:6333)
- **Models**: `code_model` (sentence-transformers/all-MiniLM-L6-v2), `semantic_model` (nomic-ai/nomic-embed-text-v1.5)
- **Context Assembly**: `source_weights`, `similarity_threshold` (0.85), `max_item_fraction` (0.25), `max_fuzzy_content_length`
- **Limits**: `memory_content_max_length` (10000), `batch_size`

### Database (`calm/db/`)

**Schema** (`schema.py`): SQLite database at `~/.calm/metadata.db` with tables:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `tasks` | Feature/bug tracking | id, title, phase, task_type, spec_id, worktree_path, blocked_by (JSON), project_path |
| `workers` | Worker lifecycle | id, task_id, role, status, started_at, ended_at, project_path |
| `reviews` | 2x review gate tracking | id, task_id, review_type, result, worker_id, reviewer_notes |
| `sessions` | Session handoff | id, handoff_content, needs_continuation, resumed_at |
| `counters` | Merge/batch counters | name, value |
| `backups` | DB backup registry | id, name, path, size |
| `test_results` | Gate check test output | id, task_id, transition, passed, failed, duration_ms, output |
| `journal_entries` | Session journals | id, summary, friction_points, next_steps, reflected_at |
| `memories` | Memory metadata | id, category, importance, tags, content (first 200 chars) |
| `ghap_entries` | GHAP metadata | id, session_id, domain, strategy, status, goal, hypothesis |
| `code_metadata` | File indexing state | project, file_path, file_hash, unit_count, last_modified |
| `git_index_state` | Commit indexing state | key, value (last_indexed_sha, count) |

**Connection** (`connection.py`): Context manager with WAL mode, foreign keys enabled, row factory.

### Storage (`calm/storage/`)

**Base** (`base.py`): Abstract `VectorStore` interface:
- `create_collection(name, dimension, distance)` - Create vector collection
- `upsert(collection, id, vector, payload)` - Insert/update point
- `search(collection, query, limit, filters)` - Semantic search
- `delete(collection, id)` - Delete point
- `scroll(collection, limit, offset, filters)` - Paginated browse
- `get(collection, id)` - Point lookup
- `collection_exists(collection)` - Check existence
- Returns `SearchResult(id, score, payload)` dataclass

**Qdrant** (`qdrant.py`): Production implementation using `qdrant_client.AsyncQdrantClient`. Cosine distance, REST transport, 30s timeout. Supports filter conditions (match, range, datetime range). Handles `UnexpectedResponse` for 404/409 cases.

**Memory** (`memory.py`): In-memory implementation (`MemoryStore`) for testing. Dict-based storage with numpy cosine similarity search. Supports all filter types.

**Metadata** (`metadata.py`): SQLite wrapper for file indexing and git state. Tracks code file hashes for incremental indexing, git index SHA for incremental commit indexing.

### Embedding (`calm/embedding/`)

**Dual-model architecture** via `EmbeddingRegistry`:

| Embedder | Model | Dimension | Purpose |
|----------|-------|-----------|---------|
| Code | all-MiniLM-L6-v2 | 384 | Code indexing and search |
| Semantic | nomic-embed-text-v1.5 | 768 | Memories, GHAP, values, commits |
| Mock | MD5 hash-based | configurable | Deterministic test vectors |

Both real models:
- Use `sentence-transformers` library
- Force CPU on macOS (MPS memory leak workaround)
- Run encoding in `asyncio.run_in_executor()` to avoid blocking event loop
- Lazy-loaded on first use (PyTorch must not load before daemon fork)

---

## Domain Packages

### GHAP Tracking (`calm/ghap/`)

GHAP (Goal-Hypothesis-Action-Prediction) provides structured problem-solving tracking.

**Data Model** (`models.py`):
- `Domain` enum: 9 domains (debugging, refactoring, feature, testing, configuration, documentation, performance, security, integration)
- `Strategy` enum: 9 strategies (systematic-elimination, trial-and-error, research-first, divide-and-conquer, root-cause-analysis, copy-from-similar, check-assumptions, read-the-error, ask-user)
- `OutcomeStatus` enum: CONFIRMED, FALSIFIED, ABANDONED
- `ConfidenceTier` enum: GOLD (auto-captured), SILVER (manual), BRONZE (poor quality), ABANDONED
- `GHAPEntry` dataclass: Full entry with iteration history, outcome, surprise, root cause, lesson

**Collector** (`collector.py`): File-based state machine using `aiofiles`:
- `current_ghap.json`: Active entry (only one at a time)
- `session_entries.jsonl`: Completed entries for current session
- `.session_id`, `.tool_count`: Session state
- `archive/`: Archived sessions ({date}_{session_id}.jsonl)
- Supports orphan detection and adoption across sessions
- Atomic writes with fsync for crash safety
- JSONL corruption recovery (line-level)

**Persister** (`persister.py`): Embeds resolved entries into 2-4 vector collections:
- `ghap_full`: Complete experience (all fields)
- `ghap_strategy`: Strategy-focused (what approach was used)
- `ghap_surprise`: Unexpected outcomes (only for FALSIFIED entries)
- `ghap_root_cause`: Root cause analysis (only for FALSIFIED with surprise)
- Same entry.id across all axes for cross-referencing
- Template-based text rendering with required/optional sections

**End-to-End Flow**:
1. `create_ghap()` → generate ID, save to current_ghap.json
2. `update_ghap()` → push old H/A/P to history, increment iteration_count
3. `resolve_ghap()` → set outcome, compute confidence_tier, append to session_entries.jsonl
4. `ObservationPersister.persist()` → render axis templates, embed, upsert to Qdrant

### Git Integration (`calm/git/`)

**Reader** (`reader.py`): GitPython-based async wrapper:
- `get_commits(since, until, path, limit)`: Commit log with diff stats
- `get_blame(file_path)`: Line-by-line blame with author/timestamp
- `get_file_history(file_path, limit)`: Commit history for specific file
- Binary file detection, shallow clone detection, UTF-8 encoding validation

**Analyzer** (`analyzer.py`): High-level git analysis:
- `index_commits()`: Incremental commit indexing (batch=75, 5-year default window). Embeds "message + files + author" text. Tracks last_indexed_sha in metadata store.
- `search_commits()`: Semantic search with author/timestamp filters
- `get_churn_hotspots(days, limit)`: Files ranked by change frequency
- `get_file_authors(file_path)`: Per-author commit/line stats
- `blame_search(pattern)`: ripgrep pattern match + git blame lookup

### Code Indexing (`calm/indexers/`)

**Tree-Sitter Parser** (`tree_sitter.py`): Multi-language AST parser supporting 9 languages:
- **Python**: Functions, classes, methods, module docstring, UPPER_CASE constants
- **TypeScript/JavaScript**: Exports, classes, functions, interfaces (TS only)
- **Rust**: Functions, structs, enums, traits
- **Swift**: Classes, structs, enums, protocols
- **Java**: Classes, interfaces, enums with methods
- **C/C++**: Functions, classes/structs (C++ only)
- **SQL**: CREATE TABLE, VIEW, FUNCTION, PROCEDURE
- Extracts: qualified_name, signature, content, docstring, cyclomatic complexity
- All parsing via `run_in_executor()` (CPU-bound)

**Code Indexer** (`indexer.py`):
- Parses files → `SemanticUnit[]` → batch embed → upsert to `code_units` collection
- Incremental: tracks file hash + mtime in metadata store, skips unchanged files
- Unit ID: SHA-256 of "project:file_path:qualified_name" (32 chars)
- Excludes: .venv, node_modules, .git, __pycache__, build, dist, .worktrees, etc.
- Configurable batch_size with sequential fallback on batch failure

### Unified Search (`calm/search/`)

**Collections** (`collections.py`): 8 named collections:
- `memories`, `code_units`, `commits`
- `ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`
- `values`

**Searcher** (`searcher.py`): Implements abstract `SearcherABC` with 5 search methods:
- `search_memories(query, category, limit)`
- `search_code(query, project, language, unit_type, limit)`
- `search_experiences(query, axis, domain, strategy, outcome, limit)`
- `search_values(query, axis, limit)`
- `search_commits(query, author, since, limit)`
- All methods: embed query → vector search with filters → typed result objects
- Only "semantic" search mode supported

**Results** (`results.py`): Typed dataclasses for each search type (MemoryResult, CodeResult, ExperienceResult, ValueResult, CommitResult), each with `.from_search_result()` factory.

### Clustering (`calm/clustering/`)

**Clusterer** (`clusterer.py`): HDBSCAN density-based clustering:
- Normalizes cosine embeddings to unit vectors
- Parameters: min_cluster_size=5, min_samples=3, cluster_selection_method="eom"
- Returns cluster labels, probabilities, weighted centroids
- Confidence weights: gold=1.0, silver=0.8, bronze=0.5, abandoned=0.2

**Experience Clusterer** (`experience.py`): Multi-axis clustering of GHAP entries:
- `cluster_axis(axis)`: Fetches experiences from ghap_{axis} collection, runs HDBSCAN
- Computes weighted centroids (gold experiences dominate cluster centers)
- Minimum 20 experiences required for meaningful clustering
- Noise points (label=-1) excluded from centroids

### Context Assembly (`calm/context/`)

**Assembler** (`assembler.py`): Parallel context retrieval with dedup and token budgets:
1. **Parallel Query**: `asyncio.gather()` across up to 5 source types (memories, code, experiences, values, commits)
2. **Deduplication**: ID-based (ghap_id > file_path > sha > memory_id) + fuzzy text matching (SequenceMatcher >= 0.85)
3. **Token Budget**: Proportional allocation via `SOURCE_WEIGHTS` config. Per-item cap at 25% of source budget.
4. **Formatting**: Markdown output with source-specific templates

**Premortem Mode**: Specialized context for failure analysis — queries experiences with outcome="falsified", groups by axis (Common Failures, Strategy Performance, Unexpected Outcomes, Root Causes).

**Token Estimation**: Heuristic of ~4 characters per token.

### Value Store (`calm/values/`)

**ValueStore** (`store.py`): Validates and stores agent-generated principles against cluster centroids:
1. Fetch cluster members and centroid
2. Embed candidate text
3. Calculate cosine distance: candidate to centroid
4. Threshold = mean(member_distances) + 0.5 * std(member_distances)
5. Valid if candidate_distance <= threshold
6. Store with full validation metadata for transparency

Value ID format: `value_{axis}_{label}_{uuid8}`

---

## MCP Server & Tools

### Server Architecture (`calm/server/`)

**Protocol**: MCP (Model Context Protocol) over HTTP
**Framework**: Starlette ASGI + Uvicorn
**Session Management**: `StreamableHTTPSessionManager` with `Mcp-Session-Id` headers

**Routes**:
- `GET /health` — JSON health status
- `POST /mcp` — MCP protocol endpoint

**Daemon** (`daemon.py`): Background process management:
- `start_daemon()`: Spawns `python -m calm.server.main` with `start_new_session=True`
- `stop_server()`: SIGTERM → 5s wait → SIGKILL
- PID file at `~/.calm/pid`

**Factory** (`app.py`): `create_server(use_mock=False)`:
- Mock mode: MemoryStore + MockEmbeddingService (for tests)
- Real mode: Lazy-initializes Qdrant, EmbeddingRegistry, all analyzers/indexers
- Collects tool implementations from all `get_*_tools()` functions
- Returns `(Server, tool_registry)` tuple

### 42 MCP Tools

| Category | Count | Tool Names |
|----------|-------|------------|
| Memory | 4 | `store_memory`, `retrieve_memories`, `list_memories`, `delete_memory` |
| Code | 3 | `index_codebase`, `search_code`, `find_similar_code` |
| Git | 5 | `index_commits`, `search_commits`, `get_file_history`, `get_churn_hotspots`, `get_code_authors` |
| GHAP | 5 | `start_ghap`, `update_ghap`, `resolve_ghap`, `get_active_ghap`, `list_ghap_entries` |
| Learning | 6 | `search_experiences`, `get_clusters`, `get_cluster_members`, `validate_value`, `store_value`, `list_values` |
| Context | 1 | `assemble_context` |
| Session | 5 | `start_session`, `get_orphaned_ghap`, `should_check_in`, `increment_tool_count`, `reset_tool_count` |
| Journal | 4 | `store_journal_entry`, `list_journal_entries`, `get_journal_entry`, `mark_entries_reflected` |
| Health | 1 | `ping` |

**Tool Registration Pattern**: Each tool category has a `get_*_tools(services...) -> dict[str, Callable]` factory. The dispatcher looks up tools by name and calls them with unpacked arguments.

**Validation**: Comprehensive input validation in `tools/validation.py` and `tools/enums.py`:
- UUID format, query length (max 10000), importance range (0.0-1.0)
- Tag format (alphanumeric/hyphen/underscore/dot, max 20 tags, max 50 chars each)
- Domain, strategy, outcome status validation against enums
- Text length limits per field (1000 for GHAP fields, 2000 for notes/results)

**Error Handling**:
- Structured errors: `{"error": {"type": "...", "message": "..."}}` (GHAP, learning tools)
- Exception-based: `MCPError`, `ValidationError` caught by dispatcher (memory, code, git tools)
- Graceful degradation: Returns empty results or "not_available" when services missing

---

## CLI & Orchestration

### CLI (`calm/cli/`)

Built with Click. Entry point: `calm` command with subcommands:

| Command | File | Purpose |
|---------|------|---------|
| `calm task` | `task.py` | Create, list, show, update, delete, transition, next-id |
| `calm worker` | `worker.py` | Start, complete, fail, list workers |
| `calm worktree` | `worktree.py` | Create, list, path, merge, remove git worktrees |
| `calm gate` | `gate.py` | Check phase transition gates, list gate requirements |
| `calm review` | `review.py` | Record, list, check, clear reviews |
| `calm session` | `session.py` | List, show session handoffs |
| `calm counter` | `counter.py` | Get, set, increment, list counters |
| `calm backup` | `backup.py` | Create, list, restore database backups |
| `calm status` | `status.py` | System overview, health check, worktrees |
| `calm server` | `server.py` | Start, stop, status, restart, run (foreground) |
| `calm init` | `init_cmd.py` | Initialize CALM database and directories |
| `calm install` | `install_cmd.py` | Full installation with all steps |

### Orchestration Engine (`calm/orchestration/`)

**Tasks** (`tasks.py`): CRUD for tasks with phase tracking:
- `Task` dataclass: id, title, phase, task_type (feature/bug), spec_id, worktree_path, blocked_by, project_path, specialist, notes
- `create_task()`, `get_task()`, `update_task()`, `delete_task()`, `list_tasks()`, `transition_task()`
- `get_next_task_id(prefix)`: Auto-increment within prefix (e.g., BUG-080, SPEC-059)

**Phases** (`phases.py`): Two phase models:
- Feature: `SPEC → DESIGN → IMPLEMENT → CODE_REVIEW → TEST → INTEGRATE → VERIFY → DONE`
- Bug: `REPORTED → INVESTIGATED → FIXED → REVIEWED → TESTED → MERGED → DONE`
- Validates transitions are sequential (no skipping)

**Gates** (`gates.py`): Automated phase transition checks:
- `IMPLEMENT → CODE_REVIEW`: Tests pass, lint clean, mypy --strict, implementation code exists, no untracked TODOs
- `CODE_REVIEW → TEST`: 2 approved code reviews
- `TEST → INTEGRATE`: Full test suite passes
- `INTEGRATE → VERIFY`: Changelog entry exists
- Bug gates: Bug report complete, root cause documented, fix plan exists, regression test added
- Runs pytest with 300s timeout, captures results to `test_output.log` and database

**Reviews** (`reviews.py`): 2x review gate system:
- `record_review(task_id, review_type, result, worker_id, notes)`
- `check_reviews(task_id, review_type)`: Requires 2 "approved" reviews
- `clear_reviews(task_id, review_type)`: Restart review cycle on changes_requested
- Review types: spec, proposal, code, bugfix

**Workers** (`workers.py`): Worker lifecycle:
- `start_worker(task_id, role)` → generates W-{timestamp}-{random} ID
- `complete_worker()`, `fail_worker()`
- `cleanup_stale_workers(max_age_hours=2)`: Auto-marks old active workers as session_ended
- `get_role_prompt(role)`: Loads from `~/.calm/roles/{role}.md`
- `get_worker_context(task_id, role)`: Assembles role prompt + task info

**Worktrees** (`worktrees.py`): Git worktree management:
- `create_worktree(task_id)`: Creates `.worktrees/{task_id}/`, creates branch, scaffolds planning_docs or bug_reports
- `merge_worktree(task_id)`: Checkout main → pull → merge --no-ff → cleanup worktree → delete branch → increment merge counters → sync dependencies
- `check_merge_conflicts(task_id)`: Dry-run merge to detect conflicts
- Merge lock: `get_counter("merge_lock")` blocks merges when E2E tests fail

**Counters** (`counters.py`): Simple key-value counters for batch job triggers:
- `merges_since_e2e`, `merges_since_docs`, `merge_lock`
- `get_counter()`, `set_counter()`, `increment_counter()`, `list_counters()`

**Sessions** (`sessions.py`): Handoff tracking:
- `create_session(handoff_content, needs_continuation)`
- `get_latest_session()`, `mark_session_resumed()`
- Handoff includes summary, active tasks, blocked items, friction points, next steps

**Journal** (`journal.py`): Session journal entries:
- `store_journal_entry(summary, working_directory, friction_points, next_steps, session_log_content)`
- `list_journal_entries(unreflected_only, project_name, working_directory)`
- `mark_entries_reflected(entry_ids, memories_created, delete_logs)`

**Backups** (`backups.py`): Database backup management:
- `create_backup(name)`: Copies metadata.db → `~/.calm/backups/{name}_{timestamp}.db`
- `restore_backup(name)`: Replaces metadata.db from backup
- `list_backups()`: Returns available backups with size and timestamp

**Project** (`project.py`): Project detection utilities:
- `detect_main_repo()`: Finds git root
- `detect_project_path()`: Returns cwd for project scoping
- `get_current_commit(repo_path)`: Returns HEAD SHA

---

## Hooks & Integration

### Hook Lifecycle

```
Claude Code Session Start
│
├─ SessionStart Hook
│  ├─ Checks CALM server running (starts if needed)
│  ├─ Detects orphaned GHAP entries
│  ├─ Counts active tasks
│  └─ Outputs: "CALM is available. N active task(s)."
│
├─ User enters prompt
│  │
│  └─ UserPromptSubmit Hook
│     ├─ Queries memories (semantic search, top 5)
│     ├─ Queries experiences (recent GHAP, top 3)
│     └─ Injects context as system reminder
│
├─ Tool execution loop:
│  │
│  ├─ PreToolUse Hook (every ~10 calls)
│  │  ├─ Increments tool counter
│  │  ├─ Checks if GHAP reminder is due
│  │  └─ Reminds about active hypothesis if present
│  │
│  ├─ Tool executes
│  │
│  └─ PostToolUse Hook (after test commands only)
│     ├─ Parses test results (pytest/npm test/cargo test/go test)
│     ├─ Compares results to GHAP prediction
│     └─ Suggests resolve_ghap --status confirmed/falsified
│
└─ Session End (/wrapup skill)
```

### Hook Implementation Details

**Common** (`hooks/common.py`): Shared utilities:
- `read_stdin()`: Parses JSON from Claude Code hook input
- `write_output(text)`: Outputs to stdout for Claude Code injection
- `get_db_path()`: Returns `~/.calm/metadata.db`
- All hooks use 1.0s SQLite timeout and graceful error handling (empty output on any failure)

**Session Start** (`hooks/session_start.py`):
- Ensures MCP server running via PID file check + `signal(0)` + subprocess start
- Queries active GHAP entries from database
- Queries active tasks (phase != DONE) from database
- Outputs greeting with available skills and task counts

**User Prompt Submit** (`hooks/user_prompt_submit.py`):
- Embeds user prompt (uses MCP server's `/mcp` endpoint or falls back to database)
- Retrieves semantically relevant memories (top 5)
- Retrieves recent experiences (top 3)
- Injects as `<system-reminder>` block
- Max output: 2000 characters

**Pre Tool Use** (`hooks/pre_tool_use.py`):
- Maintains persistent tool count in `~/.calm/tool_count` JSON file
- Checks every 10 calls if active GHAP exists
- If active, reminds about current hypothesis and prediction
- Detects session changes (resets counter on new session)
- Max output: 800 characters

**Post Tool Use** (`hooks/post_tool_use.py`):
- Triggers only after test commands (pytest, npm test, cargo test, go test, jest, mocha, rspec, unittest)
- Multi-language test result parsing with regex
- Compares pass/fail counts against GHAP prediction text
- Suggests confirm/falsify based on prediction alignment
- Max output: 800 characters

**Skill Loader** (`hooks/skill_loader.py`):
- Loads skill templates from `~/.calm/skills/{name}.md`
- Special handling for `/orchestrate`: injects `{{WORKFLOW_CONTENT}}` and `{{TASK_LIST}}`
- Task list: queries non-DONE tasks, formats as markdown table (max 20 shown)

---

## Installation System

### 10-Step Installation (`calm/install/`)

| Step | Function | Description |
|------|----------|-------------|
| 1 | `step_check_dependencies` | Verify Python 3.12+, uv, Docker |
| 2 | `step_create_directories` | Create `~/.calm/{roles,workflows,skills,sessions,journal}` |
| 3 | `step_copy_templates` | Copy 28 template files (roles, workflows, skills, config) |
| 4 | `step_init_database` | Initialize SQLite schema |
| 5 | `step_start_qdrant` | Create/start Docker container `calm-qdrant` |
| 6 | `step_register_mcp` | Add MCP server to `~/.claude.json` |
| 7 | `step_register_hooks` | Add 4 hooks to `~/.claude/settings.json` |
| 8 | `step_register_skills` | Install orchestrate/wrapup/reflection skills |
| 9 | `step_start_server` | Start MCP server daemon |
| 10 | `step_verify` | Verify all directories, database, config exist |

**Idempotent**: All config merges use deep copy + filter old entries. Safe to run multiple times.
**Dry-run**: All steps support `--dry-run` mode.
**Atomic writes**: All config files written via temp + rename pattern.

**Docker** (`install/docker.py`):
- Container: `calm-qdrant` with volume `calm_qdrant_data`
- Health check: Polls `/readiness` with exponential backoff (0.5s → 2.0s)
- Production image: `qdrant/qdrant:v1.12.1`

**Dependencies** (`install/dependencies.py`):
- Python 3.12+ (required)
- Docker with running daemon (optional, skip with `--skip-qdrant`)
- uv package manager (required)

**Templates** (`install/templates.py`):
- 17 role files (architect, backend, frontend, qa, reviewer, bug-investigator, etc.)
- 1 workflow file (default.md)
- 3 skill files (orchestrate, wrapup, reflection)
- 3 Claude Code skill wrappers (SKILL.md files for discovery)
- 1 config template (config.yaml.default)

---

## Test Suite

**1852 tests** organized by package, mirroring source structure:

```
tests/
├── calm/                    # Core package tests
│   ├── hooks/               # Hook script tests (6 files)
│   ├── orchestration/       # Orchestration engine tests (11 files)
│   ├── test_cli_*.py        # CLI command tests (12 files)
│   ├── test_config.py       # Configuration tests
│   ├── test_db_schema.py    # Database schema tests
│   ├── test_ghap.py         # GHAP model/collector tests
│   ├── test_journal_tools.py
│   ├── test_storage.py
│   └── test_tools.py
├── clustering/              # Clustering algorithm tests (5 files)
├── context/                 # Context assembly tests (7 files)
├── embedding/               # Embedding model tests (5 files)
├── git/                     # Git integration tests (2 files)
├── indexers/                # Code indexer tests (4 files)
├── search/                  # Search interface tests (4 files)
├── server/                  # MCP server tests
│   ├── tools/               # Tool-level tests (20+ files)
│   └── test_*.py            # Server integration tests (8 files)
├── storage/                 # Storage backend tests (5 files)
├── values/                  # Value store tests (2 files)
├── test_install/            # Installation tests (6 files)
├── gates/                   # Gate check tests (3 files)
├── checks/                  # Hardcoded path checks
├── fixtures/                # Test data generators and code samples
└── test_bug_*_regression.py # Bug regression tests (4 files)
```

Notable test patterns:
- `conftest.py` fixtures for mock services, temporary databases, test servers
- Bug regression tests (BUG-003, BUG-005, BUG-012, BUG-014, BUG-017-031, BUG-034-043, BUG-052-079)
- Input validation test suite (`test_input_validation/`) covering all tool inputs
- Schema conformance tests verifying MCP tool definitions match Claude Code schemas
- Data contract tests for context assembly pipeline
- Hardcoded path checks to catch migration issues

---

## Data Flow

### Memory Storage & Retrieval

```
User calls store_memory(content, category, importance, tags)
    → validate inputs (category, importance range, tags format)
    → embed content via semantic embedder (Nomic)
    → upsert to "memories" collection in Qdrant
    → return {id, status}

User calls retrieve_memories(query, limit, category, min_importance)
    → embed query via semantic embedder
    → search "memories" collection with filters
    → return MemoryResult[] sorted by relevance
```

### Code Indexing & Search

```
User calls index_codebase(directory, project)
    → TreeSitterParser.parse_file() per file → SemanticUnit[]
    → Check metadata store for file hash changes (incremental)
    → Batch embed units via code embedder (MiniLM)
    → Upsert to "code_units" collection with metadata payload
    → Track file state in metadata store

User calls search_code(query, project, language)
    → Embed query via code embedder
    → Search "code_units" with project/language filters
    → Return CodeResult[] with file paths, signatures, code snippets
```

### GHAP → Experience → Value Pipeline

```
1. GHAP Lifecycle:
   create_ghap() → update_ghap() (iterate) → resolve_ghap()

2. Persistence:
   ObservationPersister.persist(entry) → embed 2-4 axis templates
   → upsert to ghap_full, ghap_strategy, [ghap_surprise], [ghap_root_cause]

3. Clustering (requires 20+ entries):
   ExperienceClusterer.cluster_axis(axis) → HDBSCAN → ClusterResult[]
   → weighted centroids (gold experiences dominate)

4. Value Formation:
   validate_value(text, cluster_id) → embed candidate
   → cosine distance to cluster centroid
   → threshold = mean(member_distances) + 0.5 * std
   → store_value() if within threshold
```

### Context Assembly

```
User calls assemble_context(query, context_types, max_tokens)
    → Parallel search across requested sources (asyncio.gather)
    → Convert results to ContextItem[] with formatted markdown
    → Deduplicate (ID-based + fuzzy text matching)
    → Distribute token budget by SOURCE_WEIGHTS
    → Select items by relevance within per-source budgets
    → Cap individual items at 25% of source budget
    → Assemble markdown with section headers and item counts
    → Return FormattedContext with token estimate
```

### Orchestration Workflow

```
Feature:  SPEC → DESIGN → IMPLEMENT → CODE_REVIEW → TEST → INTEGRATE → VERIFY → DONE
Bug:      REPORTED → INVESTIGATED → FIXED → REVIEWED → TESTED → MERGED → DONE

Each transition:
1. Worker completes work
2. Worker runs: calm gate check <task_id> <transition>
   → Automated checks (tests, lint, mypy, reviews, changelog)
   → Results logged to database
3. If gate passes: calm task transition <task_id> <phase>
4. For review gates: 2x sequential reviews required
   → If changes requested: fix → clear reviews → restart
5. For merge: calm worktree merge <task_id>
   → checkout main → pull → merge --no-ff → cleanup → increment counters
```

---

## Configuration & Settings

### File Locations

| Path | Purpose |
|------|---------|
| `~/.calm/` | CALM home directory |
| `~/.calm/metadata.db` | SQLite orchestration database |
| `~/.calm/config.yaml` | User configuration |
| `~/.calm/roles/*.md` | Specialist role prompts (17 files) |
| `~/.calm/workflows/default.md` | Orchestration workflow |
| `~/.calm/skills/*.md` | Skill templates |
| `~/.calm/journal/` | Session journal files |
| `~/.calm/sessions/` | Session state |
| `~/.calm/pid` | Server PID file |
| `~/.calm/server.log` | Server log |
| `~/.calm/backups/` | Database backups |
| `~/.claude.json` | MCP server registration |
| `~/.claude/settings.json` | Hook registration |
| `~/.claude/skills/*/SKILL.md` | Claude Code skill discovery |
| `.worktrees/` | Git worktrees (in project root) |

### Qdrant Collections

| Collection | Embedder | Dimension | Content |
|------------|----------|-----------|---------|
| `memories` | Nomic | 768 | Semantic memories with category/tags |
| `code_units` | MiniLM | 384 | Parsed code units with metadata |
| `commits` | Nomic | 768 | Git commit messages |
| `ghap_full` | Nomic | 768 | Complete GHAP entries |
| `ghap_strategy` | Nomic | 768 | Strategy-focused embeddings |
| `ghap_surprise` | Nomic | 768 | Unexpected outcomes (FALSIFIED only) |
| `ghap_root_cause` | Nomic | 768 | Root cause analysis (FALSIFIED only) |
| `values` | Nomic | 768 | Validated value/principle statements |

### System Health States

| State | Meaning | Merge Allowed |
|-------|---------|---------------|
| HEALTHY | Normal operations | Yes |
| ATTENTION | E2E tests due (12+ merges) | Yes |
| DEGRADED | E2E tests failed | No (merge_lock=1) |

### Batch Job Triggers

| Counter | Threshold | Action |
|---------|-----------|--------|
| `merges_since_e2e` | 12 | Run E2E test suite |
| `merges_since_docs` | 12 | Regenerate documentation |
| `merge_lock` | >0 | Block all merges |
