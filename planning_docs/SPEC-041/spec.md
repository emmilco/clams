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
3. Support a `--changed-only` flag to focus on modified files
4. Add `clams/hooks/` to default directories

## Acceptance Criteria

### Script Enhancements

- [ ] Script runs `bash -n` syntax check on each shell file before shellcheck
- [ ] Script uses `shellcheck -x -S warning` (both follow sources AND warning severity)
- [ ] Script supports `--changed-only` flag that uses `git diff main...HEAD --name-only`
- [ ] When `--changed-only` is used, only changed files matching shell patterns are checked
- [ ] Default directories include `clams/hooks/` in addition to `.claude/bin/` and `scripts/`
- [ ] Script handles files in `clams/hooks/` even without `.sh` extension (check shebang)
- [ ] Exit codes unchanged: 0=clean, 1=errors, 2=skip (shellcheck unavailable)

### Error Handling

- [ ] If `bash -n` fails, report syntax error and continue to next file
- [ ] If `--changed-only` finds no shell changes, exit 0 with "No shell changes to check"
- [ ] If shellcheck unavailable, warn and skip shellcheck (but still run `bash -n`)

## Implementation Notes

**File to modify**: `.claude/gates/check_linter_shell.sh`

**Key changes**:

1. Add `bash -n` before shellcheck:
```bash
echo "Syntax check: $script"
if ! bash -n "$script" 2>&1; then
    echo "  SYNTAX ERROR"
    PASS=false
    continue  # Skip shellcheck if syntax is broken
fi
```

2. Add severity flag:
```bash
if ! shellcheck -x -S warning "$script" 2>&1; then
```

3. Add `--changed-only` support:
```bash
CHANGED_ONLY=false
if [[ "${1:-}" == "--changed-only" ]]; then
    CHANGED_ONLY=true
    shift
fi
# ... later ...
if $CHANGED_ONLY; then
    SHELL_FILES=$(git diff main...HEAD --name-only -- '*.sh' 'clams/hooks/*' '.claude/bin/*')
    # Filter to existing files and check those
fi
```

4. Update default directories:
```bash
SCRIPT_DIRS=".claude/bin/ scripts/ clams/hooks/"
```

## Testing Requirements

All tests should be automated (pytest or shell-based):

- [ ] **Unit test**: Create temp script with syntax error, verify `bash -n` catches it
- [ ] **Unit test**: Create temp script with shellcheck warning, verify detection with `-S warning`
- [ ] **Unit test**: Test `--changed-only` with mocked `git diff` output
- [ ] **Integration test**: In a worktree with hooks-only changes, verify script checks `clams/hooks/`
- [ ] **Graceful degradation**: Mock shellcheck unavailable, verify `bash -n` still runs

## Out of Scope

- Project type detection (SPEC-040)
- Gate routing logic (SPEC-040)
- Frontend check script (SPEC-042)
- Changing the overall script architecture
