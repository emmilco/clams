# SPEC-008: Technical Proposal

## HTTP Transport for Singleton MCP Server

---

## 1. Architecture Overview

### 1.1 Current State

The current architecture has a fundamental problem: each hook invocation spawns a new MCP server process via stdio transport. This means:

```
Session Start Hook:
  -> spawn clams-server process #1 (load models: ~10s)
  -> call start_session tool
  -> spawn clams-server process #2 (load models: ~10s)
  -> call get_orphaned_ghap tool
  -> spawn clams-server process #3 (load models: ~10s)
  -> call assemble_context tool
```

Meanwhile, Claude Code runs its own separate clams-server process via stdio. The hooks cannot communicate with Claude Code's server because stdio pipes are 1:1.

### 1.2 Target State

Switch to HTTP+SSE transport with a singleton daemon:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   clams-server daemon (HTTP on :6334)                        │
│   ├── Models loaded once at startup                          │
│   ├── Qdrant connection pooled                               │
│   └── Session state in memory/files                          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Claude Code ───── SSE /sse endpoint ─────┐                 │
│                                            │                 │
│   session_start.sh ─── HTTP POST /mcp ─────┼──> Server       │
│   user_prompt_submit.sh ── HTTP POST /mcp ─┤                 │
│   ghap_checkin.sh ─── HTTP POST /mcp ──────┤                 │
│   outcome_capture.sh ─ HTTP POST /mcp ─────┘                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 MCP SDK SSE Transport

The MCP Python SDK (v0.9.1, currently installed) provides `SseServerTransport` in `mcp.server.sse`. This transport:

1. Exposes a GET `/sse` endpoint that returns an SSE stream
2. Exposes a POST endpoint (configurable) for receiving messages
3. Uses session IDs to route messages to the correct SSE connection

Key implementation details from the SDK:

```python
class SseServerTransport:
    def __init__(self, endpoint: str) -> None:
        """
        Creates SSE transport. The endpoint parameter is the URL
        where clients should POST messages.
        """
        self._endpoint = endpoint  # e.g., "/mcp"
        self._read_stream_writers = {}  # session_id -> stream

    async def connect_sse(self, scope, receive, send):
        """ASGI handler for GET /sse - establishes SSE connection"""
        # Creates session_id
        # Sends "endpoint" event with session URI
        # Streams server messages to client

    async def handle_post_message(self, scope, receive, send):
        """ASGI handler for POST /mcp - receives client messages"""
        # Extracts session_id from query params
        # Routes message to correct session's read stream
```

The SDK is designed for Starlette/ASGI, so we'll use Starlette as the web framework.

---

## 2. Implementation Details

### 2.1 MCP Server HTTP Transport (`src/clams/server/main.py`)

**New module: `src/clams/server/http.py`**

```python
"""HTTP transport for CLAMS MCP server using Starlette + SSE."""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from clams.server.config import ServerSettings
from clams.server.tools import ServiceContainer, register_all_tools

logger = structlog.get_logger()

# Paths for daemon management
PID_FILE = Path.home() / ".clams" / "server.pid"
LOG_FILE = Path.home() / ".clams" / "server.log"


class HttpServer:
    """HTTP server wrapper for the MCP server."""

    def __init__(
        self,
        server: Server,
        services: ServiceContainer,
        host: str = "127.0.0.1",
        port: int = 6334,
    ) -> None:
        self.server = server
        self.services = services
        self.host = host
        self.port = port
        self.sse_transport = SseServerTransport("/mcp")
        self._running = False

    async def health_handler(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "server": "clams",
            "version": "0.1.0",
        })

    async def sse_handler(self, request: Request) -> Any:
        """SSE connection handler for Claude Code."""
        async with self.sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    async def message_handler(self, request: Request) -> Any:
        """Message handler for hook scripts (POST /mcp)."""
        await self.sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )

    def create_app(self) -> Starlette:
        """Create the Starlette application."""
        routes = [
            Route("/health", self.health_handler, methods=["GET"]),
            Route("/sse", self.sse_handler, methods=["GET"]),
            Route("/mcp", self.message_handler, methods=["POST"]),
        ]

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            )
        ]

        return Starlette(routes=routes, middleware=middleware)

    async def run(self) -> None:
        """Run the HTTP server."""
        self._running = True
        app = self.create_app()

        # Write PID file
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Setup signal handlers for graceful shutdown
        def handle_shutdown(signum: int, frame: Any) -> None:
            logger.info("server.shutdown_requested", signal=signum)
            self._running = False
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

        try:
            await server.serve()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("server.shutting_down")

        # Close services
        await self.services.close()

        # Remove PID file
        if PID_FILE.exists():
            PID_FILE.unlink()

        logger.info("server.shutdown_complete")
```

