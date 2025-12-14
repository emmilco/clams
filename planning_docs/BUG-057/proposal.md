# BUG-057: Worker Agent Permission Model Design

## Overview

This document proposes a comprehensive permission model for CLAWS worker agents. The goal is to clearly define what operations each worker role can perform, establish enforcement mechanisms, and provide graceful fallback patterns when workers encounter permission limitations.

## Problem Statement

Worker agents in CLAWS currently operate without explicit permission boundaries:

1. **No explicit permission model**: Workers inherit full Claude Code permissions without worktree-specific constraints
2. **Frequent permission failures**: 27% of sessions documented permission-related worker failures
3. **Inconsistent enforcement**: Some workers can execute commands, others cannot, depending on Claude Code's sandbox and model-level restrictions
4. **MCP tool inaccessibility**: Subagent workers cannot access MCP tools (like CLAMS memory tools)
5. **Unclear boundaries**: Workers occasionally modify files outside their designated worktree

## Design Goals

1. **Clarity**: Every role should have explicitly documented permissions
2. **Defense in depth**: Multiple layers of enforcement (prompt-level, directory-level, command-level)
3. **Graceful degradation**: Clear fallback patterns when workers cannot execute required operations
4. **Minimal friction**: Don't block legitimate work with overly restrictive permissions

## Permission Categories

### Access Levels

| Level | Description | Typical Roles |
|-------|-------------|---------------|
| `WORKTREE_WRITE` | Read anywhere, write only in worktree | Implementers, Bug Investigators |
| `WORKTREE_READ` | Read-only access to worktree | Reviewers, Spec Reviewers |
| `MAIN_READ` | Can read main repo state (git log, etc.) | All workers |
| `FULL_ACCESS` | Read/write anywhere | Orchestrator only |

### Capability Categories

1. **File Operations**
   - Read files (within repo)
   - Write/Edit files (within worktree)
   - Create new files (within worktree)
   - Delete files (within worktree)

2. **Command Execution**
   - Git commands (status, diff, log, add, commit)
   - Test commands (pytest)
   - Lint commands (ruff, mypy)
   - CLAWS commands (gate check, review record)

3. **Tool Access**
   - Bash tool
   - Edit/Write tools
   - Read/Glob/Grep tools
   - MCP tools (NOT available to subagents)

## Role Permission Matrix

### Implementer Roles (Backend, Frontend, Infra, AI/DL)

```yaml
permissions:
  access_level: WORKTREE_WRITE

  file_operations:
    read: anywhere_in_repo
    write: worktree_only
    directories:
      allowed:
        - src/
        - tests/
        - planning_docs/{TASK_ID}/
        - changelog.d/
        - clams/  # For hook changes
        - clams-visualizer/  # For frontend changes
      prohibited:
        - .claude/bin/  # Infrastructure scripts
        - .claude/roles/  # Role definitions
        - main_repo/*  # Anything in main worktree

  commands:
    allowed:
      - git status
      - git diff
      - git add
      - git commit
      - git log
      - pytest
      - ruff check
      - mypy
      - .claude/bin/claws-gate check
      - .claude/bin/claws-task transition
    prohibited:
      - git push
      - git merge
      - rm -rf
      - Any command outside worktree

  tools:
    available:
      - Read
      - Edit
      - Write
      - Glob
      - Grep
      - Bash (restricted)
    unavailable:
      - MCP tools (subagent limitation)
```

### Reviewer Roles (Reviewer, Spec Reviewer, Proposal Reviewer)

```yaml
permissions:
  access_level: WORKTREE_READ

  file_operations:
    read: anywhere_in_repo
    write: none  # Reviewers should not modify code
    directories:
      read_only:
        - src/
        - tests/
        - planning_docs/

  commands:
    allowed:
      - git status
      - git diff
      - git log
      - pytest  # Can run tests to verify
      - .claude/bin/claws-review record  # MUST run from main repo
    prohibited:
      - git add
      - git commit
      - Any write operation

  tools:
    available:
      - Read
      - Glob
      - Grep
      - Bash (read-only commands)
    unavailable:
      - Edit
      - Write
      - MCP tools
```

