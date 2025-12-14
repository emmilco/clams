# CLAWS Worker Permission Model

This document defines the permission model for CLAWS worker agents. It establishes what operations each worker role can perform, how permissions are enforced, and how to handle permission limitations.

## Quick Reference

| Role | Access Level | Can Write Files | Can Run Tests | Can Commit | MCP Tools |
|------|--------------|-----------------|---------------|------------|-----------|
| Backend | WORKTREE_WRITE | Yes (worktree) | Yes | Yes | No |
| Frontend | WORKTREE_WRITE | Yes (worktree) | Yes | Yes | No |
| Infra | WORKTREE_WRITE | Yes (worktree) | Yes | Yes | No |
| AI/DL | WORKTREE_WRITE | Yes (worktree) | Yes | Yes | No |
| Bug Investigator | WORKTREE_WRITE | Limited (reports) | Yes | No | No |
| Architect | WORKTREE_WRITE | Limited (docs) | No | No | No |
| Reviewer | WORKTREE_READ | No | Yes (verify) | No | No |
| Spec Reviewer | WORKTREE_READ | No | No | No | No |
| Proposal Reviewer | WORKTREE_READ | No | No | No | No |
| QA | WORKTREE_READ | No | Yes | No | No |
| Orchestrator | FULL_ACCESS | Yes (anywhere) | Yes | Yes | Yes |

## Access Levels

### WORKTREE_WRITE

Workers with this access level can:
- Read any file in the repository
- Write files only within their assigned worktree
- Run commands that modify the worktree (git add, git commit)
- Execute tests and linters

Typical roles: Implementers (Backend, Frontend, Infra, AI/DL)

### WORKTREE_READ

Workers with this access level can:
- Read any file in the repository
- Read worktree state (git status, git diff)
- Run tests to verify behavior
- Cannot modify any files

Typical roles: Reviewers, QA

### FULL_ACCESS

Only the orchestrator has this access level:
- Read/write anywhere in the repository
- Execute any command
- Access MCP tools
- Merge worktrees to main
- Modify infrastructure (scripts, database, roles)

## Directory Constraints

### Allowed Write Directories by Role

| Directory | Implementers | Bug Investigator | Architect | Reviewers |
|-----------|--------------|------------------|-----------|-----------|
| `src/` | Yes | No | No | No |
| `tests/` | Yes | Diagnostic only | No | No |
| `clams/` | Yes | No | No | No |
| `clams-visualizer/` | Frontend only | No | No | No |
| `planning_docs/{TASK_ID}/` | Yes | Yes | Yes | No |
| `bug_reports/` | No | Yes | No | No |
| `changelog.d/` | Yes | No | No | No |
| `docs/` | No | No | Yes (design docs) | No |
| `.claude/bin/` | No | No | No | No |
| `.claude/roles/` | No | No | No | No |

### Prohibited for All Workers

These directories are **never** modifiable by workers:

- `.claude/bin/` - Infrastructure scripts
- `.claude/roles/` - Role definitions
- `.claude/*.db` - Database files
- Main repository files (when in a worktree)

## Command Allowlists

### Implementers

```bash
# Git operations (worktree only)
git status
git diff
git add
git commit
git log

# Testing
pytest
ruff check
mypy

# CLAWS commands (from main repo)
.claude/bin/claws-gate check {TASK_ID} {TRANSITION}
.claude/bin/claws-task transition {TASK_ID} {PHASE} --gate-result pass
```

### Reviewers

```bash
# Git operations (read only)
git status
git diff
git log

# Testing (verify only)
pytest

# CLAWS commands (from main repo)
.claude/bin/claws-review record {TASK_ID} {TYPE} {RESULT} --worker {WORKER_ID}
```

### Bug Investigators

```bash
# Git operations
git status
git diff
git log
git blame

# Testing (diagnostic)
pytest

# CLAWS commands (from main repo)
.claude/bin/claws-gate check {TASK_ID} REPORTED-INVESTIGATED
.claude/bin/claws-task transition {TASK_ID} INVESTIGATED --gate-result pass
```

### Prohibited Commands (All Workers)

```bash
# Repository operations
git push
git merge
git rebase
git reset --hard

# Destructive operations
rm -rf
find -delete

# System operations
curl (to external URLs)
wget
npm/pip install (without approval)
```

## MCP Tool Access

**Critical Limitation**: MCP tools (CLAMS memory tools) are NOT available to subagent workers.

This is an architectural constraint of Claude Code's Task tool:
- Parent agent (orchestrator) has MCP tool access
- Subagents (workers) do not have MCP tool access
- This cannot be changed without Claude Code architecture changes

### Workaround

If a task requires MCP tool operations:
1. Worker completes all other work
2. Worker documents the MCP operation needed
3. Orchestrator executes MCP operations on worker's behalf
4. Credit goes to worker's analysis

### MCP-Dependent Operations

| Operation | Who Can Execute |
|-----------|-----------------|
| Store memory | Orchestrator only |
| Retrieve memories | Orchestrator only |
| Index codebase | Orchestrator only |
| Search code | Orchestrator only |
| GHAP operations | Orchestrator only |

## Fallback Protocol

When a worker encounters a permission limitation:

### Step 1: Document the Blocker

```markdown
BLOCKER: Permission limitation

**What I tried**: [exact command or tool use]
**Error message**: [exact error]
**What I need orchestrator to do**: [specific action with full parameters]
```

### Step 2: Provide Context

Include everything the orchestrator needs to complete the operation:
- Exact file paths
- Complete code snippets
- Expected outcomes
- Any verification steps

### Step 3: Continue with Available Work

Don't stop at the blocker:
- Complete analysis
- Prepare other deliverables
- Document recommendations