**Updates to `src/clams/server/main.py`:**

```python
import argparse
import os
import sys
from pathlib import Path

from clams.server.config import ServerSettings
from clams.server.http import HttpServer, PID_FILE, LOG_FILE


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="CLAMS MCP Server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with HTTP transport (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6334,
        help="HTTP server port (default: 6334)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as background daemon (implies --http)",
    )
    return parser.parse_args()


def daemonize() -> None:
    """Fork into a background daemon process."""
    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Parent exits

    # Create new session
    os.setsid()

    # Second fork (prevent acquiring controlling terminal)
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect standard file descriptors
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    # Truncate log file on restart (simple log rotation for v1)
    with open(LOG_FILE, "w") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())


async def run_http_server(settings: ServerSettings, host: str, port: int) -> None:
    """Run the MCP server with HTTP transport."""
    from clams.embedding import get_code_embedder, get_semantic_embedder

    server, services = await create_server(settings)
    http_server = HttpServer(server, services, host=host, port=port)
    await http_server.run()


def main() -> None:
    """Entry point for the MCP server."""
    args = parse_args()

    # Load configuration
    settings = ServerSettings()

    # Configure logging
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info("clams.starting", version="0.1.0", mode="http" if args.http or args.daemon else "stdio")

    # Daemonize if requested
    if args.daemon:
        daemonize()
        args.http = True  # Daemon implies HTTP

    # Validate configuration
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Initialize embedding registry
    initialize_registry(settings.code_model, settings.semantic_model)
    logger.info("embedding_registry.initialized")

    try:
        if args.http:
            asyncio.run(run_http_server(settings, args.host, args.port))
        else:
            asyncio.run(run_server(settings))  # Original stdio mode
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise
```

### 2.2 Session Tools Implementation (`src/clams/server/tools/session.py`)

**New file: `src/clams/server/tools/session.py`**

```python
"""Session management tools for hooks.

These tools support the hook lifecycle without requiring heavy server resources.
Most operations are simple file I/O with in-memory counters.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from mcp.server import Server

logger = structlog.get_logger()

# Session state paths
CLAMS_DIR = Path.home() / ".clams"
JOURNAL_DIR = CLAMS_DIR / "journal"
SESSION_ID_FILE = JOURNAL_DIR / ".session_id"
TOOL_COUNT_FILE = JOURNAL_DIR / ".tool_count"
CURRENT_GHAP_FILE = JOURNAL_DIR / "current_ghap.json"


class SessionManager:
    """Manages session state for hooks."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self._tool_count = 0
        self._load_tool_count()

    def _load_tool_count(self) -> None:
        """Load tool count from file."""
        if TOOL_COUNT_FILE.exists():
            try:
                self._tool_count = int(TOOL_COUNT_FILE.read_text().strip())
            except (ValueError, OSError):
                self._tool_count = 0

    def _save_tool_count(self) -> None:
        """Save tool count to file."""
        TOOL_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOOL_COUNT_FILE.write_text(str(self._tool_count))


def register_session_tools(server: Server, session_manager: SessionManager) -> None:
    """Register session management tools with the server."""
    # Tools are registered via the tool registry pattern in __init__.py
    pass


def get_session_tools(session_manager: SessionManager) -> dict[str, Any]:
    """Get session tool implementations."""

    async def start_session() -> dict[str, Any]:
        """Initialize a new session.

        Returns:
            Session info including session_id
        """
        # Generate new session ID
        session_id = str(uuid.uuid4())

        # Write session ID
        SESSION_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_ID_FILE.write_text(session_id)

        # Reset tool count for new session
        session_manager._tool_count = 0
        session_manager._save_tool_count()

        logger.info("session.started", session_id=session_id)
        return {
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat(),
        }

    async def get_orphaned_ghap() -> dict[str, Any]:
        """Check for orphaned GHAP from previous session.

        Returns:
            Orphan info if found, empty otherwise
        """
        if not CURRENT_GHAP_FILE.exists():
            return {"has_orphan": False}

        try:
            ghap_data = json.loads(CURRENT_GHAP_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {"has_orphan": False}

        # Get current session ID
        current_session = None
        if SESSION_ID_FILE.exists():
            try:
                current_session = SESSION_ID_FILE.read_text().strip()
            except OSError:
                pass

        # Check if GHAP belongs to a different session
        ghap_session = ghap_data.get("session_id")
        if ghap_session and ghap_session != current_session:
            logger.info(
                "session.orphan_detected",
                ghap_session=ghap_session,
                current_session=current_session,
            )
            return {
                "has_orphan": True,
                "session_id": ghap_session,
                "goal": ghap_data.get("goal", "Unknown"),
                "hypothesis": ghap_data.get("hypothesis", "Unknown"),
                "action": ghap_data.get("action", "Unknown"),
                "created_at": ghap_data.get("created_at"),
            }

        return {"has_orphan": False}

    async def should_check_in(frequency: int = 10) -> dict[str, bool]:
        """Check if GHAP reminder is due.

        Args:
            frequency: Number of tool calls between reminders

        Returns:
            Whether a check-in reminder should be shown
        """
        should_remind = session_manager._tool_count >= frequency
        return {"should_check_in": should_remind}

    async def increment_tool_count() -> dict[str, int]:
        """Increment the tool counter.

        Returns:
            New tool count
        """
        session_manager._tool_count += 1
        session_manager._save_tool_count()
        return {"tool_count": session_manager._tool_count}

    async def reset_tool_count() -> dict[str, int]:
        """Reset tool counter after showing reminder.

        Returns:
            Tool count (always 0)
        """
        session_manager._tool_count = 0
        session_manager._save_tool_count()
        return {"tool_count": 0}

    return {
        "start_session": start_session,
        "get_orphaned_ghap": get_orphaned_ghap,
        "should_check_in": should_check_in,
        "increment_tool_count": increment_tool_count,
        "reset_tool_count": reset_tool_count,
    }
```

