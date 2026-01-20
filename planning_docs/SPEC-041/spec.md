# SPEC-041: Shell/Hooks Gate Check Script Enhancements

## Problem Statement

The shell linter gate script (`.claude/gates/check_linter_shell.sh`) exists and is registered in `registry.json`, but has gaps that limit its effectiveness:

1. **No `bash -n` syntax checking** - Only runs shellcheck, missing basic syntax validation
2. **No severity filtering** - Uses `-x` flag (follow sources) but no severity threshold
3. **Doesn't check changed files** - Checks all files in configured directories rather than focusing on what changed
4. **Missing `clams/hooks/` coverage** - Default directories are `.claude/bin/` and `scripts/`, but hooks in `clams/hooks/` aren't checked by default

**Note**: Project type detection and gate routing are handled by SPEC-040's dispatcher system. This spec focuses only on enhancing the shell linter script itself.

**Reference**: R14-C from bug pattern analysis (Theme T12: Workflow/Gate Script Brittleness)

## Proposed Solution

Enhance the existing `check_linter_shell.sh` script to:
1. Add `bash -n` syntax checking before shellcheck
2. Add `-S warning` severity threshold to shellcheck
3. Support changed-only mode via environment variable
4. Add `clams/hooks/` to default directories

## Acceptance Criteria

### Script Enhancements

- [ ] Script runs `bash -n` syntax check on each shell file before shellcheck
- [ ] Script uses `shellcheck -x -S warning` (both follow sources AND warning severity)
- [ ] Script supports `CHECK_CHANGED_ONLY=1` environment variable to check only changed files
- [ ] When `CHECK_CHANGED_ONLY=1`, script uses `git diff main...HEAD --name-only` filtered to SCRIPT_DIRS
- [ ] Default directories include `clams/hooks/` in addition to `.claude/bin/` and `scripts/`
- [ ] Shebang detection (existing behavior) continues to work for all directories including `clams/hooks/`
- [ ] Usage: `check_linter_shell.sh <worktree_path> [task_id]` (unchanged positional args)

### Exit Codes

Exit codes must be deterministic based on actual checks run:

| Condition | Exit Code |
|-----------|-----------|
| All checks pass | 0 |
| Any `bash -n` or shellcheck failure | 1 |
| Shellcheck unavailable AND no shell files found | 2 (skip) |
| Shellcheck unavailable BUT shell files exist | Run `bash -n` only, exit 0 if all pass, 1 if any fail |
| `CHECK_CHANGED_ONLY=1` with no shell changes | 0 with "No shell changes to check" |

### Error Handling

- [ ] If `bash -n` fails on a file, report syntax error, set PASS=false, continue to next file
- [ ] If `CHECK_CHANGED_ONLY=1` and `git diff` fails (not a git repo, main doesn't exist, etc.), fall back to checking all files with a warning message
- [ ] If shellcheck unavailable, warn once and skip shellcheck (but still run `bash -n`)

## Implementation Notes

**File to modify**: `.claude/gates/check_linter_shell.sh`

**Key changes**:

1. Add environment variable for changed-only mode (avoids positional arg conflicts):
```bash
CHECK_CHANGED_ONLY="${CHECK_CHANGED_ONLY:-0}"
```

2. Add `bash -n` before shellcheck:
```bash
echo "Syntax check: $script"
if ! bash -n "$script" 2>&1; then
    echo "  SYNTAX ERROR"
    PASS=false
    continue  # Skip shellcheck if syntax is broken
fi
```

3. Add severity flag:
```bash
if ! shellcheck -x -S warning "$script" 2>&1; then
```

4. Changed-only logic with git error handling:
```bash
if [[ "$CHECK_CHANGED_ONLY" == "1" ]]; then
    # Build filter patterns from SCRIPT_DIRS
    FILTER_PATTERNS=""
    for dir in $SCRIPT_DIRS; do
        FILTER_PATTERNS="$FILTER_PATTERNS ${dir%/}/*"
    done

    # Try git diff, fall back to all files on failure
    if SHELL_FILES=$(git diff main...HEAD --name-only -- $FILTER_PATTERNS '*.sh' 2>/dev/null); then
        SHELL_FILES=$(echo "$SHELL_FILES" | grep -E '\.(sh|bash)$|^clams/hooks/' || true)
        if [[ -z "$SHELL_FILES" ]]; then
            echo "No shell changes to check"
            exit 0
        fi
    else
        echo "WARNING: git diff failed, falling back to checking all files"
        CHECK_CHANGED_ONLY=0
    fi
fi
```

5. Update default directories:
```bash
if [[ -z "$SCRIPT_DIRS" ]]; then
    SCRIPT_DIRS=".claude/bin/ scripts/ clams/hooks/"
fi
```

## Testing Requirements

All tests should be automated (pytest or shell-based):

- [ ] **Syntax check**: Create temp script with syntax error, verify `bash -n` catches it
- [ ] **Shellcheck warning**: Create script with shellcheck warning, verify `-S warning` detects it
- [ ] **Changed-only mode**: Set `CHECK_CHANGED_ONLY=1`, mock `git diff`, verify filtering
- [ ] **Git failure fallback**: Set `CHECK_CHANGED_ONLY=1` in non-git dir, verify fallback to all files
- [ ] **Exit code 0**: All files pass both checks
- [ ] **Exit code 1**: Any file fails `bash -n` or shellcheck
- [ ] **Exit code 2**: No shellcheck AND no shell files found
- [ ] **Shellcheck unavailable**: Mock unavailable, verify `bash -n` still runs and determines exit code
- [ ] **clams/hooks/ coverage**: Verify files in `clams/hooks/` are checked by default

## Out of Scope

- Project type detection (SPEC-040)
- Gate routing logic (SPEC-040)
- Frontend check script (SPEC-042)
- Changing the overall script architecture
- Adding new CLI positional arguments
