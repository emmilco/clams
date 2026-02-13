# CALM: Getting Started

This guide covers day-to-day usage of CALM with Claude Code.

## How CALM Works

CALM runs as an MCP server that enhances Claude Code sessions with memory and orchestration capabilities. After installation, it works automatically - no manual activation required for basic features.

### Two Modes

1. **Memory Mode** (always active): Memories, GHAP tracking, session journaling, and context injection work in every session automatically.

2. **Orchestration Mode** (opt-in): Full task management, phase gates, worktrees, and worker dispatch. Activate per-session with `/orchestrate`.

## First Run After Installation

After running the installer (`./scripts/install.sh`), the very first Claude Code session will:

1. **SessionStart hook fires**: You will see a message like:
   ```
   CALM (Claude Agent Learning & Management) is available.

   Always active: /wrapup, /reflection, memory tools
   ```
   If the server is still starting, you may briefly see "CALM available (server starting...)" instead. This is normal.

2. **Embedding models download on first use**: CALM uses two local embedding models for semantic search. These are downloaded from HuggingFace Hub the first time an MCP tool needs them:
   - `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) -- for code search
   - `nomic-ai/nomic-embed-text-v1.5` (~275 MB) -- for memories and experiences

   The first tool call that requires embeddings (e.g., `store_memory`, `index_codebase`) will take longer than usual while the models download and load. Subsequent calls use the cached models and are fast.

   Download progress is logged to `~/.calm/server.log`. If you suspect a download is stalling, check that file for status.

3. **Verify everything works**: Ask Claude to run the `ping` tool (`mcp__calm__ping`). If it returns `{"status": "healthy"}`, CALM is fully operational.

### If Model Download Fails

If you have no network connection or the download is interrupted:
- The error message will indicate a download/network failure
- CALM tools that require embeddings will return errors, but the server itself stays running
- Non-embedding tools (like `ping`, `list_memories`, journal tools) continue to work
- Retry the operation once your network connection is restored; the download will resume

## Memory Mode: Daily Usage

### Automatic Context Injection

When you start a Claude Code session, CALM automatically:
- Announces its availability
- Shows any active tasks for the current project
- Injects relevant memories into your prompts

You don't need to do anything - context flows automatically.

### Session Wrapup

At the end of a coding session, use `/wrapup` to:
- Save a summary of what you accomplished
- Record friction points and blockers
- Document next steps for continuation

```
/wrapup              # Archive session (complete)
/wrapup continue     # Handoff for continuation (next session picks up)
```

The wrapup process:
1. Analyzes your conversation
2. Extracts summary, friction points, and next steps
3. Copies the session log for later reflection
4. Records everything in the database

### Reflection

Periodically run `/reflection` to extract durable learnings from past sessions:

```
/reflection
```

This launches analysis agents that:
1. Read your unreflected session logs
2. Extract debugging insights, codebase knowledge, workflow patterns
3. Propose memories for your approval
4. Store approved memories for future context injection

**Batch Approval UI**:
```
## Proposed Memories from 3 Sessions

### Debugging Insights (2)
[x] 1. [error] When async tests hang, check for missing `await` on database calls
    Source: Session 2026-02-01

[x] 2. [error] Import errors after refactoring often indicate circular dependencies
    Source: Session 2026-01-30

### Codebase Knowledge (1)
[x] 3. [fact] Configuration uses pydantic-settings; env vars override defaults
    Source: Session 2026-02-01

Enter numbers to toggle, 'a' to select all, 'n' to select none, or 'done':
```

### GHAP Tracking

GHAP (Goal-Hypothesis-Action-Prediction) helps structure debugging:

1. **Start tracking**: When investigating a problem, Claude may start a GHAP entry
2. **Check-in reminders**: CALM reminds you to verify your hypothesis periodically
3. **Resolution**: When the issue is resolved, record whether the hypothesis was confirmed or falsified
4. **Learning**: Resolved GHAPs become searchable experiences for similar future problems

You don't need to manage GHAP manually - Claude handles it, and CALM provides the infrastructure.

## Orchestration Mode: Project Management

For larger projects with multiple tasks, enable orchestration:

```
/orchestrate
```

This injects the full workflow system, including:
- Task creation and tracking
- Phase gates with automated checks
- Git worktrees for isolated development
- Worker dispatch for specialist agents
- Review requirements (2x before advancing)

### Task Lifecycle

**Feature tasks** follow this phase model:
```
SPEC → DESIGN → IMPLEMENT → CODE_REVIEW → TEST → INTEGRATE → VERIFY → DONE
```

**Bug tasks** follow:
```
REPORTED → INVESTIGATED → FIXED → REVIEWED → TESTED → MERGED → DONE
```

### Common Orchestration Commands

```bash
# Check system status
calm status

# Create a new task
calm task create SPEC-001 "Add user authentication"

# Create worktree for isolated development
calm worktree create SPEC-001

# Check gate requirements before transition
calm gate check SPEC-001 IMPLEMENT-CODE_REVIEW

# Transition task to next phase
calm task transition SPEC-001 CODE_REVIEW --gate-result pass

# Merge completed work to main
calm worktree merge SPEC-001
```

### Worktrees

Each task gets its own git worktree - an isolated copy of the repo where implementation happens:

```bash
# Create worktree
calm worktree create SPEC-001
# Creates .worktrees/SPEC-001/ with:
#   - planning_docs/SPEC-001/spec.md
#   - planning_docs/SPEC-001/proposal.md
#   - changelog.d/SPEC-001.md