### 2.3 Context Assembly Tool (`src/clams/server/tools/context.py`)

**New file: `src/clams/server/tools/context.py`**

```python
"""Context assembly tool for user prompt injection.

This tool queries stored values and experiences to provide relevant
context when the user submits a prompt.
"""

from typing import Any

import structlog

from clams.search import Searcher
from clams.values import ValueStore

logger = structlog.get_logger()


def get_context_tools(
    searcher: Searcher,
    value_store: ValueStore,
) -> dict[str, Any]:
    """Get context assembly tool implementations."""

    async def assemble_context(
        query: str,
        context_types: list[str] | None = None,
        limit: int = 10,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Assemble relevant context for a user prompt.

        Args:
            query: User's prompt text
            context_types: Types to include ("values", "experiences")
            limit: Maximum items per type
            max_tokens: Approximate token budget

        Returns:
            Assembled context as markdown with metadata
        """
        if context_types is None:
            context_types = ["values", "experiences"]

        sections: list[str] = []
        total_items = 0

        # Get values (distilled learnings)
        if "values" in context_types:
            try:
                values = await value_store.list_values(limit=limit)
                if values:
                    value_lines = [f"- {v['text']}" for v in values]
                    sections.append("## Learned Values\n" + "\n".join(value_lines))
                    total_items += len(values)
            except Exception as e:
                logger.warning("context.values_failed", error=str(e))

        # Get relevant experiences
        if "experiences" in context_types and query:
            try:
                experiences = await searcher.search_experiences(
                    query=query,
                    limit=min(limit, 5),  # Fewer experiences, they're verbose
                )
                if experiences:
                    exp_lines = []
                    for exp in experiences:
                        exp_lines.append(
                            f"- **{exp.get('domain', 'unknown')}**: "
                            f"{exp.get('goal', 'No goal')} "
                            f"({exp.get('outcome', 'unknown')})"
                        )
                    sections.append(
                        "## Relevant Experiences\n" + "\n".join(exp_lines)
                    )
                    total_items += len(experiences)
            except Exception as e:
                logger.warning("context.experiences_failed", error=str(e))

        # Build markdown
        if sections:
            markdown = "\n\n".join(sections)
        else:
            markdown = ""

        # Rough token estimate (4 chars per token)
        token_count = len(markdown) // 4

        return {
            "markdown": markdown,
            "token_count": token_count,
            "item_count": total_items,
            "truncated": token_count > max_tokens,
        }

    return {
        "assemble_context": assemble_context,
    }
```

### 2.4 Updated Tool Registration

**Updates to `src/clams/server/tools/__init__.py`:**

Add session and context tools to the registration flow:

```python
# In register_all_tools():

# Initialize session manager
from .session import SessionManager, get_session_tools
session_manager = SessionManager()
tool_registry.update(get_session_tools(session_manager))

# Initialize context assembly
from .context import get_context_tools
tool_registry.update(get_context_tools(searcher, value_store))
```

Add tool definitions to `_get_all_tool_definitions()`:

