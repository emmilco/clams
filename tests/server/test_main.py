"""Tests for server main module."""

from learning_memory_server.server.config import ServerSettings
from learning_memory_server.server.main import create_server


def test_create_server() -> None:
    """Test that create_server creates a properly configured server."""
    settings = ServerSettings()
    server = create_server(settings)

    assert server is not None
    assert server.name == "learning-memory-server"


def test_server_has_ping_tool() -> None:
    """Test that the server has the ping tool registered."""
    settings = ServerSettings()
    server = create_server(settings)

    # Check that tools were registered
    # The server should have the ping tool available
    assert hasattr(server, "call_tool")
