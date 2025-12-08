#!/usr/bin/env bash
#
# claws-common.sh: Shared configuration for CLAWS scripts
#
# Source this at the start of any CLAWS script to get:
#   - MAIN_REPO: Path to the main (non-worktree) repository
#   - CLAUDE_DIR: Path to .claude in main repo
#   - DB_PATH: Path to the shared database
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/claws-common.sh"

# Find the script directory
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")" && pwd)"
_LOCAL_CLAUDE_DIR="$(dirname "$_SCRIPT_DIR")"
_LOCAL_REPO="$(dirname "$_LOCAL_CLAUDE_DIR")"

# Detect if we're in a worktree and find main repo
# git worktree list --porcelain shows all worktrees with their paths
# The first one listed is always the main worktree
if git rev-parse --is-inside-work-tree &>/dev/null; then
    # Get the main worktree path (first entry from worktree list)
    MAIN_REPO=$(cd "$_LOCAL_REPO" && git worktree list --porcelain 2>/dev/null | head -1 | sed 's/worktree //')

    if [[ -z "$MAIN_REPO" ]]; then
        # Fallback: use git rev-parse --git-common-dir
        _GIT_COMMON=$(cd "$_LOCAL_REPO" && git rev-parse --git-common-dir 2>/dev/null)
        if [[ -n "$_GIT_COMMON" && "$_GIT_COMMON" != ".git" ]]; then
            # Git common dir points to main repo's .git, get parent
            MAIN_REPO=$(dirname "$_GIT_COMMON")
        else
            MAIN_REPO="$_LOCAL_REPO"
        fi
    fi
else
    MAIN_REPO="$_LOCAL_REPO"
fi

# Set shared paths
CLAUDE_DIR="$MAIN_REPO/.claude"
DB_PATH="$CLAUDE_DIR/claws.db"
GATES_DIR="$CLAUDE_DIR/gates"
ROLES_DIR="$CLAUDE_DIR/roles"
WORKTREE_DIR="$MAIN_REPO/.worktrees"

# Prevent tokenizers library from hanging on fork (sentence-transformers, etc.)
# This must be set before importing any HuggingFace libraries
export TOKENIZERS_PARALLELISM=false

# Export for subprocesses
export MAIN_REPO CLAUDE_DIR DB_PATH GATES_DIR ROLES_DIR WORKTREE_DIR

# Debug: uncomment to verify paths
# echo "[clams-common] MAIN_REPO=$MAIN_REPO" >&2
# echo "[clams-common] DB_PATH=$DB_PATH" >&2
