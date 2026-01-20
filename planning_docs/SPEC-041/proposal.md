# Proposal: SPEC-041 Shell/Hooks Gate Check Script Enhancements

## Problem Statement

The current shell linter gate script (`.claude/gates/check_linter_shell.sh`) has several gaps that limit its effectiveness for catching issues in shell scripts:

1. **No syntax validation**: The script runs `shellcheck` but not `bash -n` for basic syntax checking. Syntax errors can cause runtime failures that shellcheck may not catch.

2. **No severity filtering**: The script uses `shellcheck -x` (follow sources) but doesn't filter by severity. This means info-level suggestions are treated the same as warnings, potentially creating noise or missing important issues.

3. **Checks all files unconditionally**: The script always checks all shell files in configured directories, even when only a few files have changed. This is inefficient for large directories and doesn't focus attention on the actual changes.

4. **Missing `clams/hooks/` coverage**: The default directories are `.claude/bin/` and `scripts/`, but the project has shell hooks in `clams/hooks/` (e.g., `session_start.sh`, `user_prompt_submit.sh`, `outcome_capture.sh`) that are not checked by default.

5. **Inconsistent exit code semantics**: The current script exits with 0 if no scripts are found (even when directories exist but are empty), which could mask configuration issues.

## Proposed Solution

Enhance the existing `check_linter_shell.sh` script with the following changes:

### 1. Add `bash -n` Syntax Checking

Run `bash -n` on each script before shellcheck. This catches:
- Unmatched quotes
- Unterminated loops/conditionals
- Invalid syntax that shellcheck might not flag

If `bash -n` fails, skip shellcheck for that file (the output would be noise) and set `PASS=false`.

### 2. Add Shellcheck Severity Threshold

Change from `shellcheck -x` to `shellcheck -x -S warning`. This:
- Still follows sourced files (`-x`)
- Ignores style/info issues (`-S warning` = warning and above)
- Focuses on issues that could cause bugs or unexpected behavior

### 3. Support Changed-Only Mode

Add environment variable `CHECK_CHANGED_ONLY` to check only files changed since divergence from `main`:

```bash
CHECK_CHANGED_ONLY=1 check_linter_shell.sh /path/to/worktree TASK-001
```

When enabled:
- Use `git diff main...HEAD --name-only` to get changed files
- Filter to files in SCRIPT_DIRS with shell extensions or shebangs
- If git diff fails (not a repo, no main branch), fall back to checking all files with a warning

### 4. Add `clams/hooks/` to Default Directories

Update the fallback default from:
```bash
SCRIPT_DIRS=".claude/bin/ scripts/"
```

To:
```bash
SCRIPT_DIRS=".claude/bin/ scripts/ clams/hooks/"
```

This ensures hooks are checked when no explicit configuration exists.

### 5. Clarify Exit Code Semantics

| Condition | Exit Code | Meaning |
|-----------|-----------|---------|
| All checks pass | 0 | Success |
| Any `bash -n` or shellcheck failure | 1 | Failure |
| Shellcheck unavailable AND no shell files | 2 | Skip (nothing to check) |
| Shellcheck unavailable BUT shell files exist | 0 or 1 | Run `bash -n` only; exit based on results |
| `CHECK_CHANGED_ONLY=1` with no shell changes | 0 | Success (nothing to check) |

## Implementation Details

### File Changes

**File to modify**: `.claude/gates/check_linter_shell.sh`

### Script Structure (Annotated)

