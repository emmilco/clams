#!/usr/bin/env bash
#
# check_types_python.sh: Run Python type checker (mypy)
#
# Usage: check_types_python.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - Type check clean
#   1 - Type errors found
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

echo "=== Running Python Type Checker (mypy) ==="
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

# Check for mypy availability
if command -v mypy &> /dev/null || [[ -f ".venv/bin/mypy" ]]; then
    echo "Running: mypy --strict (via uv run)"
    # Use uv run to ensure we're in the right venv
    # Set TOKENIZERS_PARALLELISM=false to prevent hangs when type-checking sentence-transformers
    if ! TOKENIZERS_PARALLELISM=false uv run mypy --strict src/ 2>&1; then
        PASS=false
    fi
else
    echo "WARNING: mypy not found - skipping type check" >&2
    echo "Install with: uv add --dev mypy" >&2
    exit 2
fi

echo ""
if $PASS; then
    echo "PASS: Type check clean"
    exit 0
else
    echo "FAIL: Type errors found"
    exit 1
fi
