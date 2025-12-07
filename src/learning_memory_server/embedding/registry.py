"""Embedding service registry for dual embedding models."""

from typing import Any

import structlog

from .base import EmbeddingService, EmbeddingSettings
from .minilm import MiniLMEmbedding
from .nomic import NomicEmbedding

logger = structlog.get_logger()


class EmbeddingRegistry:
    """Singleton registry for dual embedding models.

    Provides lazy-loaded embedders by purpose:
    - Code embedder: Fast model (configurable) for code indexing/search
    - Semantic embedder: Quality model (configurable) for memories/GHAP/clustering

    Models are loaded on first use and cached for the server's lifetime.
    Thread safety is not required since the MCP server is single-threaded asyncio.
    Model names and dimensions determined by settings.
    """

    def __init__(self, code_model: str, semantic_model: str) -> None:
        """Initialize the registry with model names.

        Args:
            code_model: Model name for code embeddings
            semantic_model: Model name for semantic embeddings
        """
        self._code_embedder: EmbeddingService | None = None
        self._semantic_embedder: EmbeddingService | None = None
        self._code_model = code_model
        self._semantic_model = semantic_model

    def get_code_embedder(self) -> EmbeddingService:
        """Get or create the code embedder.

        Returns:
            EmbeddingService: Code embedder instance (MiniLM by default)
        """
        if self._code_embedder is None:
            embedding_settings = EmbeddingSettings(model_name=self._code_model)
            self._code_embedder = MiniLMEmbedding(settings=embedding_settings)
            logger.info(
                "code_embedder.loaded",
                model=self._code_model,
                dimension=self._code_embedder.dimension,
            )
        return self._code_embedder

    def get_semantic_embedder(self) -> EmbeddingService:
        """Get or create the semantic embedder.

        Returns:
            EmbeddingService: Semantic embedder instance (Nomic by default)
        """
        if self._semantic_embedder is None:
            embedding_settings = EmbeddingSettings(
                model_name=self._semantic_model
            )
            self._semantic_embedder = NomicEmbedding(settings=embedding_settings)
            logger.info(
                "semantic_embedder.loaded",
                model=self._semantic_model,
                dimension=self._semantic_embedder.dimension,
            )
        return self._semantic_embedder


# Module-level singleton (initialized in main.py)
_registry: EmbeddingRegistry | None = None


def initialize_registry(code_model: str, semantic_model: str) -> None:
    """Initialize the global registry with model names.

    Must be called from main.py before any tool uses embedders.

    Args:
        code_model: Model name for code embeddings
        semantic_model: Model name for semantic embeddings
    """
    global _registry
    _registry = EmbeddingRegistry(code_model, semantic_model)


def get_code_embedder() -> EmbeddingService:
    """Get the code embedder from the global registry.

    Returns:
        EmbeddingService: Code embedder instance

    Raises:
        RuntimeError: If registry not initialized
    """
    if _registry is None:
        raise RuntimeError("Registry not initialized. Call initialize_registry() first.")
    return _registry.get_code_embedder()


def get_semantic_embedder() -> EmbeddingService:
    """Get the semantic embedder from the global registry.

    Returns:
        EmbeddingService: Semantic embedder instance

    Raises:
        RuntimeError: If registry not initialized
    """
    if _registry is None:
        raise RuntimeError("Registry not initialized. Call initialize_registry() first.")
    return _registry.get_semantic_embedder()
