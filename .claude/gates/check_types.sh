#!/usr/bin/env bash
#
# check_types.sh: Verify type checking passes
#
# Usage: check_types.sh [worktree_path]
#
# Runs the appropriate type checker (mypy for Python, tsc for TypeScript).
# Returns 0 if clean, 1 otherwise.

set -euo pipefail

# Source clams-common.sh for shared configuration (sets TOKENIZERS_PARALLELISM, etc.)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"
if [[ -f "$BIN_DIR/clams-common.sh" ]]; then
    source "$BIN_DIR/clams-common.sh"
fi

WORKTREE="${1:-.}"
cd "$WORKTREE"

echo "=== Running Type Checker ==="
echo "Directory: $WORKTREE"
echo ""

PASS=true

# Python - mypy
if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -d "src" && -f "$(find src -name '*.py' -print -quit 2>/dev/null)" ]]; then
    echo "Detected: Python"

    if command -v mypy &> /dev/null || [[ -f ".venv/bin/mypy" ]]; then
        echo "Running: mypy --strict (via uv run)"
        # Use uv run to ensure we're in the right venv
        # Set TOKENIZERS_PARALLELISM=false to prevent hangs when type-checking sentence-transformers
        if ! TOKENIZERS_PARALLELISM=false uv run mypy --strict src/ 2>&1; then
            PASS=false
        fi
    else
        echo "WARNING: mypy not found - skipping type check"
        echo "Install with: uv add --dev mypy"
    fi
fi

# TypeScript - tsc
if [[ -f "tsconfig.json" ]]; then
    echo "Detected: TypeScript"
    echo "Running: tsc --noEmit"
    if ! npx tsc --noEmit 2>&1; then
        PASS=false
    fi
fi

echo ""
if $PASS; then
    echo "PASS: Type check clean"
    exit 0
else
    echo "FAIL: Type errors found"
    exit 1
fi
