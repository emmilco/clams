#!/bin/bash
set -euo pipefail

# Get repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Color output
info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $*"; }
warning() { echo -e "\033[1;33m[WARNING]\033[0m $*"; }

# Parse arguments
REMOVE_DATA=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-data)
            REMOVE_DATA=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            cat <<EOF
Usage: uninstall.sh [OPTIONS]

Uninstall CALM from Claude Code.

OPTIONS:
    --remove-data    Remove ~/.calm/ directory (requires confirmation)
    --force          Skip confirmation prompts
    --help           Show this help message

DEFAULT BEHAVIOR:
    - Remove CALM from ~/.claude.json
    - Remove CALM hooks from ~/.claude/settings.json
    - Stop and remove calm-qdrant Docker container
    - Keep ~/.calm/ data directory (use --remove-data to delete)

EXAMPLES:
    ./scripts/uninstall.sh                          # Safe uninstall, keep data
    ./scripts/uninstall.sh --remove-data            # Full removal with confirmation
    ./scripts/uninstall.sh --remove-data --force    # Full removal, no prompts

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

echo ""
echo "=========================================="
echo "  CALM Uninstallation"
echo "=========================================="
echo ""

# Confirmation prompt unless --force
if [ "$FORCE" = false ]; then
    echo "This will remove CALM from Claude Code configuration."
    if [ "$REMOVE_DATA" = true ]; then
        warning "This will also DELETE ~/.calm/ (all memories, GHAP data, etc.)"
    fi
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Uninstall cancelled"
        exit 0
    fi
fi

# 1. Stop CALM daemon
info "Stopping CALM daemon..."
calm_bin="$REPO_ROOT/.venv/bin/calm"
if [ -x "$calm_bin" ]; then
    if "$calm_bin" server stop 2>/dev/null; then
        success "CALM daemon stopped"
    else
        info "CALM daemon was not running"
    fi
else
    # Try stopping manually via PID file
    daemon_pid_file="$HOME/.calm/server.pid"
    if [ -f "$daemon_pid_file" ]; then
        daemon_pid=$(cat "$daemon_pid_file")
        if kill "$daemon_pid" 2>/dev/null; then
            success "CALM daemon stopped (PID: $daemon_pid)"
            rm -f "$daemon_pid_file"
        fi
    fi
fi

# 2. Remove MCP server from ~/.claude.json
info "Removing MCP server configuration..."
if [ -f "$HOME/.claude.json" ]; then
    server_data='{"name": "calm"}'
    if python3 "$REPO_ROOT/scripts/json_merge.py" \
        remove-server \
        --config-file "$HOME/.claude.json" \
        --data "$server_data"; then
        success "Removed from ~/.claude.json"
    else
        info "CALM was not in ~/.claude.json (already removed)"
    fi
else
    info "~/.claude.json not found (skipping)"
fi

# 2. Remove hooks from ~/.claude/settings.json
info "Removing hook registrations..."
if [ -f "$HOME/.claude/settings.json" ]; then
    hooks_data=$(jq -n \
        --arg session_start "python -m calm.hooks.session_start" \
        --arg user_prompt "python -m calm.hooks.user_prompt_submit" \
        --arg pre_tool "python -m calm.hooks.pre_tool_use" \
        --arg post_tool "python -m calm.hooks.post_tool_use" \
        '{
            commands: [$session_start, $user_prompt, $pre_tool, $post_tool]
        }') || {
        echo "Error: Failed to build hooks data JSON"
        exit 1
    }

    if python3 "$REPO_ROOT/scripts/json_merge.py" \
        remove-hooks \
        --config-file "$HOME/.claude/settings.json" \
        --data "$hooks_data"; then
        success "Removed from ~/.claude/settings.json"
    else
        info "CALM hooks were not in ~/.claude/settings.json (already removed)"
    fi
else
    info "~/.claude/settings.json not found (skipping)"
fi

# 3. Stop and remove Docker container
info "Stopping Qdrant container..."
if docker ps -a --format '{{.Names}}' | grep -q '^calm-qdrant$'; then
    docker stop calm-qdrant &> /dev/null || true
    docker rm calm-qdrant &> /dev/null || true
    success "Removed calm-qdrant container"
else
    info "calm-qdrant container not found (skipping)"
fi

# 4. Remove Docker volume (contains Qdrant data)
if docker volume ls --format '{{.Name}}' | grep -q '^calm_qdrant_storage$'; then
    if [ "$FORCE" = false ]; then
        echo ""
        read -p "Remove Qdrant data volume? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker volume rm calm_qdrant_storage &> /dev/null || true
            success "Removed Qdrant data volume"
        else
            info "Kept Qdrant data volume (can be removed manually with: docker volume rm calm_qdrant_storage)"
        fi
    else
        docker volume rm calm_qdrant_storage &> /dev/null || true
        success "Removed Qdrant data volume"
    fi
fi

# 5. Remove ~/.calm/ if requested
if [ "$REMOVE_DATA" = true ]; then
    if [ -d "$HOME/.calm" ]; then
        info "Removing ~/.calm/ data directory..."
        rm -rf "$HOME/.calm"
        success "Removed ~/.calm/"
    else
        info "~/.calm/ not found (skipping)"
    fi
else
    info "Kept ~/.calm/ data directory (use --remove-data to delete)"
fi

echo ""
echo "=========================================="
success "CALM uninstalled"
echo "=========================================="
echo ""
echo "What was removed:"
echo "  - CALM daemon process"
echo "  - MCP server from ~/.claude.json"
echo "  - Hooks from ~/.claude/settings.json"
echo "  - calm-qdrant Docker container"
if [ "$REMOVE_DATA" = true ]; then
    echo "  - ~/.calm/ data directory"
fi
echo ""
echo "What was NOT removed:"
echo "  - This repository ($REPO_ROOT)"
echo "  - Python virtual environment (.venv)"
if [ "$REMOVE_DATA" = false ]; then
    echo "  - ~/.calm/ data directory"
fi
echo ""
echo "To fully remove CALM:"
echo "  rm -rf $REPO_ROOT"
echo ""