```python
# === Session Tools (SPEC-008) ===
Tool(
    name="start_session",
    description="Initialize a new session.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
Tool(
    name="get_orphaned_ghap",
    description="Check for orphaned GHAP from previous session.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
Tool(
    name="should_check_in",
    description="Check if GHAP reminder is due.",
    inputSchema={
        "type": "object",
        "properties": {
            "frequency": {
                "type": "integer",
                "description": "Tool calls between reminders (default 10)",
                "default": 10,
            },
        },
        "required": [],
    },
),
Tool(
    name="increment_tool_count",
    description="Increment the tool counter.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
Tool(
    name="reset_tool_count",
    description="Reset tool counter after reminder.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
# === Context Tools (SPEC-008) ===
Tool(
    name="assemble_context",
    description="Assemble relevant context for a user prompt.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "User's prompt text",
            },
            "context_types": {
                "type": "array",
                "items": {"type": "string", "enum": ["values", "experiences"]},
                "description": "Types to include (default: both)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum items per type (default 10)",
                "default": 10,
            },
            "max_tokens": {
                "type": "integer",
                "description": "Approximate token budget (default 1500)",
                "default": 1500,
            },
        },
        "required": ["query"],
    },
),
```

### 2.5 Hook Script Updates

#### `.claude/hooks/session_start.sh`

```bash
#!/bin/bash
# .claude/hooks/session_start.sh
# Hook: SessionStart
# Purpose: Initialize session (non-blocking)

set -uo pipefail

CLAMS_DIR="$HOME/.clams"
JOURNAL_DIR="$CLAMS_DIR/journal"
PID_FILE="$CLAMS_DIR/server.pid"
CURRENT_GHAP="$JOURNAL_DIR/current_ghap.json"
SESSION_ID_FILE="$JOURNAL_DIR/.session_id"

# Ensure directories exist
mkdir -p "$JOURNAL_DIR"

# Start daemon if not running (non-blocking)
start_daemon_if_needed() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        return 0  # Already running
    fi

    # Get clams-server path from this script's location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    CLAMS_SERVER="$REPO_ROOT/.venv/bin/clams-server"

    if [ -x "$CLAMS_SERVER" ]; then
        # Start daemon in background (don't wait for model loading)
        "$CLAMS_SERVER" --daemon --http --port 6334 &
    fi
}

# Generate session ID (local operation)
generate_session_id() {
    if command -v uuidgen &>/dev/null; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        python3 -c "import uuid; print(uuid.uuid4())"
    fi
}

# Check for orphaned GHAP (local file read)
check_orphan() {
    if [ ! -f "$CURRENT_GHAP" ]; then
        return 1
    fi

    local current_session=""
    if [ -f "$SESSION_ID_FILE" ]; then
        current_session=$(cat "$SESSION_ID_FILE" 2>/dev/null || echo "")
    fi

    local ghap_session
    ghap_session=$(jq -r '.session_id // ""' "$CURRENT_GHAP" 2>/dev/null || echo "")

    if [ -n "$ghap_session" ] && [ "$ghap_session" != "$current_session" ]; then
        # Found orphan
        jq '{
            goal: .goal,
            hypothesis: .hypothesis,
            action: .action,
            created_at: .created_at
        }' "$CURRENT_GHAP" 2>/dev/null
        return 0
    fi
    return 1
}

# Main execution (all non-blocking local operations)
start_daemon_if_needed

# Generate and save new session ID
SESSION_ID=$(generate_session_id)
echo "$SESSION_ID" > "$SESSION_ID_FILE"

# Check for orphaned GHAP
ORPHAN=$(check_orphan)
if [ -n "$ORPHAN" ]; then
    GOAL=$(echo "$ORPHAN" | jq -r '.goal // "Unknown"')
    HYPOTHESIS=$(echo "$ORPHAN" | jq -r '.hypothesis // "Unknown"')

    cat <<EOF
{
  "type": "orphan_detected",
  "content": "## Orphaned GHAP Detected\n\nFrom previous session:\n\n**Goal**: $GOAL\n**Hypothesis**: $HYPOTHESIS\n\n**Options**:\n- Adopt and continue this work\n- Abandon with reason"
}
EOF
else
    cat <<EOF
{
  "type": "session_started",
  "session_id": "$SESSION_ID"
}
EOF
fi

exit 0
```

#### `.claude/hooks/user_prompt_submit.sh`

