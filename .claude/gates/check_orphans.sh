#!/usr/bin/env bash
#
# check_orphans.sh: Detect orphaned code
#
# Usage: check_orphans.sh [worktree_path]
#
# Looks for potentially orphaned code:
# - Unused imports
# - Unused variables (where detectable)
# - Dead code patterns
#
# Returns 0 if clean, 1 if orphans found.

set -euo pipefail

WORKTREE="${1:-.}"
cd "$WORKTREE"

echo "=== Checking for Orphaned Code ==="
echo "Directory: $WORKTREE"
echo ""

ISSUES=0

# Python - use ruff or pylint for unused imports/variables
if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -d "src" ]]; then
    echo "Checking Python for unused imports/variables..."

    if command -v ruff &> /dev/null; then
        # F401 = unused import, F841 = unused variable
        unused=$(ruff check . --select=F401,F841 2>&1 || true)
        if [[ -n "$unused" ]]; then
            echo "$unused"
            ISSUES=$((ISSUES + $(echo "$unused" | wc -l)))
        fi
    fi
fi

# Check for common orphan patterns in any language
echo ""
echo "Checking for orphan patterns..."

# Files that look like they might be orphaned (backup files, etc.)
orphan_files=$(find . -type f \( -name "*.bak" -o -name "*.orig" -o -name "*~" -o -name "*.old" \) -not -path "./.git/*" 2>/dev/null || true)
if [[ -n "$orphan_files" ]]; then
    echo "Potential orphan files found:"
    echo "$orphan_files"
    ISSUES=$((ISSUES + $(echo "$orphan_files" | wc -l)))
fi

# Check for TODO/FIXME/HACK comments that might indicate incomplete cleanup
echo ""
echo "Checking for incomplete cleanup markers..."
cleanup_markers=$(grep -rn "# TODO: remove\|// TODO: remove\|# FIXME: cleanup\|// FIXME: cleanup\|# HACK\|// HACK" . --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs" 2>/dev/null | grep -v ".git" || true)
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
