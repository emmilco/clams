# SPEC-004: Technical Proposal

## Overview

Implement commit-anchored gate pass verification by:
1. Adding a `gate_passes` table to the database
2. Modifying `clams-gate` to record passes
3. Modifying `clams-task` to verify passes before transitions

## Implementation

### 1. Database Schema (clams-init)

Add to `.claude/bin/clams-init`:

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

### 2. Gate Check Changes (clams-gate)

Add a function to record gate passes. Place this function near the top of the file, after the `source` line:

```bash
# Record a successful gate pass in the database.
# The UNIQUE constraint on (task_id, transition, commit_sha) means:
# - Same commit can only have one record per gate (INSERT OR REPLACE updates timestamp)
# - Different commits create new records, preserving history
record_gate_pass() {
    local task_id="$1"
    local transition="$2"
    local worktree="$3"

    # Get current commit SHA
    local commit_sha
    commit_sha=$(cd "$worktree" && git rev-parse HEAD)

    if [[ -z "$commit_sha" ]]; then
        echo "Error: Could not determine commit SHA" >&2
        return 1
    fi

    # Record in database with proper SQL escaping
    # Task IDs and transitions are controlled strings (alphanumeric + hyphen)
    # Commit SHAs are hex strings from git - safe but we escape anyway
    sqlite3 "$DB_PATH" <<EOF
INSERT OR REPLACE INTO gate_passes (task_id, transition, commit_sha)
VALUES ('$(echo "$task_id" | sed "s/'/''/g")', '$(echo "$transition" | sed "s/'/''/g")', '$(echo "$commit_sha" | sed "s/'/''/g")');
EOF

    echo "Gate pass recorded for commit ${commit_sha:0:7}"
}
```

**Integration point**: Call `record_gate_pass` at the end of `cmd_check`, just before the final success output. Add this block inside the `if [[ $failed -eq 0 ]]` section:

```bash
    # Record gate pass for transitions that require verification
    case "$transition" in
        IMPLEMENT-CODE_REVIEW|TEST-INTEGRATE|INVESTIGATED-FIXED|REVIEWED-TESTED)
            record_gate_pass "$task_id" "$transition" "$worktree"
            ;;
    esac
```

Transitions that record gate passes:
- `IMPLEMENT-CODE_REVIEW`
- `TEST-INTEGRATE`
- `INVESTIGATED-FIXED`
- `REVIEWED-TESTED`

### 3. Transition Changes (clams-task)

Add verification before allowing transitions. Place this function near the top of the file, after the `source` line:

```bash
# Verify that a gate check passed for this task at the current commit.
# We query for the most recent gate pass and compare commit SHAs.
# This ensures code hasn't changed since the gate check passed.
verify_gate_pass() {
    local task_id="$1"
    local transition="$2"
    local worktree="$3"

    # Get current commit SHA
    local current_sha
    current_sha=$(cd "$worktree" && git rev-parse HEAD)

    if [[ -z "$current_sha" ]]; then
        echo "Error: Could not determine commit SHA" >&2
        return 1
    fi

    # Check for matching gate pass (with SQL escaping)
    # ORDER BY passed_at DESC LIMIT 1 gets the most recent pass for this gate
    local recorded_sha
    recorded_sha=$(sqlite3 "$DB_PATH" \
        "SELECT commit_sha FROM gate_passes
         WHERE task_id = '$(echo "$task_id" | sed "s/'/''/g")'
         AND transition = '$(echo "$transition" | sed "s/'/''/g")'
         ORDER BY passed_at DESC LIMIT 1;")

    if [[ -z "$recorded_sha" ]]; then
        echo "Error: No gate pass found for $transition transition" >&2
        echo "" >&2
        echo "Run the gate check first:" >&2
        echo "  .claude/bin/clams-gate check $task_id $transition" >&2
        return 1
    fi

    if [[ "$current_sha" != "$recorded_sha" ]]; then
        echo "Error: Code has changed since gate check passed" >&2
        echo "" >&2
        echo "Gate passed at commit: ${recorded_sha:0:7}" >&2
        echo "Current commit: ${current_sha:0:7}" >&2
        echo "" >&2
        echo "Re-run the gate check:" >&2
        echo "  .claude/bin/clams-gate check $task_id $transition" >&2
        return 1
    fi

    echo "✓ Gate verification passed (commit ${current_sha:0:7})"
    return 0
}
```

**Integration point**: In `cmd_transition`, add gate verification **after** validating the phase transition is valid and **before** enforcing review requirements. Insert this block around line 280 (after the `valid_transition` checks):

```bash
    # Verify gate pass for transitions that require it
    local gate_transition=""
    case "${from_phase}-${to_phase}" in
        IMPLEMENT-CODE_REVIEW)
            gate_transition="IMPLEMENT-CODE_REVIEW"
            ;;
        TEST-INTEGRATE)
            gate_transition="TEST-INTEGRATE"
            ;;
        INVESTIGATED-FIXED)
            gate_transition="INVESTIGATED-FIXED"
            ;;
        REVIEWED-TESTED)
            gate_transition="REVIEWED-TESTED"
            ;;
    esac

    if [[ -n "$gate_transition" ]]; then
        if [[ -z "$worktree_path" || ! -d "$worktree_path" ]]; then
            echo "Error: No worktree found for task $id" >&2
            exit 1
        fi
        if ! verify_gate_pass "$id" "$gate_transition" "$worktree_path"; then
            exit 1
        fi
    fi
```

### 4. Transition-to-Gate Mapping

The transition command needs to map the phase transition to the gate name:

| From Phase | To Phase | Gate to Verify |
|------------|----------|----------------|
| IMPLEMENT | CODE_REVIEW | IMPLEMENT-CODE_REVIEW |
| TEST | INTEGRATE | TEST-INTEGRATE |
| INVESTIGATED | FIXED | INVESTIGATED-FIXED |
| REVIEWED | TESTED | REVIEWED-TESTED |

## Files Modified

1. `.claude/bin/clams-init` - Add gate_passes table
2. `.claude/bin/clams-gate` - Add record_gate_pass function, call on success
3. `.claude/bin/clams-task` - Add verify_gate_pass function, call before transition

## Migration

Run the new `clams-init` to add the table. Existing databases will get the new table added (CREATE TABLE IF NOT EXISTS).

## Verification

Manual testing per the spec:
1. Run gate check → record should appear in database
2. Transition without gate check → should fail
3. Modify code after gate check → transition should fail
4. Re-run gate check → transition should succeed
