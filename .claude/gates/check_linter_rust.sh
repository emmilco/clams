#!/usr/bin/env bash
#
# check_linter_rust.sh: Run Rust linter (cargo clippy)
#
# Usage: check_linter_rust.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - Linter clean
#   1 - Linter errors found
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

echo "=== Running Rust Linter (cargo clippy) ==="
echo "Directory: $WORKTREE"
echo ""

# Verify this is a Rust project
if [[ ! -f "Cargo.toml" ]]; then
    echo "Error: Not a Rust project (no Cargo.toml)" >&2
    exit 2
fi

# Verify cargo is available
if ! command -v cargo &> /dev/null; then
    echo "Error: cargo not found" >&2
    exit 2
fi

PASS=true

echo "Running: cargo clippy -- -D warnings"
if ! cargo clippy -- -D warnings 2>&1; then
    PASS=false
fi

echo ""
if $PASS; then
    echo "PASS: Linter clean"
    exit 0
else
    echo "FAIL: Linter errors found"
    exit 1
fi
