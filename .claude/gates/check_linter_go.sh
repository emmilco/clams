#!/usr/bin/env bash
#
# check_linter_go.sh: Run Go linter (go vet + staticcheck)
#
# Usage: check_linter_go.sh <worktree_path> [task_id]
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

echo "=== Running Go Linter ==="
echo "Directory: $WORKTREE"
echo ""

# Verify this is a Go project
if [[ ! -f "go.mod" ]]; then
    echo "Error: Not a Go project (no go.mod)" >&2
    exit 2
fi

# Verify go is available
if ! command -v go &> /dev/null; then
    echo "Error: go not found" >&2
    exit 2
fi

PASS=true

echo "Running: go vet ./..."
if ! go vet ./... 2>&1; then
    PASS=false
fi

# Run staticcheck if available
if command -v staticcheck &> /dev/null; then
    echo ""
    echo "Running: staticcheck ./..."
    if ! staticcheck ./... 2>&1; then
        PASS=false
    fi
else
    echo ""
    echo "Note: staticcheck not found (optional)"
fi

echo ""
if $PASS; then
    echo "PASS: Linter clean"
    exit 0
else
    echo "FAIL: Linter errors found"
    exit 1
fi
