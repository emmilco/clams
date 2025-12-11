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

Uninstall CLAMS from Claude Code.

OPTIONS:
    --remove-data    Remove ~/.clams/ directory (requires confirmation)
    --force          Skip confirmation prompts
    --help           Show this help message

DEFAULT BEHAVIOR:
    - Remove CLAMS from ~/.claude.json
    - Remove CLAMS hooks from ~/.claude/settings.json
    - Stop and remove clams-qdrant Docker container
    - Keep ~/.clams/ data directory (use --remove-data to delete)

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
echo "  CLAMS Uninstallation"
echo "=========================================="
echo ""

# Confirmation prompt unless --force
if [ "$FORCE" = false ]; then
    echo "This will remove CLAMS from Claude Code configuration."
    if [ "$REMOVE_DATA" = true ]; then
        warning "This will also DELETE ~/.clams/ (all memories, GHAP data, etc.)"
    fi
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Uninstall cancelled"
        exit 0
    fi
fi

# 1. Remove MCP server from ~/.claude.json
info "Removing MCP server configuration..."
if [ -f "$HOME/.claude.json" ]; then
    server_data='{"name": "clams"}'
    if python3 "$REPO_ROOT/scripts/json_merge.py" \
        remove-server \
        --config-file "$HOME/.claude.json" \
        --data "$server_data"; then
        success "Removed from ~/.claude.json"
    else
        info "CLAMS was not in ~/.claude.json (already removed)"
    fi
else
    info "~/.claude.json not found (skipping)"
fi

# 2. Remove hooks from ~/.claude/settings.json
info "Removing hook registrations..."
if [ -f "$HOME/.claude/settings.json" ]; then
    hooks_data=$(jq -n \
        --arg session_start "$REPO_ROOT/.claude/hooks/session_start.sh" \
        --arg user_prompt "$REPO_ROOT/.claude/hooks/user_prompt_submit.sh" \
        --arg ghap_checkin "$REPO_ROOT/.claude/hooks/ghap_checkin.sh" \
        --arg outcome "$REPO_ROOT/.claude/hooks/outcome_capture.sh" \
        '{
            commands: [$session_start, $user_prompt, $ghap_checkin, $outcome]
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
        info "CLAMS hooks were not in ~/.claude/settings.json (already removed)"
    fi
else
    info "~/.claude/settings.json not found (skipping)"
fi

# 3. Stop and remove Docker container
info "Stopping Qdrant container..."
if docker ps -a --format '{{.Names}}' | grep -q '^clams-qdrant$'; then
    docker stop clams-qdrant &> /dev/null || true
    docker rm clams-qdrant &> /dev/null || true
    success "Removed clams-qdrant container"
else
    info "clams-qdrant container not found (skipping)"
fi

# 4. Remove Docker volume (contains Qdrant data)
if docker volume ls --format '{{.Name}}' | grep -q '^clams_qdrant_storage$'; then
    if [ "$FORCE" = false ]; then
        echo ""
        read -p "Remove Qdrant data volume? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker volume rm clams_qdrant_storage &> /dev/null || true
            success "Removed Qdrant data volume"
        else
            info "Kept Qdrant data volume (can be removed manually with: docker volume rm clams_qdrant_storage)"
        fi
    else
        docker volume rm clams_qdrant_storage &> /dev/null || true
        success "Removed Qdrant data volume"
    fi
fi

# 5. Remove ~/.clams/ if requested
if [ "$REMOVE_DATA" = true ]; then
    if [ -d "$HOME/.clams" ]; then
        info "Removing ~/.clams/ data directory..."
        rm -rf "$HOME/.clams"
        success "Removed ~/.clams/"
    else
        info "~/.clams/ not found (skipping)"
    fi
else
    info "Kept ~/.clams/ data directory (use --remove-data to delete)"
fi

echo ""
echo "=========================================="
success "CLAMS uninstalled"
echo "=========================================="
echo ""
echo "What was removed:"
echo "  - MCP server from ~/.claude.json"
echo "  - Hooks from ~/.claude/settings.json"
echo "  - clams-qdrant Docker container"
if [ "$REMOVE_DATA" = true ]; then
    echo "  - ~/.clams/ data directory"
fi
echo ""
echo "What was NOT removed:"
echo "  - This repository ($REPO_ROOT)"
echo "  - Python virtual environment (.venv)"
if [ "$REMOVE_DATA" = false ]; then
    echo "  - ~/.clams/ data directory"
fi
echo ""
echo "To fully remove CLAMS:"
echo "  rm -rf $REPO_ROOT"
echo ""