```bash
#!/bin/bash
# .claude/hooks/user_prompt_submit.sh
# Hook: UserPromptSubmit
# Purpose: Inject rich context (blocking, waits for server)

set -uo pipefail

SERVER_URL="http://localhost:6334"

# Wait for server to be ready (blocking)
wait_for_ready() {
    local max_wait=$1
    for ((i=1; i<=max_wait; i++)); do
        if curl -s --max-time 1 "$SERVER_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Call MCP tool via HTTP
call_mcp() {
    local tool_name="$1"
    local args="$2"

    # Build JSON-RPC request
    local request=$(jq -n \
        --arg method "tools/call" \
        --arg name "$tool_name" \
        --argjson args "$args" \
        '{
            jsonrpc: "2.0",
            id: 1,
            method: $method,
            params: {name: $name, arguments: $args}
        }')

    # Make HTTP request
    curl -s --max-time 5 \
        -X POST "$SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -d "$request" 2>/dev/null
}

# Read user prompt from stdin
USER_PROMPT=$(cat)

# Wait for server (max 30s)
if ! wait_for_ready 30; then
    cat <<EOF
{
  "type": "degraded",
  "reason": "server_timeout"
}
EOF
    exit 0
fi

# Call assemble_context tool
ARGS=$(jq -n \
    --arg query "$USER_PROMPT" \
    '{
        query: $query,
        context_types: ["values", "experiences"],
        limit: 10,
        max_tokens: 1500
    }')

RESULT=$(call_mcp "assemble_context" "$ARGS")

# Extract markdown content from JSON-RPC response
if [ -n "$RESULT" ]; then
    CONTENT=$(echo "$RESULT" | jq -r '.result.content[0].text // ""' 2>/dev/null)
    if [ -n "$CONTENT" ]; then
        MARKDOWN=$(echo "$CONTENT" | jq -r '.markdown // ""' 2>/dev/null)
        TOKEN_COUNT=$(echo "$CONTENT" | jq -r '.token_count // 0' 2>/dev/null)

        if [ -n "$MARKDOWN" ]; then
            cat <<EOF
{
  "type": "rich",
  "content": $(echo "$MARKDOWN" | jq -Rs .),
  "token_count": $TOKEN_COUNT
}
EOF
            exit 0
        fi
    fi
fi

# Fallback: no context
cat <<EOF
{
  "type": "degraded",
  "reason": "no_context"
}
EOF
exit 0
```

#### `.claude/hooks/ghap_checkin.sh`

```bash
#!/bin/bash
# .claude/hooks/ghap_checkin.sh
# Hook: PreToolUse
# Purpose: GHAP check-in reminder

set -uo pipefail

SERVER_URL="http://localhost:6334"
FREQUENCY=10

# Quick MCP call (1s timeout, don't block tool execution)
call_mcp_quick() {
    local tool_name="$1"
    local args="$2"

    local request=$(jq -n \
        --arg method "tools/call" \
        --arg name "$tool_name" \
        --argjson args "$args" \
        '{
            jsonrpc: "2.0",
            id: 1,
            method: $method,
            params: {name: $name, arguments: $args}
        }')

    curl -s --max-time 1 \
        -X POST "$SERVER_URL/mcp" \
        -H "Content-Type: application/json" \
        -d "$request" 2>/dev/null
}

# First increment tool count
call_mcp_quick "increment_tool_count" '{}' >/dev/null 2>&1

# Check if reminder is due
RESULT=$(call_mcp_quick "should_check_in" "{\"frequency\": $FREQUENCY}")
SHOULD_CHECKIN=$(echo "$RESULT" | jq -r '.result.content[0].text // "{}"' 2>/dev/null | jq -r '.should_check_in // false')

if [ "$SHOULD_CHECKIN" != "true" ]; then
    exit 0
fi

# Get current GHAP state
GHAP_RESULT=$(call_mcp_quick "get_active_ghap" '{}')
GHAP=$(echo "$GHAP_RESULT" | jq -r '.result.content[0].text // "{}"' 2>/dev/null)
GOAL=$(echo "$GHAP" | jq -r '.goal // "Unknown"')
HYPOTHESIS=$(echo "$GHAP" | jq -r '.hypothesis // "Unknown"')
PREDICTION=$(echo "$GHAP" | jq -r '.prediction // "Unknown"')

# Reset tool counter
call_mcp_quick "reset_tool_count" '{}' >/dev/null 2>&1

cat <<EOF
{
  "type": "reminder",
  "content": "## GHAP Check-in ($FREQUENCY tools since last update)\n\n**Current Goal**: $GOAL\n**Current Hypothesis**: $HYPOTHESIS\n**Current Prediction**: $PREDICTION\n\nIs your hypothesis still valid? If it changed, update your GHAP entry."
}
EOF

exit 0
```

### 2.6 Install/Uninstall Script Updates

#### `scripts/install.sh` additions

