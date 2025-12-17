#!/usr/bin/env bash
#
# check_linter_shell.sh: Run shell script linter (shellcheck)
#
# Usage: check_linter_shell.sh <worktree_path> [task_id]
#
# Checks shell scripts in configured script_dirs from project.json
# Falls back to .claude/bin/ and scripts/ if not configured.
#
# Exit codes:
#   0 - Linter clean
#   1 - Linter errors found
#   2 - Tool not available (skipped)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/claws-common.sh" ]]; then
    source "$BIN_DIR/claws-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Running Shell Script Linter (shellcheck) ==="
echo "Directory: $WORKTREE"
echo ""

# Verify shellcheck is available
if ! command -v shellcheck &> /dev/null; then
    echo "WARNING: shellcheck not found" >&2
    echo "Install with: brew install shellcheck (macOS) or apt install shellcheck (Linux)" >&2
    exit 2
fi

# Get script directories from project.json or use defaults
PROJECT_CONFIG="$CLAUDE_DIR/project.json"
SCRIPT_DIRS=""

if [[ -f "$PROJECT_CONFIG" ]] && command -v jq &>/dev/null; then
    SCRIPT_DIRS=$(jq -r '.script_dirs[]? // empty' "$PROJECT_CONFIG" 2>/dev/null | tr '\n' ' ')
fi

# Fallback to defaults
if [[ -z "$SCRIPT_DIRS" ]]; then
    SCRIPT_DIRS=".claude/bin/ scripts/"
fi

echo "Checking directories: $SCRIPT_DIRS"
echo ""

PASS=true
SCRIPTS_FOUND=false

for dir in $SCRIPT_DIRS; do
    dir_path="$WORKTREE/$dir"

    if [[ ! -d "$dir_path" ]]; then
        continue
    fi

    # Find shell scripts (by shebang or extension)
    while IFS= read -r -d '' script; do
        SCRIPTS_FOUND=true

        # Skip non-executable files and known non-shell files
        if [[ "$script" == *.md ]] || [[ "$script" == *.json ]] || [[ "$script" == *.py ]]; then
            continue
        fi

        # Check if it's a shell script (has bash/sh shebang or .sh extension)
        if [[ "$script" == *.sh ]] || head -1 "$script" 2>/dev/null | grep -qE "^#!.*(bash|sh)"; then
            echo "Checking: $script"
            if ! shellcheck -x "$script" 2>&1; then
                PASS=false
            fi
        fi
    done < <(find "$dir_path" -type f \( -name "*.sh" -o -executable \) -print0 2>/dev/null)
done

if [[ "$SCRIPTS_FOUND" == "false" ]]; then
    echo "No shell scripts found in: $SCRIPT_DIRS"
    echo ""
    echo "SKIP: No shell scripts to check"
    exit 0
fi

echo ""
if $PASS; then
    echo "PASS: Shell linter clean"
    exit 0
else
    echo "FAIL: Shell linter errors found"
    exit 1
fi
