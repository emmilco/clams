#!/bin/bash
set -euo pipefail

# CALM Installation Script
# Thin wrapper around the Python install command

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Color output
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

# Check prerequisites
if ! command -v python3 &> /dev/null; then
    error "Python 3 not found. Install from https://www.python.org/downloads/"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Build args to forward
ARGS=("--dev")  # Always dev mode when installing from repo
for arg in "$@"; do
    case $arg in
        --dry-run|--skip-qdrant|--skip-hooks|--skip-mcp|--skip-server|--force|-y|--yes|-v|--verbose)
            ARGS+=("$arg")
            ;;
        --help|-h)
            cat <<EOF
Usage: install.sh [OPTIONS]

Install CALM for Claude Code development.

This script runs 'uv run calm install --dev' with forwarded options.

OPTIONS:
    --dry-run        Show what would be done without making changes
    --skip-qdrant    Skip Qdrant Docker setup
    --skip-hooks     Skip hook registration
    --skip-mcp       Skip MCP server registration
    --skip-server    Skip starting the CALM server
    --force          Overwrite existing files
    -y, --yes        Skip confirmation prompts
    -v, --verbose    Verbose output
    --help           Show this help message

PREREQUISITES:
    - Python 3.12+
    - uv (https://astral.sh/uv/install.sh)
    - Docker (unless --skip-qdrant)

EXAMPLES:
    ./scripts/install.sh              # Development install
    ./scripts/install.sh --dry-run    # Preview changes
    ./scripts/install.sh -y           # Skip prompts

EOF
            exit 0
            ;;
        *)
            error "Unknown option: $arg"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Sync dependencies first
echo "Syncing Python dependencies..."
uv sync --quiet

# Run the Python install command
exec uv run calm install "${ARGS[@]}"