```bash
# After setup_python_env(), add:

start_daemon() {
    step "Starting CLAMS server daemon"

    local clams_server="$REPO_ROOT/.venv/bin/clams-server"
    local pid_file="$HOME/.clams/server.pid"

    if [ "$DRY_RUN" = true ]; then
        info "[DRY RUN] Would start daemon: $clams_server --daemon --http --port 6334"
        return
    fi

    # Check if already running
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        info "Daemon already running (PID: $(cat "$pid_file"))"
        return
    fi

    # Start daemon
    "$clams_server" --daemon --http --port 6334

    # Wait for server to be ready (up to 60s for model loading)
    info "Waiting for server to initialize (loading models)..."
    local max_wait=60
    for ((i=1; i<=max_wait; i++)); do
        if curl -s --max-time 1 http://localhost:6334/health >/dev/null 2>&1; then
            success "Server ready"
            return
        fi
        if [ $((i % 10)) -eq 0 ]; then
            info "Still waiting... ($i/${max_wait}s)"
        fi
        sleep 1
    done

    warning "Server slow to start (may still be loading models)"
}

# Update configure_mcp_server() to use HTTP:

configure_mcp_server() {
    step "Configuring MCP server"

    local config_file="$HOME/.claude.json"

    # Build server config JSON for HTTP/SSE transport
    local server_config=$(jq -n '{
        name: "clams",
        config: {
            type: "sse",
            url: "http://localhost:6334/sse"
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
        success "MCP server configured in $config_file (HTTP/SSE transport)"
    else
        warning "MCP server was already configured (no changes made)"
    fi
}
```

#### `scripts/uninstall.sh` additions

```bash
# Before removing MCP config, add:

stop_daemon() {
    info "Stopping CLAMS server daemon..."

    local pid_file="$HOME/.clams/server.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
            success "Stopped daemon (PID: $pid)"
        else
            info "Daemon not running"
        fi
        rm -f "$pid_file"
    else
        info "No PID file found (daemon not running)"
    fi
}

# Call at the start of uninstall
stop_daemon
```

---

## 3. API/Interface Design

### 3.1 HTTP Endpoints

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `/health` | GET | Health check | Hooks, monitoring |
| `/sse` | GET | SSE stream for Claude Code | Claude Code |
| `/mcp` | POST | JSON-RPC message handler | Hooks |

### 3.2 JSON-RPC Message Format

Hooks send JSON-RPC 2.0 requests to `/mcp`:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "assemble_context",
        "arguments": {
            "query": "How do I implement...",
            "context_types": ["values"],
            "limit": 10
        }
    }
}
```

Response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [
            {
                "type": "text",
                "text": "{\"markdown\": \"## Learned Values\\n...\", \"token_count\": 150}"
            }
        ]
    }
}
```

### 3.3 Hook JSON Output Format

All hooks output JSON with a `type` field:

```json
// Success
{"type": "session_started", "session_id": "abc-123"}
{"type": "rich", "content": "## Context\\n...", "token_count": 150}
{"type": "reminder", "content": "## GHAP Check-in\\n..."}
{"type": "outcome", "content": "## Test PASSED\\n...", "suggested_action": "resolve_confirmed"}

// Degraded (server unavailable)
{"type": "degraded", "reason": "server_timeout"}
{"type": "degraded", "reason": "request_failed"}

// Special
{"type": "orphan_detected", "content": "## Orphaned GHAP\\n..."}
```

### 3.4 New MCP Tool Signatures

| Tool | Arguments | Returns |
|------|-----------|---------|
| `start_session` | None | `{session_id, started_at}` |
| `get_orphaned_ghap` | None | `{has_orphan, goal?, hypothesis?, ...}` |
| `should_check_in` | `frequency: int = 10` | `{should_check_in: bool}` |
| `increment_tool_count` | None | `{tool_count: int}` |
| `reset_tool_count` | None | `{tool_count: int}` |
| `assemble_context` | `query, context_types?, limit?, max_tokens?` | `{markdown, token_count, ...}` |

---

## 4. Testing Strategy

### 4.1 Unit Tests

**New test file: `tests/server/test_http.py`**

```python
"""Tests for HTTP transport."""

import pytest
from starlette.testclient import TestClient

from clams.server.http import HttpServer


@pytest.fixture
def http_server(mock_server, mock_services):
    """Create HTTP server for testing."""
    return HttpServer(mock_server, mock_services)


@pytest.fixture
def client(http_server):
    """Create test client."""
    app = http_server.create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestMcpEndpoint:
    def test_tool_call(self, client):
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {}}
        })
        assert response.status_code == 200
```

