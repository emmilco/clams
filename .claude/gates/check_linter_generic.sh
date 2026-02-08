#!/usr/bin/env bash
#
# check_linter_generic.sh: Generic linter fallback
#
# Usage: check_linter_generic.sh <worktree_path> [task_id]
#
# For unknown project types, this script skips linting with a warning.
# Configure project type explicitly to enable proper linting.
#
# Exit codes:
#   0 - Skipped (no linter available for unknown type)
#   1 - (not used)
#   2 - (not used)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Generic Linter Check ==="
echo "Directory: $WORKTREE"
echo ""
echo "WARNING: Project type is 'unknown' - skipping linter check"
echo ""
echo "To enable linting, configure project type explicitly:"
echo "  Add to .claude/project.json: {\"project_type\": \"<python|javascript|rust|go|shell>\"}"
echo ""
echo "SKIP: No linter configured for unknown project type"
exit 0