```bash
#!/usr/bin/env bash
#
# check_linter_shell.sh: Run shell script linter (shellcheck + bash -n)
#
# Usage: check_linter_shell.sh <worktree_path> [task_id]
#
# Environment variables:
#   CHECK_CHANGED_ONLY=1   Only check files changed since main
#   SCRIPT_DIRS            Space-separated directories to check
#
# Exit codes:
#   0 - All checks pass (or no shell changes when CHECK_CHANGED_ONLY=1)
#   1 - Linter or syntax errors found
#   2 - Tool not available and no shell files found (skipped)

set -euo pipefail

# ... (existing sourcing of claws-common.sh)

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"
CHECK_CHANGED_ONLY="${CHECK_CHANGED_ONLY:-0}"

cd "$WORKTREE"

echo "=== Running Shell Script Linter (shellcheck + bash -n) ==="
echo "Directory: $WORKTREE"
echo ""

# Check for shellcheck availability
SHELLCHECK_AVAILABLE=true
if ! command -v shellcheck &> /dev/null; then
    echo "WARNING: shellcheck not found" >&2
    echo "Install with: brew install shellcheck (macOS) or apt install shellcheck (Linux)" >&2
    SHELLCHECK_AVAILABLE=false
fi

# Get script directories from project.json or use defaults
PROJECT_CONFIG="$CLAUDE_DIR/project.json"
SCRIPT_DIRS=""

if [[ -f "$PROJECT_CONFIG" ]] && command -v jq &>/dev/null; then
    SCRIPT_DIRS=$(jq -r '.script_dirs[]? // empty' "$PROJECT_CONFIG" 2>/dev/null | tr '\n' ' ')
fi

# Fallback to defaults (now includes clams/hooks/)
if [[ -z "$SCRIPT_DIRS" ]]; then
    SCRIPT_DIRS=".claude/bin/ scripts/ clams/hooks/"
fi

echo "Checking directories: $SCRIPT_DIRS"

# Changed-only mode: get list of changed shell files
CHANGED_FILES=""
if [[ "$CHECK_CHANGED_ONLY" == "1" ]]; then
    echo "Mode: checking changed files only"

    # Build filter patterns for git diff
    FILTER_ARGS=()
    for dir in $SCRIPT_DIRS; do
        FILTER_ARGS+=("${dir%/}/*")
    done

    # Try git diff, fall back to all files on failure
    if CHANGED_FILES=$(git diff main...HEAD --name-only -- "${FILTER_ARGS[@]}" 2>/dev/null); then
        # Filter to shell files (by extension)
        CHANGED_FILES=$(echo "$CHANGED_FILES" | grep -E '\.(sh|bash)$' || true)

        if [[ -z "$CHANGED_FILES" ]]; then
            echo "No shell changes to check"
            exit 0
        fi
        echo "Changed shell files:"
        echo "$CHANGED_FILES" | sed 's/^/  /'
    else
        echo "WARNING: git diff failed, falling back to checking all files"
        CHECK_CHANGED_ONLY=0
        CHANGED_FILES=""
    fi
fi

echo ""

PASS=true
SCRIPTS_CHECKED=0

# Function to check a single script
check_script() {
    local script="$1"
    local relative_path="${script#$WORKTREE/}"

    # Skip non-shell files
    if [[ "$script" == *.md ]] || [[ "$script" == *.json ]] || [[ "$script" == *.py ]] || [[ "$script" == *.yaml ]]; then
        return 0
    fi

    # Check if it's a shell script (has bash/sh shebang or .sh extension)
    if [[ "$script" == *.sh ]] || [[ "$script" == *.bash ]] || head -1 "$script" 2>/dev/null | grep -qE "^#!.*(bash|sh)"; then
        SCRIPTS_CHECKED=$((SCRIPTS_CHECKED + 1))

        echo "Checking: $relative_path"

        # Step 1: bash -n syntax check
        echo "  Syntax check (bash -n)..."
        if ! bash -n "$script" 2>&1 | sed 's/^/    /'; then
            echo "    SYNTAX ERROR"
            PASS=false
            return 0  # Continue to next file, skip shellcheck
        fi

        # Step 2: shellcheck (if available)
        if [[ "$SHELLCHECK_AVAILABLE" == "true" ]]; then
            echo "  Linter check (shellcheck)..."
            if ! shellcheck -x -S warning "$script" 2>&1 | sed 's/^/    /'; then
                PASS=false
            fi
        fi
    fi
}

# Process files
if [[ "$CHECK_CHANGED_ONLY" == "1" ]] && [[ -n "$CHANGED_FILES" ]]; then
    # Check only changed files
    while IFS= read -r file; do
        if [[ -f "$WORKTREE/$file" ]]; then
            check_script "$WORKTREE/$file"
        fi
    done <<< "$CHANGED_FILES"
else
    # Check all files in directories
    for dir in $SCRIPT_DIRS; do
        dir_path="$WORKTREE/$dir"

        if [[ ! -d "$dir_path" ]]; then
            continue
        fi

        # Find shell scripts (by shebang or extension)
        while IFS= read -r -d '' script; do
            check_script "$script"
        done < <(find "$dir_path" -type f \( -name "*.sh" -o -name "*.bash" -o -executable \) -print0 2>/dev/null)
    done
fi

# Handle exit codes
echo ""
if [[ "$SCRIPTS_CHECKED" -eq 0 ]]; then
    if [[ "$SHELLCHECK_AVAILABLE" == "false" ]]; then
        echo "SKIP: No shell scripts found and shellcheck unavailable"
        exit 2
    else
        echo "No shell scripts found in: $SCRIPT_DIRS"
        echo "SKIP: No shell scripts to check"
        exit 0
    fi
fi

if $PASS; then
    echo "PASS: Shell linter clean ($SCRIPTS_CHECKED scripts checked)"
    exit 0
else
    echo "FAIL: Shell linter errors found"
    exit 1
fi
```

