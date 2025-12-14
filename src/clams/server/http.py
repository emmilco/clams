"""HTTP transport for CLAMS MCP server using Starlette + SSE.

This module provides HTTP+SSE transport for the MCP server, enabling:
- Claude Code to connect via SSE at /sse endpoint
- Hook scripts to make HTTP POST requests to /api/call endpoint
- Health checks at /health endpoint

This replaces the stdio transport for production use, allowing multiple
clients (Claude Code + hooks) to share a single server instance.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import FrameType
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from clams.server.tools import ServiceContainer

logger = structlog.get_logger()

# Default paths for daemon management
DEFAULT_PID_FILE = Path.home() / ".clams" / "server.pid"
DEFAULT_LOG_FILE = Path.home() / ".clams" / "server.log"


def get_pid_file() -> Path:
    """Get PID file path from environment or default."""
    env_path = os.environ.get("CLAMS_PID_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_PID_FILE


def get_log_file() -> Path:
    """Get log file path from environment or default."""
    env_path = os.environ.get("CLAMS_LOG_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_LOG_FILE


class HttpServer:
    """HTTP server wrapper for the MCP server.

    Provides:
    - /health: GET endpoint for health checks
    - /sse: GET endpoint for SSE connections (Claude Code)
    - /api/call: POST endpoint for direct tool calls (hook scripts)
    """

    def __init__(
        self,
        server: Server,
        services: ServiceContainer,
        tool_registry: dict[str, Callable[..., Coroutine[Any, Any, Any]]],
        host: str = "127.0.0.1",
        port: int = 6335,
    ) -> None:
        """Initialize HTTP server.

        Args:
            server: MCP Server instance with tools registered
            services: Service container for cleanup on shutdown
            tool_registry: Dictionary mapping tool names to async functions
            host: Host to bind to (default: 127.0.0.1 for security)
            port: Port to bind to (default: 6335)
        """
        self.server = server
        self.services = services
        self.tool_registry = tool_registry
        self.host = host
        self.port = port
        self.sse_transport = SseServerTransport("/sse")
        self._shutdown_event: asyncio.Event | None = None

    async def health_handler(self, request: Request) -> JSONResponse:
        """Health check endpoint.

        Returns server status and version information.
        """
        return JSONResponse({
            "status": "healthy",
            "server": "clams",
            "version": "0.1.0",
        })

    def sse_asgi_app(self) -> Any:
        """Return ASGI app that handles both GET (SSE) and POST (messages).

        GET requests establish SSE connections for server-to-client events.
        POST requests deliver client messages to an established session.
        """
        async def app(scope: Any, receive: Any, send: Any) -> None:
            method = scope.get("method", "GET")

            if method == "GET":
                logger.info("http.sse_connection_started")
                request = Request(scope, receive, send)
                async with self.sse_transport.connect_sse(
                    scope, receive, request._send
                ) as (read_stream, write_stream):
                    await self.server.run(
                        read_stream,
                        write_stream,
                        self.server.create_initialization_options(),
                    )
                logger.info("http.sse_connection_closed")
            elif method == "POST":
                logger.info("http.sse_post_received")
                await self.sse_transport.handle_post_message(scope, receive, send)
            else:
                response = Response("Method not allowed", status_code=405)
                await response(scope, receive, send)

        return app

    async def api_call_handler(self, request: Request) -> JSONResponse:
        """Direct tool call endpoint for hook scripts (POST /api/call).

        This endpoint bypasses the SSE transport and directly invokes
        tools from the registry. It's designed for hook scripts that
        make standalone HTTP requests without establishing an SSE session.

        Request format:
        {
            "method": "tools/call",
            "params": {
                "name": "tool_name",
                "arguments": {...}
            }
        }

        Response format:
        {
            "result": {...}  # Tool result
        }
        or
        {
            "error": "error message"
        }
        """
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            logger.warning("api.invalid_json", error=str(e))
            return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

        # Extract tool name and arguments
        params = body.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return JSONResponse(
                {"error": "Missing tool name in params.name"},
                status_code=400,
            )

        if tool_name not in self.tool_registry:
            logger.warning("api.unknown_tool", tool=tool_name)
            return JSONResponse(
                {"error": f"Unknown tool: {tool_name}"},
                status_code=404,
            )

        logger.debug("api.tool_call", tool=tool_name, arguments=arguments)

        try:
            tool_func = self.tool_registry[tool_name]
            result = await tool_func(**arguments)

            # Format result as JSON
            if isinstance(result, (dict, list)):
                return JSONResponse(result)
            elif isinstance(result, str):
                return JSONResponse({"result": result})
            else:
                return JSONResponse({"result": str(result)})

        except TypeError as e:
            # Invalid arguments
            logger.warning("api.invalid_arguments", tool=tool_name, error=str(e))
            return JSONResponse(
                {"error": f"Invalid arguments for {tool_name}: {e}"},
                status_code=400,
            )
        except Exception as e:
            logger.error("api.tool_error", tool=tool_name, error=str(e), exc_info=True)
            return JSONResponse(
                {"error": f"Tool error: {e}"},
                status_code=500,
            )

    def create_app(self) -> Any:
        """Create the ASGI application with routes and middleware.

        Returns a wrapper ASGI app that handles /sse directly (to avoid
        Starlette's trailing slash redirect) and delegates other routes
        to Starlette.
        """
        routes = [
            Route("/health", self.health_handler, methods=["GET"]),
            Route("/api/call", self.api_call_handler, methods=["POST"]),
        ]

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            )
        ]

        starlette_app = Starlette(routes=routes, middleware=middleware)
        sse_app = self.sse_asgi_app()

        # Wrap to intercept /sse requests before Starlette
        async def app(scope: Any, receive: Any, send: Any) -> None:
            path = scope.get("path", "")
            if path == "/sse" or path.startswith("/sse?"):
                await sse_app(scope, receive, send)
            else:
                await starlette_app(scope, receive, send)

        return app

    async def run(self) -> None:
        """Run the HTTP server.

        Writes PID file on startup and cleans up on shutdown.
        Handles SIGTERM/SIGINT for graceful shutdown.
        """
        import uvicorn

        self._shutdown_event = asyncio.Event()
        app = self.create_app()

        # Write PID file
        pid_file = get_pid_file()
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        # Set restrictive permissions (user read/write only)
        os.chmod(pid_file, 0o600)
        logger.info("http.pid_file_written", path=str(pid_file), pid=os.getpid())

        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",  # Reduce uvicorn noise
        )
        server = uvicorn.Server(config)

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()

        def handle_shutdown(signum: int, frame: FrameType | None) -> None:
            logger.info("http.shutdown_requested", signal=signum)
            if self._shutdown_event:
                loop.call_soon_threadsafe(self._shutdown_event.set)

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

        logger.info(
            "http.server_starting",
            host=self.host,
            port=self.port,
        )

        try:
            # Run server until shutdown signal
            await server.serve()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Clean up resources on shutdown.

        Closes services and removes PID file.
        """
        logger.info("http.shutting_down")

        # Close services
        try:
            await self.services.close()
            logger.info("http.services_closed")
        except Exception as e:
            logger.error("http.services_close_failed", error=str(e))

        # Remove PID file
        pid_file = get_pid_file()
        if pid_file.exists():
            try:
                pid_file.unlink()
                logger.info("http.pid_file_removed")
            except Exception as e:
                logger.warning("http.pid_file_remove_failed", error=str(e))

        logger.info("http.shutdown_complete")


def daemonize() -> None:
    """Spawn a daemon process using subprocess instead of fork.

    This avoids macOS MPS fork safety issues by using subprocess.Popen
    which creates a completely fresh Python process. The parent process
    exits immediately, leaving the child running as a daemon.

    The child process runs with:
    - stdin connected to /dev/null
    - stdout/stderr redirected to log file
    - New session (detached from terminal)
    - Working directory unchanged
    """
    log_file = get_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build command to run the server in HTTP mode (not daemon mode to avoid recursion)
    # We use --http since we're already daemonizing via subprocess
    cmd = [
        sys.executable,
        "-m", "clams.server.main",
        "--http",
    ]

    # Open log file for output
    with open(log_file, "w") as log_out:
        with open("/dev/null") as devnull:
            # Start subprocess detached from this process
            proc = subprocess.Popen(
                cmd,
                stdin=devnull,
                stdout=log_out,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Creates new session (like setsid)
                # Don't close file descriptors - let child inherit log file
            )

    # Write child PID to file so it can be tracked
    pid_file = get_pid_file()
    pid_file.write_text(str(proc.pid))

    # Log daemonization (to stderr since log_file now belongs to child)
    print(f"Daemon started with PID {proc.pid}", file=sys.stderr)

    # Parent exits, child continues running
    sys.exit(0)


def is_server_running() -> bool:
    """Check if the server is already running.

    Returns:
        True if PID file exists and process is running
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is running (signal 0 doesn't kill, just checks)
        os.kill(pid, 0)
        return True
    except (ValueError, OSError, ProcessLookupError):
        # Invalid PID or process not running
        return False


def stop_server() -> bool:
    """Stop the running server.

    Returns:
        True if server was stopped, False if not running
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        # Wait for process to exit (up to 5 seconds)
        for _ in range(50):
            try:
                os.kill(pid, 0)
                import time
                time.sleep(0.1)
            except (OSError, ProcessLookupError):
                # Process exited
                break
        # Force kill if still running
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        # Clean up PID file if server didn't
        if pid_file.exists():
            pid_file.unlink()
        return True
    except (ValueError, OSError, ProcessLookupError):
        # Invalid PID or process not running
        if pid_file.exists():
            pid_file.unlink()
        return False
