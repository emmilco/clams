"""CALM server main entry point.

This module is the entry point for the CALM MCP server when run as a daemon.
It's invoked via `python -m calm.server.main`.

Fork/Daemon Constraint
======================

This server may run as a daemon which uses subprocess spawning.
To avoid MPS (macOS GPU) issues, heavy imports (PyTorch, embedding models)
should be deferred until after the server starts.

See calm/server/main.py for detailed documentation on this constraint.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
from collections.abc import AsyncIterator
from pathlib import Path
from types import FrameType
from typing import Any


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CALM MCP Server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6335,
        help="HTTP server port (default: 6335)",
    )
    return parser.parse_args()


def run_server(host: str, port: int) -> None:
    """Run the CALM server.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    asyncio.run(_run_server_async(host, port))


async def _run_server_async(host: str, port: int) -> None:
    """Run the server asynchronously."""
    import structlog
    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from calm import __version__
    from calm.config import settings
    from calm.server.app import create_server

    logger = structlog.get_logger()

    logger.info("calm.starting", version=__version__, host=host, port=port)

    # Create MCP server
    mcp_server, _tool_registry = await create_server()

    # Create Streamable HTTP session manager.
    # The session manager handles session creation, tracking, and
    # reconnection via Mcp-Session-Id headers automatically.
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
    )

    # Health endpoint
    async def health_handler(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "server": "calm",
            "version": __version__,
        })

    # MCP endpoint handler (ASGI app) -- delegates to session manager
    async def mcp_handler(scope: Any, receive: Any, send: Any) -> None:
        await session_manager.handle_request(scope, receive, send)

    # Lifespan context manager for the Starlette app
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("calm.session_manager_started")
            yield
        logger.info("calm.session_manager_stopped")

    # Create Starlette app with routes
    routes = [
        Route("/health", health_handler, methods=["GET"]),
        Mount("/mcp", app=mcp_handler),
    ]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )
    ]

    starlette_app = Starlette(
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    # Write PID file
    pid_file = Path(settings.pid_file).expanduser()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    os.chmod(pid_file, 0o600)
    logger.info("calm.pid_file_written", path=str(pid_file), pid=os.getpid())

    # Configure uvicorn
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Setup signal handlers
    shutdown_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def handle_shutdown(signum: int, frame: FrameType | None) -> None:
        logger.info("calm.shutdown_requested", signal=signum)
        loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info("calm.server_ready", host=host, port=port)

    try:
        await server.serve()
    finally:
        # Clean up PID file
        if pid_file.exists():
            try:
                pid_file.unlink()
                logger.info("calm.pid_file_removed")
            except Exception as e:
                logger.warning("calm.pid_file_remove_failed", error=str(e))

        logger.info("calm.shutdown_complete")


def main() -> None:
    """Entry point when run as a module."""
    args = parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
