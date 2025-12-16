#!/usr/bin/env bash
#
# check_types_javascript.sh: Run TypeScript type checker (tsc)
#
# Usage: check_types_javascript.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - Type check clean (or not a TypeScript project)
#   1 - Type errors found
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

echo "=== Running TypeScript Type Checker ==="
echo "Directory: $WORKTREE"
echo ""

# Check if this is a TypeScript project
if [[ ! -f "tsconfig.json" ]]; then
    echo "Skip: Not a TypeScript project (no tsconfig.json)"
    exit 0
fi

PASS=true

echo "Running: tsc --noEmit"
if ! npx tsc --noEmit 2>&1; then
    PASS=false
fi

echo ""
if $PASS; then
    echo "PASS: Type check clean"
    exit 0
else
    echo "FAIL: Type errors found"
    exit 1
fi
