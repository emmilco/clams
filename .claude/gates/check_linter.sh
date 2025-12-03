#!/usr/bin/env bash
#
# check_linter.sh: Verify linter passes
#
# Usage: check_linter.sh [worktree_path]
#
# Runs the appropriate linter and verifies no errors.
# Returns 0 if clean, 1 otherwise.

set -euo pipefail

WORKTREE="${1:-.}"
cd "$WORKTREE"

echo "=== Running Linter ==="
echo "Directory: $WORKTREE"
echo ""

PASS=true

# Python - ruff or flake8
if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -d "src" && -f "$(find src -name '*.py' -print -quit 2>/dev/null)" ]]; then
    echo "Detected: Python"

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
        echo "WARNING: No Python linter found (ruff or flake8)"
    fi
fi

# JavaScript/TypeScript - eslint
if [[ -f "package.json" ]]; then
    echo "Detected: Node.js"

    if [[ -f "node_modules/.bin/eslint" ]] || command -v eslint &> /dev/null; then
        echo "Running: eslint"
        if ! npx eslint . 2>&1; then
            PASS=false
        fi
    else
        echo "WARNING: eslint not found"
    fi
fi

# Rust - clippy
if [[ -f "Cargo.toml" ]]; then
    echo "Detected: Rust"
    echo "Running: cargo clippy"
    if ! cargo clippy -- -D warnings 2>&1; then
        PASS=false
    fi
fi

# Go - go vet and staticcheck
if [[ -f "go.mod" ]]; then
    echo "Detected: Go"
    echo "Running: go vet"
    if ! go vet ./... 2>&1; then
        PASS=false
    fi

    if command -v staticcheck &> /dev/null; then
        echo "Running: staticcheck"
        if ! staticcheck ./... 2>&1; then
            PASS=false
        fi
    fi
fi

echo ""
if $PASS; then
    echo "PASS: Linter clean"
    exit 0
else
    echo "FAIL: Linter errors found"
    exit 1
fi