# Get worktree path
calm worktree path SPEC-001
# Returns: /path/to/repo/.worktrees/SPEC-001

# List all worktrees
calm worktree list

# Merge to main when done
calm worktree merge SPEC-001
```

### Phase Gates

Before transitioning between phases, gate checks verify requirements:

```bash
calm gate check SPEC-001 IMPLEMENT-CODE_REVIEW
```

Example gate requirements for IMPLEMENT → CODE_REVIEW:
- Tests pass
- Linter clean
- Type check passes (mypy --strict)
- Implementation code exists in src/ or tests/
- No untracked TODOs

### Reviews

All artifacts require 2 approved reviews before advancing:

```bash
# Record a review
calm review record SPEC-001 code approved --worker W-123

# Check if reviews pass
calm review check SPEC-001 code

# List reviews for a task
calm review list SPEC-001
```

If a reviewer requests changes, the review cycle restarts from review #1.

## Configuration

CALM uses environment variables with the `CALM_` prefix. Set these in `~/.claude.json`:

```json
{
  "mcpServers": {
    "calm": {
      "type": "stdio",
      "command": "/path/to/calm/.venv/bin/calm",
      "args": ["server", "run"],
      "env": {
        "CALM_LOG_LEVEL": "INFO",
        "CALM_QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

### Available Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CALM_STORAGE_PATH` | `~/.calm` | Base storage directory |
| `CALM_SQLITE_PATH` | `~/.calm/metadata.db` | SQLite database path |
| `CALM_QDRANT_URL` | `http://localhost:6333` | Qdrant connection URL |
| `CALM_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `CALM_CODE_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Code embedding model |
| `CALM_SEMANTIC_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | Semantic embedding model |

## Key Concepts

### Memories

Memories are persistent knowledge stored with:
- **Content**: The actual insight or fact
- **Category**: preference, fact, event, workflow, context, error, decision
- **Importance**: 0.0-1.0 (higher = more likely to be retrieved)
- **Tags**: Optional categorization

Memories are retrieved semantically - ask about "database connection issues" and you'll get relevant memories even if they don't use those exact words.

### Experience Axes

GHAP experiences are embedded along multiple axes for richer retrieval:
- **full**: Complete narrative
- **strategy**: Problem-solving approach
- **surprise**: Unexpected outcomes
- **root_cause**: Why the hypothesis was wrong

### Specialist Roles

In orchestration mode, workers can be dispatched with specialist roles:

| Role | Purpose |
|------|---------|
| Architect | Design phase, technical proposals |
| Backend | Server-side implementation |
| Frontend | Client-side implementation |
| Reviewer | Code review |
| QA | Testing and verification |
| Bug Investigator | Root cause analysis |

Role definitions are stored in `~/.calm/roles/`.

## Best Practices

### End Sessions Cleanly

Always run `/wrapup` before ending a session. This:
- Preserves context for future sessions
- Enables the reflection → memory pipeline
- Documents what you accomplished

### Review Proposed Memories

When running `/reflection`, review each proposed memory:
- Skip memories that are too specific (line numbers, exact file paths)
- Approve memories that capture durable patterns
- The goal is insights that help in similar future situations

### Use Orchestration for Multi-Task Projects

If you're working on multiple features or bugs simultaneously:
1. Run `/orchestrate` to enable task tracking
2. Create tasks for each piece of work
3. Use worktrees to keep changes isolated
4. Follow the phase model for clean handoffs

### Let Gates Guide Quality

Don't skip gate checks. They catch:
- Missing tests
- Type errors
- Linting issues
- Incomplete implementations

Fix issues before transitioning rather than accumulating debt.

## Troubleshooting

### First Tool Call Is Slow or Times Out

On the very first use, embedding models (~365 MB total) must download from HuggingFace Hub. This can take a few minutes depending on your connection speed. Check `~/.calm/server.log` for download progress. If the download fails:
- Verify your network connection
- Retry the tool call -- downloads resume where they left off
- If behind a proxy, set `HTTPS_PROXY` in your MCP server environment

### Memories Not Being Retrieved

- Check that Qdrant is running: `docker ps | grep qdrant`
- Verify memories exist: Use the `mcp__calm__list_memories` tool
- Check importance scores - low importance memories may not surface

### GHAP Not Tracking

- GHAP is started by Claude during debugging, not manually
- Check for active GHAP: Use the `mcp__calm__get_active_ghap` tool
- Previous session's GHAP should be reported at session start

### Orchestration Commands Not Working

- Ensure you ran `/orchestrate` in the current session
- Check server status: `calm server status`
- Verify you're in a git repository with tasks

### Gate Check Failures

Read the failure output carefully:
- **Tests failed**: Fix failing tests before retrying
- **Type check failed**: Run `mypy --strict src/` to see errors
- **Linter failed**: Run `ruff check src/ tests/` to see issues
- **No implementation code**: Gate expects changes in src/ or tests/

## Next Steps

- Read the [README](README.md) for installation and architecture details
- Explore `~/.calm/roles/` to understand specialist behaviors
- Check `~/.calm/workflows/default.md` for full orchestration documentation
- Run `calm --help` for complete CLI reference
