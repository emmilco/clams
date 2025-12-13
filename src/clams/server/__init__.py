"""MCP server implementation.

IMPORTANT: This module avoids importing from main.py at module level to prevent
PyTorch imports before daemonization. Use explicit imports when needed:

    from clams.server.main import main, create_server
    from clams.server.config import ServerSettings
"""

from clams.server.config import ServerSettings
from clams.server.logging import configure_logging

__all__ = [
    "ServerSettings",
    "configure_logging",
]