### Bug Investigator

```yaml
permissions:
  access_level: WORKTREE_WRITE

  file_operations:
    read: anywhere_in_repo
    write:
      - bug_reports/{BUG_ID}.md
      - planning_docs/{TASK_ID}/
      - tests/  # For diagnostic scaffolding
    directories:
      allowed:
        - bug_reports/
        - planning_docs/{TASK_ID}/
        - tests/  # Temporary diagnostic tests
      prohibited:
        - src/  # Don't fix, just investigate

  commands:
    allowed:
      - git status
      - git diff
      - git log
      - git blame
      - pytest
      - .claude/bin/claws-gate check
      - .claude/bin/claws-task transition
    prohibited:
      - git commit  # Only orchestrator should commit investigation results

  tools:
    available:
      - Read
      - Edit (bug_reports only)
      - Glob
      - Grep
      - Bash (diagnostic commands)
    unavailable:
      - Write (new files)
      - MCP tools
```

### Architect

```yaml
permissions:
  access_level: WORKTREE_WRITE

  file_operations:
    read: anywhere_in_repo
    write:
      - planning_docs/{TASK_ID}/proposal.md
      - planning_docs/{TASK_ID}/decisions.md
      - planning_docs/{TASK_ID}/spec.md  # Can update spec to match proposal

  commands:
    allowed:
      - git status
      - git log
      - git diff
    prohibited:
      - pytest  # Not their job
      - git commit  # Orchestrator commits design docs

  tools:
    available:
      - Read
      - Edit
      - Write (planning_docs only)
      - Glob
      - Grep
      - Bash (read-only)
    unavailable:
      - MCP tools
```

### QA / E2E Runner

```yaml
permissions:
  access_level: WORKTREE_READ

  file_operations:
    read: anywhere_in_repo
    write: none

  commands:
    allowed:
      - pytest (full suite)
      - git status
      - git diff
      - .claude/bin/claws-gate check
      - .claude/bin/claws-task transition
    prohibited:
      - git add/commit
      - Any file modification

  tools:
    available:
      - Read
      - Glob
      - Grep
      - Bash (test execution)
    unavailable:
      - Edit
      - Write
      - MCP tools
```

## Enforcement Layers

### Layer 1: Prompt-Based (Soft Enforcement)

Add explicit permission sections to each role file in `.claude/roles/`:

```markdown
## Permissions

**Access Level**: WORKTREE_WRITE

**You CAN**:
- Read any file in the repository
- Write files in: src/, tests/, planning_docs/{TASK_ID}/
- Run: git status, git diff, git log, pytest, ruff, mypy
- Run gate checks from main repo

**You CANNOT**:
- Modify files in .claude/bin/ or .claude/roles/
- Edit files in the main repository (only your worktree)
- Run git push or git merge
- Access MCP tools (they are not available to worker agents)

**If you encounter a permission error**:
1. Document what you tried to do
2. Document the error
3. Report to orchestrator with your analysis
4. The orchestrator will complete the operation on your behalf
```

### Layer 2: Worker Context (Dynamic Enforcement)

Modify `claws-worker context` to include explicit permission constraints:

```bash
# In cmd_context() function of claws-worker:

echo "## Permission Constraints"
echo ""
echo "**HARD RULES - Violations will fail the task:**"
echo "1. ALL file writes MUST be within: \`$worktree_path\`"
echo "2. CLAWS commands MUST run from main repo: \`$main_repo\`"
echo "3. Do NOT modify: \`.claude/bin/\`, \`.claude/roles/\`, \`.claude/*.db\`"
echo ""
echo "**If you cannot execute a required operation:**"
echo "1. Document what you need to do"
echo "2. Document why you cannot (permission error, tool not available)"
echo "3. Report to orchestrator with your complete analysis"
echo ""
```

### Layer 3: Directory Guardrails (Automated Check)

Add to role files a verification step before completion:

