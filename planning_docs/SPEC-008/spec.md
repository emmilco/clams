# SPEC-008: HTTP Transport for Singleton MCP Server

## Background

SPEC-002-19 designed a hook system for automatic context injection and GHAP state management. The hooks were implemented as shell scripts that call MCP tools via `mcp_client.py`. However:

1. **The MCP tools were never implemented**: `start_session`, `get_orphaned_ghap`, `should_check_in`, `reset_tool_count`, `end_session`, and `assemble_context` don't exist in the MCP server
2. **The architecture is fundamentally slow**: Each MCP call spawns a new server process that loads embedding models (10+ seconds per call)
3. **The hooks silently fail**: They gracefully degrade to empty responses, so users don't know they're broken

The root cause is that hooks spawn their own MCP server instances via stdio, while Claude Code has a separate server instance running. The hooks can't connect to Claude's server because stdio pipes are 1:1.

## Problem Statement

The current hook implementation:
- Takes 10-15 seconds on session start (spawns 3 MCP servers sequentially)
- Never actually works (calls non-existent MCP tools)
- Wastes resources loading embedding models for simple file I/O operations

Users experience:
- Long delays when starting Claude Code sessions
- No context injection (hooks silently return empty data)
- No GHAP lifecycle management

## Goals

1. **Singleton server**: All callers (Claude Code + hooks) connect to one running instance
2. **Performance**: Hooks complete in < 200ms (after server is warm)
3. **Non-blocking startup**: SessionStart hook doesn't wait for server to load models
4. **Functionality**: Hooks work as originally designed in SPEC-002-19

## Non-Goals

