#!/usr/bin/env bash
#
# check_platform.sh: Pre-flight platform capability check (SPEC-033)
#
# Runs before test suite to detect and report platform capabilities.
# This is informational - it does not fail the gate.
#
# Usage: check_platform.sh [worktree_path]

set -euo pipefail

WORKTREE="${1:-.}"
cd "$WORKTREE"

echo "=== Platform Pre-Flight Check ==="
echo ""

# Find the Python interpreter
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

# Set PYTHONPATH to include src directory
export PYTHONPATH="${WORKTREE}/src:${PYTHONPATH:-}"

$PYTHON -c "
from clams.utils.platform import get_platform_info, format_report

info = get_platform_info()
print(format_report(info))

# Platform-specific warnings
warnings = []

# MPS fork safety warning (BUG-042)
if info.is_macos and info.mps_available:
    warnings.append(
        'MPS is available. Daemon mode uses subprocess to avoid fork() issues. '
        'PyTorch imports must happen AFTER daemonization.'
    )

# Memory warning (BUG-014)
if info.mps_available:
    warnings.append(
        'MPS available but disabled for embeddings (memory leak workaround). '
        'Embedding operations will use CPU.'
    )

# Missing optional dependencies
if not info.has_ripgrep:
    warnings.append('ripgrep not installed - git blame analysis will be limited')

if not info.docker_running:
    warnings.append('Docker not running - integration tests will be skipped')

if not info.qdrant_available:
    warnings.append('Qdrant not available - vector storage tests will be skipped')

if warnings:
    print()
    print('=== Platform Warnings ===')
    for w in warnings:
        print(f'  - {w}')

print()
print('Platform check complete.')
"

exit 0
