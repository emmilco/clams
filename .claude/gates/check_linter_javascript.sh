#!/usr/bin/env bash
#
# check_linter_javascript.sh: Run JavaScript/TypeScript linter (eslint)
#
# Usage: check_linter_javascript.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - Linter clean
#   1 - Linter errors found
#   2 - Tool not available (skipped)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Running JavaScript/TypeScript Linter ==="
echo "Directory: $WORKTREE"
echo ""

# Verify this is a JavaScript/TypeScript project
if [[ ! -f "package.json" ]]; then
    echo "Error: Not a JavaScript project (no package.json)" >&2
    exit 2
fi

PASS=true

# Check for eslint
if [[ -f "node_modules/.bin/eslint" ]] || command -v eslint &> /dev/null; then
    echo "Running: eslint"
    if ! npx eslint . 2>&1; then
        PASS=false
    fi
elif grep -q '"eslint"' package.json 2>/dev/null; then
    # eslint is in dependencies but not installed
    echo "Installing dependencies..."
    npm install --quiet 2>/dev/null || npm install
    echo ""
    echo "Running: eslint"
    if ! npx eslint . 2>&1; then
        PASS=false
    fi
else
    echo "WARNING: eslint not found in project" >&2
    echo "Install with: npm install --save-dev eslint" >&2
    exit 2
fi

echo ""
if $PASS; then
    echo "PASS: Linter clean"
    exit 0
else
    echo "FAIL: Linter errors found"
    exit 1
fi