**New test file: `tests/server/test_session_tools.py`**

```python
"""Tests for session management tools."""

import pytest

from clams.server.tools.session import SessionManager, get_session_tools


@pytest.fixture
def session_manager(tmp_path, monkeypatch):
    """Create session manager with temp paths."""
    monkeypatch.setattr("clams.server.tools.session.CLAMS_DIR", tmp_path)
    monkeypatch.setattr("clams.server.tools.session.JOURNAL_DIR", tmp_path / "journal")
    return SessionManager()


class TestStartSession:
    async def test_creates_session_id(self, session_manager):
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()
        assert "session_id" in result
        assert len(result["session_id"]) == 36  # UUID format


class TestShouldCheckIn:
    async def test_returns_false_when_count_low(self, session_manager):
        tools = get_session_tools(session_manager)
        result = await tools["should_check_in"](frequency=10)
        assert result["should_check_in"] is False

    async def test_returns_true_when_count_high(self, session_manager):
        tools = get_session_tools(session_manager)
        for _ in range(10):
            await tools["increment_tool_count"]()
        result = await tools["should_check_in"](frequency=10)
        assert result["should_check_in"] is True
```

### 4.2 Integration Tests

**New test file: `tests/integration/test_hooks.py`**

```python
"""Integration tests for hook scripts with HTTP server."""

import subprocess
import time
import pytest


@pytest.fixture(scope="module")
def running_server(tmp_path_factory):
    """Start server for integration tests."""
    # Start server
    proc = subprocess.Popen([
        "clams-server", "--http", "--port", "6399"
    ])

    # Wait for ready
    for _ in range(30):
        try:
            import httpx
            resp = httpx.get("http://localhost:6399/health", timeout=1)
            if resp.status_code == 200:
                break
        except:
            pass
        time.sleep(1)

    yield "http://localhost:6399"

    proc.terminate()
    proc.wait()


class TestSessionStartHook:
    def test_completes_quickly(self, running_server, tmp_path):
        """Session start should complete in < 100ms."""
        start = time.time()
        result = subprocess.run(
            [".claude/hooks/session_start.sh"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        elapsed = time.time() - start

        assert result.returncode == 0
        assert elapsed < 0.1  # 100ms


class TestUserPromptSubmitHook:
    def test_returns_context(self, running_server):
        """User prompt hook should return context."""
        result = subprocess.run(
            [".claude/hooks/user_prompt_submit.sh"],
            input="How do I fix this bug?",
            capture_output=True,
            text=True,
            timeout=35,  # 30s wait + 5s buffer
        )
        assert result.returncode == 0
        assert "type" in result.stdout
```

### 4.3 Performance Tests

**New test file: `tests/performance/test_hook_timing.py`**

```python
"""Performance tests for hook timing requirements."""

import subprocess
import statistics
import time
import pytest


@pytest.fixture(scope="module")
def warm_server():
    """Ensure server is running and warm."""
    # Server startup tested separately
    for _ in range(30):
        try:
            import httpx
            resp = httpx.get("http://localhost:6334/health", timeout=1)
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    pytest.skip("Server not available")


class TestHookTiming:
    """Verify hooks meet timing requirements."""

    def measure_hook(self, script: str, input_data: str = "") -> float:
        """Measure hook execution time."""
        start = time.perf_counter()
        subprocess.run(
            [script],
            input=input_data,
            capture_output=True,
            timeout=5,
        )
        return time.perf_counter() - start

    def test_session_start_under_100ms(self, warm_server):
        """session_start.sh should complete in < 100ms."""
        times = [
            self.measure_hook(".claude/hooks/session_start.sh")
            for _ in range(5)
        ]
        avg = statistics.mean(times)
        assert avg < 0.1, f"Average {avg:.3f}s exceeds 100ms"

    def test_user_prompt_under_200ms(self, warm_server):
        """user_prompt_submit.sh should complete in < 200ms (warm)."""
        times = [
            self.measure_hook(
                ".claude/hooks/user_prompt_submit.sh",
                "How do I implement this feature?"
            )
            for _ in range(5)
        ]
        avg = statistics.mean(times)
        assert avg < 0.2, f"Average {avg:.3f}s exceeds 200ms"

    def test_ghap_checkin_under_200ms(self, warm_server):
        """ghap_checkin.sh should complete in < 200ms."""
        times = [
            self.measure_hook(".claude/hooks/ghap_checkin.sh")
            for _ in range(5)
        ]
        avg = statistics.mean(times)
        assert avg < 0.2, f"Average {avg:.3f}s exceeds 200ms"
```

### 4.4 Daemon Management Tests

