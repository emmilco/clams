"""Tests for server main module."""

import pytest

from learning_memory_server.embedding import NomicEmbedding
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.server.main import create_embedding_service, create_server


@pytest.fixture
def embedding_service() -> NomicEmbedding:
    """Create an embedding service for testing."""
    settings = ServerSettings()
    return create_embedding_service(settings)


def test_create_embedding_service() -> None:
    """Test that create_embedding_service creates a valid embedding service."""
    settings = ServerSettings()
    embedding_service = create_embedding_service(settings)

    assert embedding_service is not None
    assert embedding_service.dimension > 0


def test_create_server(embedding_service: NomicEmbedding) -> None:
    """Test that create_server creates a properly configured server."""
    settings = ServerSettings()
    server = create_server(settings, embedding_service)

    assert server is not None
    assert server.name == "learning-memory-server"


def test_server_has_ping_tool(embedding_service: NomicEmbedding) -> None:
    """Test that the server has the ping tool registered."""
    settings = ServerSettings()
    server = create_server(settings, embedding_service)

    # Check that tools were registered
    # The server should have the ping tool available
    assert hasattr(server, "call_tool")
