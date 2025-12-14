# Retrospective Tasks Execution Plan

## Dependency Analysis

### Logical Dependencies
- **BUG-062 → BUG-061**: BUG-062 (auto-detect project type) reads from `project.json` that BUG-061 creates

### File Conflict Groups (same files modified)
| Group | File | Tasks |
|-------|------|-------|
| A | `.claude/bin/claws-gate` | BUG-053, BUG-061, BUG-062 |
| B | `.claude/bin/claws-worktree` | BUG-058, BUG-059, BUG-060, BUG-063 |
| C | `.claude/bin/claws-session` | BUG-064, BUG-065 |
| D | `pyproject.toml` | BUG-052, BUG-055 |
| E | `tests/conftest.py` | BUG-052, BUG-054 |

### Independent Tasks
- BUG-056 (.pre-commit-config.yaml)
- BUG-057 (investigation only - no code changes)

## Execution Strategy

Since each task has its own worktree, we can **implement in parallel**.
File conflicts only matter at **merge time**.

### Implementation Waves (respects 6-worker limit)

**Wave 1** (6 tasks - all independent for implementation):
- BUG-052: Add global pytest timeout
- BUG-053: Gate script timeout with force-kill
- BUG-054: Test isolation fixture
- BUG-055: Mark slow tests
- BUG-056: Pre-commit hook
- BUG-057: Investigation (no code)

**Wave 2** (6 tasks):
- BUG-058: Auto-sync pip after merge
- BUG-059: Worktree health check
- BUG-060: File overlap detection
- BUG-061: Centralize impl directories
- BUG-063: Pre-merge conflict check
- BUG-064: Auto-commit on wrapup

**Wave 3** (2 tasks - BUG-062 depends on BUG-061 being merged):
- BUG-062: Auto-detect project type (BLOCKED BY BUG-061)
- BUG-065: Next-commands in handoff

### Merge Order (to minimize conflicts)

1. **Independent files first**:
   - BUG-056, BUG-057

2. **pyproject.toml group** (sequential):
   - BUG-052 → BUG-055

3. **conftest.py** (after BUG-052):
   - BUG-054

4. **claws-gate group** (sequential):
   - BUG-053 → BUG-061 → BUG-062

5. **claws-worktree group** (sequential):
   - BUG-058 → BUG-059 → BUG-060 → BUG-063

6. **claws-session group** (sequential):
   - BUG-064 → BUG-065

## Specs (Different Workflow)

SPEC-011 and SPEC-012 are in SPEC phase and need:
1. Spec Review #1
2. Spec Review #2
3. Human approval
4. Transition to DESIGN
5. Architect writes proposal
6. etc.

These follow the feature workflow, not bug workflow.
