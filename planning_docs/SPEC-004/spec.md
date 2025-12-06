# SPEC-004: Gate Pass Verification for Phase Transitions

## Problem Statement

Currently, phase transitions that require test runs (e.g., `REVIEWED-TESTED`, `TEST-INTEGRATE`, `IMPLEMENT-CODE_REVIEW`) can be executed without proof that the gate check actually passed. The `clams-gate check` command runs tests and outputs PASS/FAIL, but the `clams-task transition` command doesn't verify that the gate was actually run and passed.

This allows transitions to be made without proper verification:
1. Gate check could be skipped entirely
2. Gate check could have failed but transition still executed
3. Code could be modified after gate passed, invalidating the test results

## Solution

Implement a **commit-anchored gate pass verification** system:

1. When `clams-gate check` passes, it records a `gate_pass` entry in the database containing:
   - Task ID
   - Transition name (e.g., `REVIEWED-TESTED`)
   - Commit SHA at time of pass
   - Timestamp

2. When `clams-task transition` is called for transitions that require gate verification, it:
   - Checks for a matching `gate_pass` record (task_id + transition)
   - Verifies the current HEAD commit matches the recorded commit SHA
   - Rejects transition if either check fails

This ensures:
- Gate checks cannot be skipped
- Code cannot be modified after gate passes without re-running the gate
- Clear audit trail of what code state was tested

## Scope

### In Scope

- New `gate_passes` database table
- Modification to `clams-gate check` to record passes
- Modification to `clams-task transition` to verify gate passes
- Transitions requiring gate verification:
  - **Feature**: `IMPLEMENT-CODE_REVIEW`, `TEST-INTEGRATE`
  - **Bug**: `INVESTIGATED-FIXED`, `REVIEWED-TESTED`

### Out of Scope

- **Review-only gates** (e.g., `SPEC-DESIGN`, `CODE_REVIEW-TEST`, `FIXED-REVIEWED`): Already enforced via the `reviews` table. The transition command checks for 2 approved reviews before allowing the transition.
- **Manual gates** (`VERIFY-DONE`, `MERGED-DONE`): These run on main after the worktree is deleted, so there's no commit SHA to verify against. Manual verification by the orchestrator is appropriate here.
- **File-existence gates** (e.g., `INTEGRATE-VERIFY`, `TESTED-MERGED`): These only check that a changelog file exists. No tests are run, so there's no test result to anchor to a commit.

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS gate_passes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, transition, commit_sha)
);
```

The unique constraint allows the same gate to pass multiple times (after code changes), but prevents duplicate entries for the same commit.

## Behavior Changes

### clams-gate check

When a gate check passes for a test-requiring transition:

1. Get current HEAD commit SHA from worktree
2. Insert/replace record in `gate_passes` table
3. Output includes: "Gate pass recorded for commit {sha}"

```bash
$ .claude/bin/clams-gate check BUG-003 REVIEWED-TESTED
=== Gate Check: REVIEWED-TESTED ===
...
✓ Full test suite passes (no skipped tests): PASS

==========================================
GATE RESULT: PASS
Gate pass recorded for commit abc1234

Proceed with transition:
  .claude/bin/clams-task transition BUG-003 TESTED --gate-result pass
```

### clams-task transition

For transitions requiring gate verification:

1. Get current HEAD commit SHA from worktree
2. Query `gate_passes` for matching task_id + transition + commit_sha
3. If no match found, reject with clear error message

```bash
# Success case
$ .claude/bin/clams-task transition BUG-003 TESTED --gate-result pass
✓ Gate verification passed (commit abc1234)
✓ Review gate passed: 2/2 bugfix reviews approved
Transitioned BUG-003: REVIEWED -> TESTED

# Failure case - no gate pass
$ .claude/bin/clams-task transition BUG-003 TESTED --gate-result pass
Error: No gate pass found for REVIEWED-TESTED transition

Run the gate check first:
  .claude/bin/clams-gate check BUG-003 REVIEWED-TESTED

# Failure case - code changed since gate pass
$ .claude/bin/clams-task transition BUG-003 TESTED --gate-result pass
Error: Code has changed since gate check passed

Gate passed at commit: abc1234
Current commit: def5678

Re-run the gate check:
  .claude/bin/clams-gate check BUG-003 REVIEWED-TESTED
```

## Error Handling

- **Git command failure**: If `git rev-parse HEAD` fails (e.g., corrupted repo, not a git directory), the gate check should fail with a clear error message. Do not record a gate pass without a valid commit SHA.
- **Detached HEAD**: Detached HEAD is valid - use the commit SHA as normal. This can occur during rebases or when checking out specific commits.
- **Database errors**: SQLite errors should propagate and fail the operation. No silent failures.

## Acceptance Criteria

1. **Database table created**: `gate_passes` table exists with correct schema
2. **Gate check records passes**: Running `clams-gate check` for test-requiring transitions records the commit SHA on success
3. **Transition verifies gate pass**: Running `clams-task transition` for test-requiring transitions verifies a matching gate pass exists
4. **Commit mismatch rejected**: If code changes after gate passes, transition is rejected until gate is re-run
5. **Clear error messages**: Failure cases provide actionable error messages
6. **Existing transitions unaffected**: Review-only and manual gates continue to work as before

## Test Plan

**Manual verification only** - no automated tests for this feature.

**Rationale**: This is infrastructure code that modifies the core CLAMS workflow commands. The best way to validate it is through real usage of the system. Automated tests for bash scripts that interact with git worktrees, databases, and other CLAMS commands would be complex and fragile. The human will monitor behavior and adjust as needed.

**Verification scenarios**:
1. Gate check records pass → transition succeeds
2. No gate pass → transition fails with clear error
3. Code change after gate pass → transition fails until gate re-run
4. Re-run gate after code change → transition succeeds

## Migration

Run schema migration to add `gate_passes` table. No data migration needed - existing tasks can simply run gate checks before their next transition.
