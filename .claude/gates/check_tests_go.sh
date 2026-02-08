#!/usr/bin/env bash
#
# check_tests_go.sh: Run Go test suite (go test)
#
# Usage: check_tests_go.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - All tests passed
#   1 - Tests failed
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

echo "=== Running Go Tests (go test) ==="
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

echo "Running: go test ./..."
if go test ./... 2>&1 | tee test_output.log; then
    echo ""
    echo "PASS: All tests passed"
    exit 0
else
    echo ""
    echo "FAIL: Tests failed"
    exit 1
fi