### Key Implementation Decisions

#### Why `bash -n` before shellcheck?

1. **Faster feedback**: Syntax errors are caught immediately without shellcheck's analysis time
2. **Cleaner output**: If syntax is broken, shellcheck output is noisy and unhelpful
3. **Comprehensive**: shellcheck focuses on style/best practices, while `bash -n` catches fundamental syntax errors

#### Why `-S warning` instead of `-S error`?

Warnings are important for shell scripts because they often indicate:
- Unquoted variables (SC2086) - major source of bugs
- Use of undefined variables (SC2154)
- Potentially incorrect comparisons (SC2015)

Info-level items are typically style preferences that don't affect correctness.

#### Why environment variable for changed-only mode?

Using an environment variable (`CHECK_CHANGED_ONLY`) instead of a positional argument:
1. Maintains backwards compatibility with existing `check_linter_shell.sh <worktree> [task_id]` interface
2. Allows easy integration with CI pipelines via env
3. Can be set once for multiple gate check invocations

#### Why fall back to checking all files when git diff fails?

The gate should still provide value even when:
- Running outside a git repository
- The `main` branch doesn't exist (new repos, renamed branches)
- Git is not installed

Falling back to checking all files ensures the gate never silently skips.

## Testing Strategy

Tests will be placed in `tests/infrastructure/test_shell_linter_gate.py` to match the existing infrastructure test pattern.

### Unit Tests (Python with subprocess)

