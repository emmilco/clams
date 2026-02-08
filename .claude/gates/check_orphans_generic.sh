#!/usr/bin/env bash
#
# check_orphans_generic.sh: Generic orphan code detection
#
# Usage: check_orphans_generic.sh <worktree_path> [task_id]
#
# Performs basic orphan detection that works across languages:
#   - Backup/orphan files (*.bak, *.orig, *~, *.old)
#   - Cleanup markers (TODO: remove, FIXME: cleanup, HACK)
#
# Exit codes:
#   0 - No orphans found
#   1 - Potential orphans detected
#   2 - (not used)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Checking for Orphaned Code (Generic) ==="
echo "Directory: $WORKTREE"
echo ""

ISSUES=0

# Check for orphan files (backup files, etc.)
echo "Checking for orphan files..."
orphan_files=$(find . -type f \( -name "*.bak" -o -name "*.orig" -o -name "*~" -o -name "*.old" \) -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.venv/*" -not -path "./venv/*" -not -path "./target/*" 2>/dev/null || true)
if [[ -n "$orphan_files" ]]; then
    echo "Potential orphan files found:"
    echo "$orphan_files"
    ISSUES=$((ISSUES + $(echo "$orphan_files" | wc -l)))
fi

# Check for cleanup markers in source files
echo ""
echo "Checking for incomplete cleanup markers..."
cleanup_markers=$(grep -rn "TODO: remove\|FIXME: cleanup\|# HACK\|// HACK" . \
    --include="*.py" \
    --include="*.js" \
    --include="*.ts" \
    --include="*.tsx" \
    --include="*.jsx" \
    --include="*.go" \
    --include="*.rs" \
    --include="*.java" \
    --include="*.rb" \
    --include="*.sh" \
    2>/dev/null | grep -v ".git" | grep -v "node_modules" | grep -v ".venv" || true)

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