**New test file: `tests/server/test_daemon.py`**

```python
"""Tests for daemon lifecycle management."""

import os
import signal
import subprocess
import time
import pytest


class TestDaemonLifecycle:
    def test_creates_pid_file(self, tmp_path):
        """Daemon should create PID file."""
        pid_file = tmp_path / "server.pid"

        proc = subprocess.Popen([
            "clams-server", "--http", "--port", "6399"
        ], env={**os.environ, "CLAMS_PID_FILE": str(pid_file)})

        time.sleep(2)

        assert pid_file.exists()
        pid = int(pid_file.read_text())
        assert pid == proc.pid

        proc.terminate()
        proc.wait()

    def test_graceful_shutdown(self, tmp_path):
        """SIGTERM should trigger graceful shutdown."""
        pid_file = tmp_path / "server.pid"

        proc = subprocess.Popen([
            "clams-server", "--http", "--port", "6399"
        ], env={**os.environ, "CLAMS_PID_FILE": str(pid_file)})

        # Wait for ready
        time.sleep(5)

        # Send SIGTERM
        proc.send_signal(signal.SIGTERM)

        # Should exit cleanly
        exit_code = proc.wait(timeout=10)
        assert exit_code == 0

        # PID file should be cleaned up
        assert not pid_file.exists()
```

---

## 5. Migration Path

### 5.1 Implementation Order

1. **Phase 1: HTTP Transport Infrastructure**
   - Add `src/clams/server/http.py`
   - Add `--http`, `--port`, `--daemon` CLI arguments
   - Add Starlette and uvicorn dependencies
   - Test HTTP endpoints work

2. **Phase 2: Session Tools**
   - Add `src/clams/server/tools/session.py`
   - Add `src/clams/server/tools/context.py`
   - Register tools in `__init__.py`
   - Unit test all new tools

3. **Phase 3: Hook Script Updates**
   - Update `session_start.sh` (non-blocking)
   - Update `user_prompt_submit.sh` (blocking, HTTP)
   - Update `ghap_checkin.sh` (quick HTTP)
   - Update `outcome_capture.sh` (quick HTTP)
   - Delete `mcp_client.py` (no longer needed)

4. **Phase 4: Install/Uninstall Updates**
   - Add daemon management to `install.sh`
   - Add daemon stop to `uninstall.sh`
   - Update Claude Code config for SSE transport

5. **Phase 5: Testing & Performance Validation**
   - Integration tests with running server
   - Performance tests for timing requirements
   - End-to-end hook workflow tests

### 5.2 Backwards Compatibility

This is a breaking change that requires reinstallation:

1. **Users must run `uninstall.sh`** to remove old stdio config
2. **Users must run `install.sh`** to install HTTP config
3. **No automatic migration** - clean break is simpler

Since this is a greenfield project (per CLAUDE.md), there are no external users to migrate.

### 5.3 Rollback Plan

If issues are discovered:

1. Revert hook scripts to use `mcp_client.py`
2. Revert `~/.claude.json` to stdio transport
3. Stop daemon and remove PID file

---

## 6. Dependencies

### 6.1 New Python Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing ...
    "starlette>=0.27.0",
    "uvicorn[standard]>=0.24.0",
]
```

Note: These may already be transitive dependencies of the MCP SDK (which requires `sse-starlette`).

### 6.2 Runtime Requirements

- Port 6334 must be available
- Server needs write access to `~/.clams/`
- Daemon requires Unix fork() (macOS/Linux only)

---

## 7. Security Considerations

### 7.1 Local-Only Binding

The HTTP server binds to `127.0.0.1` only:
- Not accessible from network
- No authentication needed
- Same security model as stdio

### 7.2 No Secrets in Logs

Server logs should not contain:
- User prompts
- Memory content
- Embedding vectors

### 7.3 PID File Permissions

PID file should be user-readable only:
```bash
chmod 600 ~/.clams/server.pid
```

---

## 8. Appendix: Open Questions Addressed

### Q1: Daemon management approach?

**Decision**: PID file approach (not systemd/launchd)

Rationale:
- Works on all Unix systems
- No root/admin required
- Simple implementation
- Matches spec recommendation

### Q2: Port conflict handling?

**Decision**: Configurable port with clear error

Implementation:
```python
try:
    await server.serve()
except OSError as e:
    if e.errno == errno.EADDRINUSE:
        logger.error("Port 6334 already in use. Use --port to specify different port.")
        sys.exit(1)
```

### Q3: Server crash recovery?

**Decision**: Manual restart for v1

The `session_start.sh` hook will attempt to start the daemon if not running, providing automatic recovery on next session start.
