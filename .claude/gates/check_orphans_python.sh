#!/usr/bin/env bash
#
# check_orphans_python.sh: Detect orphaned Python code
#
# Usage: check_orphans_python.sh <worktree_path> [task_id]
#
# Checks for:
#   - Unused imports (F401)
#   - Unused variables (F841)
#   - Backup/orphan files
#   - Cleanup markers (TODO: remove, FIXME: cleanup)
#
# Exit codes:
#   0 - No orphans found
#   1 - Orphans detected
#   2 - Tool not available

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Checking for Orphaned Python Code ==="
echo "Directory: $WORKTREE"
echo ""

ISSUES=0

# Python - use ruff for unused imports/variables
echo "Checking for unused imports/variables..."
if command -v ruff &> /dev/null; then
    # F401 = unused import, F841 = unused variable
    unused=$(ruff check . --select=F401,F841 2>&1 || true)
    if [[ -n "$unused" ]]; then
        echo "$unused"
        ISSUES=$((ISSUES + $(echo "$unused" | wc -l)))
    fi
else
    echo "WARNING: ruff not found - skipping unused code check" >&2
fi

# Check for orphan patterns
echo ""
echo "Checking for orphan files..."
orphan_files=$(find . -type f \( -name "*.bak" -o -name "*.orig" -o -name "*~" -o -name "*.old" \) -not -path "./.git/*" -not -path "./.venv/*" 2>/dev/null || true)
if [[ -n "$orphan_files" ]]; then
    echo "Potential orphan files found:"
    echo "$orphan_files"
    ISSUES=$((ISSUES + $(echo "$orphan_files" | wc -l)))
fi

# Check for cleanup markers
echo ""
echo "Checking for incomplete cleanup markers..."
cleanup_markers=$(grep -rn "# TODO: remove\|# FIXME: cleanup\|# HACK" . --include="*.py" 2>/dev/null | grep -v ".git" | grep -v ".venv" || true)
if [[ -n "$cleanup_markers" ]]; then
    echo "Cleanup markers found:"
    echo "$cleanup_markers"
    ISSUES=$((ISSUES + $(echo "$cleanup_markers" | wc -l)))
fi

echo ""
if [[ $ISSUES -eq 0 ]]; then
    echo "PASS: No orphaned code detected"
    exit 0
else
    echo "FAIL: $ISSUES potential orphan issue(s) found"
    echo "Review the above and clean up or justify each item"
    exit 1
fi
