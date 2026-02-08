#!/usr/bin/env bash
#
# check_linter_python.sh: Run Python linter (ruff or flake8)
#
# Usage: check_linter_python.sh <worktree_path> [task_id]
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

echo "=== Running Python Linter ==="
echo "Directory: $WORKTREE"
echo ""

# Verify this looks like a Python project
if [[ ! -f "pyproject.toml" ]] && [[ ! -f "setup.py" ]]; then
    if [[ ! -d "src" ]] || [[ -z "$(find src -name '*.py' -print -quit 2>/dev/null)" ]]; then
        echo "Error: Not a Python project" >&2
        exit 2
    fi
fi

PASS=true

if command -v ruff &> /dev/null; then
    echo "Running: ruff check"
    if ! ruff check . 2>&1; then
        PASS=false
    fi
elif command -v flake8 &> /dev/null; then
    echo "Running: flake8"
    if ! flake8 . 2>&1; then
        PASS=false
    fi
else
    echo "WARNING: No Python linter found (ruff or flake8)" >&2
    echo "Install with: pip install ruff" >&2
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