```markdown
## Pre-Completion Checklist

Before reporting completion, verify:
```bash
# Check that all changes are within worktree
git -C {WORKTREE_PATH} status --porcelain | grep -v "^??" | awk '{print $2}' | while read file; do
  if [[ "$file" == ../* ]]; then
    echo "ERROR: Modified file outside worktree: $file"
    exit 1
  fi
done
```
```

### Layer 4: Fallback Pattern (When Permissions Fail)

When a worker cannot complete an operation due to permissions:

```markdown
## Fallback Protocol

If you encounter permission limitations (tool denied, command blocked, sandbox restriction):

1. **Complete what you can**: Provide full analysis, recommendations, and code snippets
2. **Document the blocker clearly**:
   ```
   BLOCKER: Permission limitation

   **What I tried**: [exact command or tool use]
   **Error**: [exact error message]
   **What I need orchestrator to do**: [specific action with parameters]
   ```
3. **Provide actionable context**: Include the exact code, file paths, and commands
4. **Report to orchestrator**: Your analysis is valuable even if you can't execute

The orchestrator will:
1. Execute the blocked operation on your behalf
2. Use your analysis to guide the action
3. Credit your work in the completion record
```

## Implementation Roadmap

### Phase 1: Documentation (This Bug)

1. Create `docs/worker-permission-model.md` with full permission matrix
2. Update each role file with permission section
3. Update `claws-worker context` to output permission constraints
4. Document fallback protocol in `_base.md`

### Phase 2: Soft Enforcement (Follow-up Task)

1. Add permission checklist to each role file
2. Add pre-completion verification steps
3. Create `claws-worker validate` command to check worktree boundaries

### Phase 3: Hard Enforcement (Future Consideration)

1. Investigate Claude Code sandbox configuration for subagents
2. Explore per-worktree `.claude/settings.json` for path restrictions
3. Consider git hooks to prevent commits with out-of-scope changes

## Known Limitations

### Claude Code Subagent Restrictions

The Task tool creates subagents that have additional restrictions beyond the parent agent:

1. **MCP tools unavailable**: Subagents cannot access MCP server tools
2. **Sandbox may be stricter**: Subagents may have reduced Bash/Edit permissions
3. **Model matters**: Haiku and Sonnet agents have more restrictions than Opus

**Mitigation**: Always use Opus for workers, design tasks within known constraints, and use the fallback protocol when workers hit limitations.

### No Technical Enforcement of Worktree Boundaries

Currently, there is no technical mechanism in Claude Code to restrict file operations to specific directories. All enforcement is:
- Prompt-based (soft)
- Self-reported (workers should verify their own compliance)
- Post-hoc (violations caught during review)

**Mitigation**: Clear documentation, explicit instructions in worker context, and code review to catch violations.

## Success Criteria

1. **All role files updated** with permission sections
2. **Worker context includes** explicit permission constraints
3. **Fallback protocol documented** in `_base.md`
4. **No more ambiguity** about what workers can/cannot do
5. **Graceful degradation** when workers hit permission limits

## Appendix: Common Permission Errors and Solutions

### Error: Edit tool denied

**Symptom**: Worker tries to edit a file but the Edit tool is blocked
**Root Cause**: Claude Code sandbox restricting subagent tool use
**Solution**: Worker documents the intended edit and reports to orchestrator

### Error: Bash command not permitted

**Symptom**: Worker tries to run a command but Bash tool is denied
**Root Cause**: Command not in parent agent's allow list, or model-level restriction
**Solution**: Worker provides command and expected output; orchestrator executes

### Error: MCP tool not available

**Symptom**: Worker tries to use CLAMS memory tools but they don't exist
**Root Cause**: MCP tools are only available to the parent agent, not subagents
**Solution**: Task should not require MCP tools; redesign or have orchestrator handle

### Error: File modified outside worktree

**Symptom**: git status shows changes to files outside the worktree
**Root Cause**: Worker edited the wrong file path
**Solution**: Reviewer catches during code review; worker provides correct path
