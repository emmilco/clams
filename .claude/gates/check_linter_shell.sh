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
# Checks shell scripts in configured script_dirs from project.json
# Falls back to .claude/bin/, scripts/, and clams/hooks/ if not configured.
#
# Exit codes:
#   0 - All checks pass (or no shell changes when CHECK_CHANGED_ONLY=1)
#   1 - Linter or syntax errors found
#   2 - Tool not available and no shell files found (skipped)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

# Save CLAUDE_DIR if set by caller (for testing)
_CALLER_CLAUDE_DIR="${CLAUDE_DIR:-}"

if [[ -f "$BIN_DIR/claws-common.sh" ]]; then
    source "$BIN_DIR/claws-common.sh"
fi

# Restore caller's CLAUDE_DIR if it was set (allows override for testing)
if [[ -n "$_CALLER_CLAUDE_DIR" ]]; then
    CLAUDE_DIR="$_CALLER_CLAUDE_DIR"
fi

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

    # Check if it's a shell script (has bash/sh shebang or .sh/.bash extension)
    if [[ "$script" == *.sh ]] || [[ "$script" == *.bash ]] || head -1 "$script" 2>/dev/null | grep -qE "^#!.*(bash|sh)"; then
        SCRIPTS_CHECKED=$((SCRIPTS_CHECKED + 1))

        echo "Checking: $relative_path"

        # Step 1: bash -n syntax check
        echo "  Syntax check (bash -n)..."
        local syntax_output
        if ! syntax_output=$(bash -n "$script" 2>&1); then
            echo "    SYNTAX ERROR"
            echo "$syntax_output" | sed 's/^/    /'
            PASS=false
            return 0  # Continue to next file, skip shellcheck
        fi

        # Step 2: shellcheck (if available)
        if [[ "$SHELLCHECK_AVAILABLE" == "true" ]]; then
            echo "  Linter check (shellcheck)..."
            local shellcheck_output
            if ! shellcheck_output=$(shellcheck -x -S warning "$script" 2>&1); then
                echo "$shellcheck_output" | sed 's/^/    /'
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

        # Find shell scripts (by extension or executable bit)
        # Note: -perm +111 is macOS compatible (not -executable which is GNU find only)
        while IFS= read -r -d '' script; do
            check_script "$script"
        done < <(find "$dir_path" -type f \( -name "*.sh" -o -name "*.bash" -o -perm +111 \) -print0 2>/dev/null)
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
