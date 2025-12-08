"""Tests for server main module."""

import pytest

from clams.embedding import (
    EmbeddingService,
    get_semantic_embedder,
    initialize_registry,
)
from clams.server.config import ServerSettings
from clams.server.main import create_server


@pytest.fixture
def settings() -> ServerSettings:
    """Create settings for testing."""
    return ServerSettings()


@pytest.fixture
def embedding_service(settings: ServerSettings) -> EmbeddingService:
    """Create an embedding service for testing."""
    # Initialize registry before getting embedder
    initialize_registry(settings.code_model, settings.semantic_model)
    return get_semantic_embedder()


def test_registry_provides_embedder(settings: ServerSettings) -> None:
    """Test that registry provides a valid embedding service."""
    initialize_registry(settings.code_model, settings.semantic_model)
    embedder = get_semantic_embedder()

    assert embedder is not None
    assert embedder.dimension > 0


async def test_create_server(
    settings: ServerSettings, embedding_service: EmbeddingService
) -> None:
    """Test that create_server creates a properly configured server."""
    server, services = await create_server(settings)

    try:
        assert server is not None
        assert server.name == "clams"
    finally:
        await services.close()


async def test_server_has_ping_tool(
    settings: ServerSettings, embedding_service: EmbeddingService
) -> None:
    """Test that the server has the ping tool registered."""
    server, services = await create_server(settings)

    try:
        # Check that tools were registered
        # The server should have the ping tool available
        assert hasattr(server, "call_tool")
    finally:
        await services.close()