```python
class TestShellLinterGate:
    """Tests for check_linter_shell.sh gate script."""

    def test_bash_syntax_error_detected(self, tmp_path):
        """Verify bash -n catches syntax errors."""
        # Create script with syntax error
        script = tmp_path / ".claude" / "bin" / "bad.sh"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\nif [ true; then\necho "broken"\nfi\n')
        script.chmod(0o755)

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 1
        assert "SYNTAX ERROR" in result.stdout

    def test_shellcheck_warning_detected(self, tmp_path):
        """Verify shellcheck -S warning catches warnings."""
        # Create script with unquoted variable (SC2086)
        script = tmp_path / ".claude" / "bin" / "unquoted.sh"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\nrm -rf $DIR\n')
        script.chmod(0o755)

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 1
        assert "SC2086" in result.stdout or "shellcheck" in result.stdout.lower()

    def test_changed_only_mode_with_no_changes(self, tmp_git_repo):
        """Verify CHECK_CHANGED_ONLY=1 exits 0 when no shell changes."""
        env = os.environ.copy()
        env["CHECK_CHANGED_ONLY"] = "1"

        result = subprocess.run(
            [gate_script, str(tmp_git_repo)],
            capture_output=True, text=True, env=env
        )

        assert result.returncode == 0
        assert "No shell changes to check" in result.stdout

    def test_git_diff_failure_fallback(self, tmp_path):
        """Verify fallback to all files when git diff fails."""
        # tmp_path is not a git repo
        script = tmp_path / ".claude" / "bin" / "test.sh"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\necho "hello"\n')
        script.chmod(0o755)

        env = os.environ.copy()
        env["CHECK_CHANGED_ONLY"] = "1"

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True, env=env
        )

        assert result.returncode == 0  # Script is valid
        assert "git diff failed" in result.stdout
        assert "fallback" in result.stdout.lower()

    def test_clams_hooks_checked_by_default(self, tmp_path):
        """Verify clams/hooks/ directory is checked by default."""
        # Create hook with syntax error
        hook = tmp_path / "clams" / "hooks" / "test.sh"
        hook.parent.mkdir(parents=True)
        hook.write_text('#!/bin/bash\necho "unclosed string\n')
        hook.chmod(0o755)

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 1
        assert "clams/hooks" in result.stdout

    def test_exit_code_0_all_pass(self, tmp_path):
        """Verify exit code 0 when all scripts pass."""
        script = tmp_path / ".claude" / "bin" / "good.sh"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\nset -euo pipefail\necho "hello"\n')
        script.chmod(0o755)

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_exit_code_2_no_shellcheck_no_scripts(self, tmp_path):
        """Verify exit code 2 when shellcheck unavailable and no scripts."""
        # This test needs to mock shellcheck unavailability
        # Could use a PATH override that excludes shellcheck
        pass  # Implementation depends on test infrastructure

    def test_shellcheck_unavailable_runs_bash_n_only(self, tmp_path):
        """Verify bash -n runs when shellcheck unavailable."""
        # Create valid script
        script = tmp_path / ".claude" / "bin" / "test.sh"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\necho "hello"\n')
        script.chmod(0o755)

        # Run with PATH that doesn't include shellcheck
        env = os.environ.copy()
        env["PATH"] = "/usr/bin"  # Minimal PATH without shellcheck

        result = subprocess.run(
            [gate_script, str(tmp_path)],
            capture_output=True, text=True, env=env
        )

        # Should still pass based on bash -n
        # May warn about shellcheck but continue
        assert "bash -n" in result.stdout.lower() or "syntax" in result.stdout.lower()
```

### Test Fixtures

```python
@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temporary git repo with main branch."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True)

    return tmp_path
```

## Backwards Compatibility

The changes maintain backwards compatibility:

1. **Same positional arguments**: `check_linter_shell.sh <worktree> [task_id]` unchanged
2. **Same default behavior**: Without `CHECK_CHANGED_ONLY`, checks all files as before
3. **Same exit codes**: 0=pass, 1=fail, 2=skip (semantics clarified but not changed)
4. **Same project.json support**: `script_dirs` from project.json still works

New features are opt-in via environment variables.

## Rollout Plan

1. Implement changes to `check_linter_shell.sh`
2. Add tests for new functionality
3. Run existing gate checks to verify no regressions
4. Document `CHECK_CHANGED_ONLY` in script header comments

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| `bash -n` false positives | None observed in testing; `bash -n` only catches actual syntax errors |
| `-S warning` too strict | Can be overridden via project.json `shellcheck_args` if needed (future enhancement) |
| `clams/hooks/` may not exist in all projects | Script already handles missing directories gracefully |
| `git diff` performance on large repos | Three-dot syntax (`main...HEAD`) limits comparison scope |

## Open Questions

None. The spec is clear and the implementation is straightforward.

## Appendix: Current Hook Coverage

The `clams/hooks/` directory contains these shell scripts that will now be checked by default:

- `session_start.sh` - Server lifecycle management
- `session_end.sh` - Server shutdown handling
- `user_prompt_submit.sh` - Context assembly
- `outcome_capture.sh` - GHAP outcome recording
- `ghap_checkin.sh` - GHAP reminder checks

All of these are critical hooks that interact with the CLAMS server and should be validated.
