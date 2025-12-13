#!/bin/bash
set -euo pipefail

# Get repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Color output
info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }
warning() { echo -e "\033[1;33m[WARNING]\033[0m $*"; }

# Progress tracking
step_counter=0
total_steps=8

step() {
    step_counter=$((step_counter + 1))
    info "Step $step_counter/$total_steps: $*"
}

# Parse arguments
DRY_RUN=false
SKIP_QDRANT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-qdrant)
            SKIP_QDRANT=true
            shift
            ;;
        --help)
            cat <<EOF
Usage: install.sh [OPTIONS]

Install CLAMS globally for Claude Code.

OPTIONS:
    --dry-run        Show what would be configured without making changes
    --skip-qdrant    Skip Qdrant setup (use existing instance)
    --help           Show this help message

EXAMPLES:
    ./scripts/install.sh                    # Full installation
    ./scripts/install.sh --dry-run          # Preview changes
    ./scripts/install.sh --skip-qdrant      # Use existing Qdrant

PREREQUISITES:
    - Python 3.12+
    - uv (https://astral.sh/uv/install.sh)
    - Docker (unless --skip-qdrant)
    - jq (for JSON processing)

EOF
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Banner
echo ""
echo "=========================================="
echo "  CLAMS Installation"
echo "=========================================="
echo ""

if [ "$DRY_RUN" = true ]; then
    warning "DRY RUN MODE - No changes will be made"
    echo ""
fi

check_prerequisites() {
    step "Checking prerequisites"

    local errors=()

    # Python version
    if ! command -v python3 &> /dev/null; then
        errors+=("Python 3 not found. Install from https://www.python.org/downloads/")
    else
        python_version=$(python3 --version | awk '{print $2}')
        python_major=$(echo "$python_version" | cut -d. -f1)
        python_minor=$(echo "$python_version" | cut -d. -f2)
        if [ "$python_major" -lt 3 ] || ([ "$python_major" -eq 3 ] && [ "$python_minor" -lt 12 ]); then
            errors+=("Python 3.12+ required (found $python_version). Upgrade from https://www.python.org/downloads/")
        fi
    fi

    # uv
    if ! command -v uv &> /dev/null; then
        errors+=("uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
    fi

    # jq
    if ! command -v jq &> /dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            errors+=("jq not found. Install with: brew install jq")
        else
            errors+=("jq not found. Install with: sudo apt-get install jq (or equivalent)")
        fi
    fi

    # Docker (if not skipping Qdrant)
    if [ "$SKIP_QDRANT" = false ]; then
        if ! command -v docker &> /dev/null; then
            errors+=("Docker not found. Install from https://docs.docker.com/get-docker/")
        elif ! docker info &> /dev/null; then
            errors+=("Docker daemon not running. Start Docker Desktop or systemd service.")
        fi
    fi

    # Report all errors at once
    if [ ${#errors[@]} -gt 0 ]; then
        error "Missing prerequisites:"
        for err in "${errors[@]}"; do
            echo "  - $err"
        done
        echo ""
        echo "Fix the above issues and re-run this script."
        exit 1
    fi

    success "All prerequisites met"
}

check_port_available() {
    local port=$1
    local port_in_use=false

    # Try lsof first (macOS and some Linux)
    if command -v lsof &> /dev/null; then
        if lsof -Pi :$port -sTCP:LISTEN -t &> /dev/null; then
            port_in_use=true
        fi
    # Fallback to ss (modern Linux)
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$port "; then
            port_in_use=true
        fi
    # Fallback to netstat (older systems)
    elif command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            port_in_use=true
        fi
    else
        warning "Cannot check port availability (lsof/ss/netstat not found)"
        warning "If installation fails, port $port may be in use"
        return
    fi

    if [ "$port_in_use" = true ]; then
        error "Port $port is already in use."
        echo ""
        echo "Options:"
        echo "  1. Stop the process using port $port"
        echo "  2. Run with --skip-qdrant if you have Qdrant running elsewhere"
        echo "  3. Modify docker-compose.yml to use different ports"
        exit 1
    fi
}

setup_qdrant() {
    step "Setting up Qdrant"

    if [ "$SKIP_QDRANT" = true ]; then
        warning "Skipping Qdrant setup (--skip-qdrant flag)"
        return
    fi

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would start Qdrant container via docker-compose"
        return
    fi

    check_port_available 6333

    info "Starting Qdrant container..."
    docker-compose up -d --wait

    # Verify health
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:6333/healthz &> /dev/null; then
            success "Qdrant is healthy"
            return
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    error "Qdrant failed to become healthy after ${max_attempts}s"
    docker-compose logs qdrant
    exit 1
}

setup_python_env() {
    step "Installing Python dependencies"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would run: uv sync"
        return
    fi

    info "Running uv sync..."
    if ! uv sync; then
        error "Failed to install dependencies"
        echo ""
        echo "Troubleshooting:"
        echo "  - Check your internet connection"
        echo "  - Try: uv cache clean && uv sync"
        exit 1
    fi

    success "Dependencies installed"
}

start_daemon() {
    step "Starting CLAMS daemon"

    local clams_bin="$REPO_ROOT/.venv/bin/clams-server"
    local pid_file="$HOME/.clams/server.pid"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would start daemon: $clams_bin --daemon"
        return
    fi

    # Check if already running
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        info "CLAMS daemon is already running"
        return
    fi

    # Start daemon
    "$clams_bin" --daemon --http --port 6334

    # Wait a moment for daemon to start
    sleep 2

    # Verify daemon started
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        success "CLAMS daemon started (PID: $(cat "$pid_file"))"
    else
        warning "CLAMS daemon may have failed to start - check ~/.clams/server.log"
    fi
}

configure_mcp_server() {
    step "Configuring MCP server"

    local config_file="$HOME/.claude.json"
    local clams_bin="$REPO_ROOT/.venv/bin/clams-server"

    if [ "$DRY_RUN" = false ] && [ ! -x "$clams_bin" ]; then
        error "clams-server not found at $clams_bin"
        echo "Did dependency installation fail?"
        exit 1
    fi

    # Build server config JSON for HTTP+SSE transport
    local server_config=$(jq -n \
        '{
            name: "clams",
            config: {
                type: "sse",
                url: "http://127.0.0.1:6334/sse"
            }
        }')

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would add to $config_file:"
        echo "$server_config" | jq .
        return
    fi

    # Use json_merge.py to safely add server
    if python3 "$REPO_ROOT/scripts/json_merge.py" \
        add-server \
        --config-file "$config_file" \
        --data "$server_config"; then
        success "MCP server configured in $config_file"
    else
        warning "MCP server was already configured (no changes made)"
    fi
}

register_hooks() {
    step "Registering hooks"

    local settings_file="$HOME/.claude/settings.json"

    # Verify hook scripts exist before registering
    local hook_scripts=(
        "$REPO_ROOT/.claude/hooks/session_start.sh"
        "$REPO_ROOT/.claude/hooks/user_prompt_submit.sh"
        "$REPO_ROOT/.claude/hooks/ghap_checkin.sh"
        "$REPO_ROOT/.claude/hooks/outcome_capture.sh"
    )

    if [ "$DRY_RUN" = false ]; then
        for hook_script in "${hook_scripts[@]}"; do
            if [ ! -f "$hook_script" ]; then
                error "Hook script not found: $hook_script"
                echo "Installation directory may be incomplete."
                exit 1
            fi
        done
    fi

    # Build hooks config JSON with absolute paths
    local hooks_config=$(jq -n \
        --arg session_start "$REPO_ROOT/.claude/hooks/session_start.sh" \
        --arg user_prompt "$REPO_ROOT/.claude/hooks/user_prompt_submit.sh" \
        --arg ghap_checkin "$REPO_ROOT/.claude/hooks/ghap_checkin.sh" \
        --arg outcome "$REPO_ROOT/.claude/hooks/outcome_capture.sh" \
        '{
            SessionStart: [
                {
                    matcher: "startup",
                    hooks: [{type: "command", command: $session_start}]
                }
            ],
            UserPromptSubmit: [
                {
                    hooks: [{type: "command", command: $user_prompt}]
                }
            ],
            PreToolUse: [
                {
                    matcher: "*",
                    hooks: [{type: "command", command: $ghap_checkin}]
                }
            ],
            PostToolUse: [
                {
                    matcher: "Bash(pytest:*)|Bash(npm test:*)|Bash(cargo test:*)",
                    hooks: [{type: "command", command: $outcome}]
                }
            ]
        }')

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would add to $settings_file:"
        echo "$hooks_config" | jq .
        return
    fi

    # Use json_merge.py to safely add hooks
    if python3 "$REPO_ROOT/scripts/json_merge.py" \
        add-hooks \
        --config-file "$settings_file" \
        --data "$hooks_config"; then
        success "Hooks registered in $settings_file"
    else
        warning "Hooks were already registered (no changes made)"
    fi
}

initialize_storage() {
    step "Initializing storage directory"

    local clams_dir="$HOME/.clams"
    local journal_dir="$clams_dir/journal"
    local archive_dir="$journal_dir/archive"
    local session_id="$journal_dir/.session_id"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would create:"
        echo "  - $clams_dir"
        echo "  - $journal_dir"
        echo "  - $archive_dir"
        echo "  - $session_id (with new UUID)"
        return
    fi

    # Create directories
    mkdir -p "$archive_dir"

    # Create session ID if doesn't exist
    if [ ! -f "$session_id" ]; then
        # Generate UUID (macOS and Linux compatible)
        if command -v uuidgen &> /dev/null; then
            uuidgen > "$session_id"
        else
            python3 -c "import uuid; print(uuid.uuid4())" > "$session_id"
        fi
        info "Generated session ID: $(cat $session_id)"
    else
        info "Using existing session ID: $(cat $session_id)"
    fi

    # Create empty journal if doesn't exist
    local journal_file="$journal_dir/session_entries.jsonl"
    if [ ! -f "$journal_file" ]; then
        touch "$journal_file"
    fi

    success "Storage initialized at $clams_dir"
}

verify_installation() {
    step "Verifying installation"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would verify:"
        echo "  - Storage directory structure"
        echo "  - MCP server binary"
        return
    fi

    if python3 "$REPO_ROOT/scripts/verify_install.py" "$REPO_ROOT/.venv"; then
        success "Installation verified"
    else
        error "Installation verification failed"
        exit 1
    fi
}

# Run installation steps
check_prerequisites
setup_qdrant
setup_python_env
configure_mcp_server
register_hooks
initialize_storage
start_daemon
verify_installation

# Success summary
echo ""
echo "=========================================="
success "CLAMS installed successfully!"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  - MCP server: ~/.claude.json (HTTP+SSE transport)"
echo "  - Hooks: ~/.claude/settings.json"
echo "  - Storage: ~/.clams/"
echo "  - Daemon: http://127.0.0.1:6334 (PID file: ~/.clams/server.pid)"
if [ "$SKIP_QDRANT" = false ]; then
    echo "  - Qdrant: http://localhost:6333"
fi
echo ""
echo "Daemon management:"
echo "  - Start: clams-server --daemon"
echo "  - Stop:  clams-server --stop"
echo "  - Logs:  ~/.clams/server.log"
echo ""
echo "Next steps:"
echo "  1. Start a new Claude Code session"
echo "  2. Hooks will automatically inject context"
echo "  3. Use MCP tools: mcp__clams__ping, mcp__clams__store_memory, etc."
echo ""
