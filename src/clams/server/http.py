"""HTTP transport for CLAMS MCP server using Starlette + SSE.

This module provides HTTP+SSE transport for the MCP server, enabling:
- Claude Code to connect via SSE at /sse endpoint
- Hook scripts to make HTTP POST requests to /mcp endpoint
- Health checks at /health endpoint

This replaces the stdio transport for production use, allowing multiple
clients (Claude Code + hooks) to share a single server instance.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from types import FrameType

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
    - /mcp: POST endpoint for tool calls (hook scripts)
    """

    def __init__(
        self,
        server: Server,
        services: ServiceContainer,
        host: str = "127.0.0.1",
        port: int = 6334,
    ) -> None:
        """Initialize HTTP server.

        Args:
            server: MCP Server instance with tools registered
            services: Service container for cleanup on shutdown
            host: Host to bind to (default: 127.0.0.1 for security)
            port: Port to bind to (default: 6334)
        """
        self.server = server
        self.services = services
        self.host = host
        self.port = port
        self.sse_transport = SseServerTransport("/mcp")
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

    async def sse_handler(self, request: Request) -> Response:
        """SSE connection handler for Claude Code.

        Establishes a long-lived SSE connection for bidirectional
        communication with the MCP client.
        """
        logger.info("http.sse_connection_started")
        async with self.sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )
        logger.info("http.sse_connection_closed")
        return Response()

    async def message_handler(self, request: Request) -> Response:
        """Message handler for hook scripts (POST /mcp).

        Receives JSON-RPC messages from hook scripts and routes
        them to the appropriate SSE session.
        """
        await self.sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )
        return Response()

    def create_app(self) -> Starlette:
        """Create the Starlette application with routes and middleware."""
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
    """Fork into a background daemon process.

    Uses double-fork technique to properly daemonize:
    1. First fork separates from parent
    2. setsid() creates new session
    3. Second fork prevents reacquiring terminal
    4. Redirect stdio to log file
    """
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
    log_file = get_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    # Truncate log file on restart (simple log rotation for v1)
    with open(log_file, "w") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())

    logger.info("http.daemonized", pid=os.getpid())


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