- Direct file access bypass (we're fixing the architecture instead)
- Domain-specific premortem (deferred in SPEC-002-19)

## Solution Overview

Switch from stdio to HTTP transport:

1. **MCP server runs as HTTP daemon** on `localhost:6334`
2. **Models load once** at daemon startup, stay in memory
3. **Claude Code connects via HTTP** (change `~/.claude.json` config)
4. **Hooks connect via HTTP** (simple curl/httpx calls to same server)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Claude Code ──HTTP──┐                                 │
│                       ├──> clams-server :6334           │
│   Hook scripts ──HTTP─┘    (singleton, models loaded)   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Hook Behavior

### SessionStart Hook
- **Non-blocking**: Don't wait for server to finish loading
- Check if daemon is running (quick health check)
- If not running, start daemon in background (don't wait for model load)
- Initialize session state (write `.session_id`)
- Check for orphaned GHAP (file read only)
- Exit immediately (< 50ms)
- **No context injection** at this stage

### UserPromptSubmit Hook
- **Blocking**: Wait for server if still starting
- Server should be ready by now (user took time to type)
- Query server for values/context
- Inject context into prompt
- If server ready: < 200ms
- If server still loading: wait up to 30s, then graceful degrade

### PreToolUse Hook (ghap_checkin.sh)
- Check tool count, remind about GHAP if needed
- Quick HTTP call to running server
- < 200ms

### PostToolUse Hook (outcome_capture.sh)
- Detect test/build outcomes
- Prompt for GHAP resolution
- < 200ms

## Detailed Design

### 1. MCP Server Changes (`src/clams/server/main.py`)

Add HTTP+SSE transport support:

```python
# New entry point for HTTP mode
def run_http(host: str = "127.0.0.1", port: int = 6334):
    """Run MCP server with HTTP transport."""
    # MCP SDK supports this via mcp.server.http
    app = create_http_app(server)
    uvicorn.run(app, host=host, port=port)
```

Server startup:
1. Load embedding models (one-time cost)
2. Initialize Qdrant connections
3. Start HTTP server on port 6334
4. Write PID file for lifecycle management

### 2. Daemon Management

**PID file**: `~/.clams/server.pid`
**Log file**: `~/.clams/server.log`

```bash
# Start daemon (in install.sh or session_start.sh)
start_daemon() {
    if is_running; then
        return 0  # Already running
    fi
    nohup clams-server --http --port 6334 > ~/.clams/server.log 2>&1 &
    echo $! > ~/.clams/server.pid
}

# Check if running
is_running() {
    [ -f ~/.clams/server.pid ] && kill -0 $(cat ~/.clams/server.pid) 2>/dev/null
}

# Health check (with timeout)
wait_for_ready() {
    for i in {1..30}; do
        curl -s http://localhost:6334/health && return 0
        sleep 1
    done
    return 1
}
```

### 3. Claude Code Configuration

Update `~/.claude.json`:

```json
{
  "mcpServers": {
    "clams": {
      "type": "sse",
      "url": "http://localhost:6334/sse"
    }
  }
}
```

### 4. Hook Scripts

#### `session_start.sh` (Non-blocking)
```bash
#!/bin/bash
# Ensure daemon is starting (don't wait for ready)
start_daemon_if_needed  # Returns immediately

# These operations are local file I/O only (no server needed)
SESSION_ID=$(generate_session_id)
echo "$SESSION_ID" > ~/.clams/journal/.session_id

# Check for orphaned GHAP (local file read)
if [ -f ~/.clams/journal/current_ghap.json ]; then
    ORPHAN=$(check_orphan_ghap)
    if [ -n "$ORPHAN" ]; then
        echo '{"type": "orphan_detected", "content": "..."}'
        exit 0
    fi
fi

# No context injection at session start - defer to first prompt
echo '{"type": "session_started", "session_id": "'$SESSION_ID'"}'
exit 0
```

#### `user_prompt_submit.sh` (Blocking)
```bash
#!/bin/bash
# Wait for server to be ready (blocking)
if ! wait_for_ready 30; then
    echo '{"type": "degraded", "content": "Server not available"}'
    exit 0
fi

# Now call MCP tools via HTTP
CONTEXT=$(curl -s -X POST http://localhost:6334/tools/assemble_context \
    -H "Content-Type: application/json" \
    -d '{"query": "'"$USER_PROMPT"'", "context_types": ["values"], "limit": 10}')

echo '{"type": "rich", "content": '"$CONTEXT"'}'
exit 0
```

#### `ghap_checkin.sh`
```bash
#!/bin/bash
# Quick check - server should be running by now
SHOULD_CHECKIN=$(curl -s http://localhost:6334/tools/should_check_in \
    -d '{"frequency": 10}' 2>/dev/null || echo '{"should_check_in": false}')

if [ "$(echo $SHOULD_CHECKIN | jq -r '.should_check_in')" = "true" ]; then
    GHAP=$(curl -s http://localhost:6334/tools/get_active_ghap)
    echo '{"type": "reminder", "content": "..."}'
fi
exit 0
```

### 5. Missing MCP Tools

These tools need to be implemented in `src/clams/server/tools/`:

| Tool | Purpose | Implementation |
|------|---------|----------------|
| `start_session` | Initialize session, return ID | Write to journal file |
| `get_orphaned_ghap` | Check for GHAP from previous session | Read `current_ghap.json`, compare session ID |
| `should_check_in` | Check if GHAP reminder due | Read `.tool_count`, compare to frequency |
| `reset_tool_count` | Reset counter after reminder | Write "0" to `.tool_count` |
| `end_session` | Clean up session state | Archive current GHAP if any |
| `assemble_context` | Get relevant context for prompt | Query Qdrant for values/experiences |

### 6. Install/Uninstall Scripts

**install.sh additions**:
```bash
# Start daemon
echo "Starting CLAMS server daemon..."
clams-server --http --port 6334 --daemon

# Wait for ready
echo "Waiting for server to initialize..."
wait_for_ready 60 || echo "Warning: Server slow to start"

# Configure Claude Code for HTTP
update_claude_json_for_http
```

**uninstall.sh additions**:
```bash
# Stop daemon
if [ -f ~/.clams/server.pid ]; then
    kill $(cat ~/.clams/server.pid) 2>/dev/null
    rm ~/.clams/server.pid
fi
```

## Acceptance Criteria

### Server
- [ ] MCP server supports HTTP+SSE transport
- [ ] Server runs as daemon, writes PID file
- [ ] Health endpoint responds at `/health`
- [ ] Models load once at startup, stay in memory
- [ ] Server auto-restarts if crashed (optional, nice-to-have)

### Performance
- [ ] `session_start.sh` completes in < 50ms (non-blocking)
- [ ] `user_prompt_submit.sh` completes in < 200ms (after server warm)
- [ ] `ghap_checkin.sh` completes in < 200ms
- [ ] `outcome_capture.sh` completes in < 200ms
- [ ] Server startup (cold) < 15s (model loading)
- [ ] Regression tests verify timing

### Functionality
- [ ] Claude Code can call MCP tools via HTTP
- [ ] All hooks can call MCP tools via HTTP
- [ ] Missing tools implemented: `start_session`, `get_orphaned_ghap`, `should_check_in`, `reset_tool_count`, `assemble_context`
- [ ] Session lifecycle works (start → prompts → GHAP tracking → end)
- [ ] Orphaned GHAP detection works across sessions

### Installation
- [ ] `install.sh` starts daemon and configures HTTP transport
- [ ] `uninstall.sh` stops daemon and cleans up
- [ ] Daemon survives terminal close (proper daemonization)

## Migration

1. Update MCP server to support HTTP transport
2. Implement missing MCP tools
3. Update hook scripts to use HTTP calls
4. Update install/uninstall scripts for daemon management
5. Change `~/.claude.json` config from stdio to HTTP

## Open Questions

1. **Daemon management**: Use systemd/launchd, or simple PID file approach?
   - **Recommendation**: PID file for simplicity. Systemd/launchd adds platform-specific complexity.

2. **Port conflict**: What if 6334 is in use?
   - **Recommendation**: Make port configurable, fail with clear error message.

3. **Server crash recovery**: Auto-restart daemon?
   - **Recommendation**: For v1, manual restart. Auto-restart adds complexity.