### Step 4: Report to Orchestrator

Your completion report should include:
1. Work completed successfully
2. Work blocked by permissions (with full context)
3. Recommendations for next steps

## Enforcement Mechanisms

### Layer 1: Prompt-Based (Role Files)

Each role file in `.claude/roles/` includes a Permissions section that explicitly states:
- What the worker CAN do
- What the worker CANNOT do
- What to do if blocked

### Layer 2: Worker Context (claws-worker)

The `claws-worker context` command outputs permission constraints specific to the task:
- Worktree path
- Allowed directories
- Main repo location (for CLAWS commands)

### Layer 3: Self-Verification

Workers verify their own compliance before reporting completion:

```bash
# Check all changes are within worktree
git status --porcelain | grep -v "^??" | awk '{print $2}'
# All paths should be relative, not starting with ../
```

### Layer 4: Code Review

Reviewers verify during code review:
- Changes are within expected directories
- No files modified outside worktree scope
- No infrastructure files touched

## Role-Specific Permission Details

### Backend Developer

```yaml
access_level: WORKTREE_WRITE
can_write:
  - src/clams/**
  - tests/**
  - planning_docs/{TASK_ID}/**
  - changelog.d/{TASK_ID}.md
can_run:
  - pytest
  - ruff
  - mypy
  - git (add, commit, status, diff, log)
  - claws-gate check
  - claws-task transition
cannot:
  - Modify .claude/**
  - Access MCP tools
  - Push to remote
```

### Frontend Developer

```yaml
access_level: WORKTREE_WRITE
can_write:
  - clams-visualizer/**
  - planning_docs/{TASK_ID}/**
  - changelog.d/{TASK_ID}.md
can_run:
  - npm (in clams-visualizer/)
  - git (add, commit, status, diff, log)
  - claws-gate check
  - claws-task transition
cannot:
  - Modify backend code (src/clams/**)
  - Modify .claude/**
  - Access MCP tools
```

### Code Reviewer

```yaml
access_level: WORKTREE_READ
can_write: []
can_run:
  - pytest (verify tests pass)
  - git (status, diff, log)
  - claws-review record
cannot:
  - Modify any files
  - Run claws-gate check
  - Run claws-task transition
  - Access MCP tools
```

### Bug Investigator

```yaml
access_level: WORKTREE_WRITE
can_write:
  - bug_reports/{BUG_ID}.md
  - planning_docs/{TASK_ID}/**
  - tests/**  # Diagnostic scaffolding only
can_run:
  - pytest
  - git (status, diff, log, blame)
  - claws-gate check
  - claws-task transition
cannot:
  - Modify src/** (investigate, don't fix)
  - Access MCP tools
  - Commit changes (orchestrator commits investigation)
```

### Architect

```yaml
access_level: WORKTREE_WRITE
can_write:
  - planning_docs/{TASK_ID}/proposal.md
  - planning_docs/{TASK_ID}/decisions.md
  - planning_docs/{TASK_ID}/spec.md  # Update to match proposal
can_run:
  - git (status, log)
cannot:
  - Write production code (src/**)
  - Run tests
  - Access MCP tools
```

## Common Issues and Solutions

### Issue: Edit tool denied

**Symptom**: Worker attempts to edit a file but the Edit tool is blocked.

**Cause**: Claude Code sandbox restriction on subagent.

**Solution**:
```markdown
BLOCKER: Edit tool denied

I attempted to edit: /path/to/file.py
To make this change:

**Before** (line 42):
```python
old_code = "something"
```

**After**:
```python
new_code = "something_better"
```

Please make this edit on my behalf.
```

### Issue: Bash command blocked

**Symptom**: Worker tries to run a command but Bash tool returns permission error.

**Cause**: Command not in parent agent's allowlist, or model restriction.

**Solution**:
```markdown
BLOCKER: Bash command blocked

Command I need to run:
```bash
pytest tests/specific_test.py -v
```

Expected output: Test results showing whether my fix works.

Please run this command and share the output.
```

### Issue: MCP tool not found

**Symptom**: Worker tries to use CLAMS tools but they don't appear in available tools.

**Cause**: MCP tools only available to parent agent.

**Solution**:
```markdown
Note: I cannot access MCP tools. If this task requires storing memories
or GHAP entries, please handle that operation after my completion.

Recommended MCP operation:
Tool: mcp__clams__store_memory
Parameters:
  content: "..."
  category: "..."
```

### Issue: Wrote to wrong directory

**Symptom**: Git status shows changes outside worktree.

**Cause**: Worker used wrong file path (main repo instead of worktree).

**Solution**:
1. Worker identifies the error during self-check
2. Worker reports to orchestrator
3. Orchestrator reverts changes and provides correct path
4. Worker retries with correct path

## Implementation Checklist

For workers implementing code:

- [ ] Read the spec and proposal before writing code
- [ ] Verify all file writes are within worktree
- [ ] Run tests: `pytest -vvsx 2>&1 | tee test_output.log`
- [ ] Run linter: `ruff check src/ tests/`
- [ ] Run type check: `mypy --strict src/`
- [ ] Run gate check from main repo
- [ ] Commit all changes (code AND planning docs)
- [ ] Verify no files outside worktree modified

For reviewers:

- [ ] Verify implementation code exists (git diff --stat src/ tests/)
- [ ] Read the spec and proposal
- [ ] Review the diff for correctness
- [ ] Run tests to verify they pass
- [ ] Verify changes are within expected scope
- [ ] Record review result in database

## Version History

| Date | Change | Author |
|------|--------|--------|
| 2025-12-14 | Initial permission model design | BUG-057 |
