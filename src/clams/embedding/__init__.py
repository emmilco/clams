"""Embedding generation and management."""

from .base import (
    EmbeddingModelError,
    EmbeddingService,
    EmbeddingSettings,
    Vector,
)
from .minilm import MiniLMEmbedding
from .mock import MockEmbedding
from .nomic import NomicEmbedding
from .registry import (
    EmbeddingRegistry,
    get_code_embedder,
    get_semantic_embedder,
    initialize_registry,
)

__all__ = [
    "EmbeddingModelError",
    "EmbeddingRegistry",
    "EmbeddingService",
    "EmbeddingSettings",
    "MiniLMEmbedding",
    "MockEmbedding",
    "NomicEmbedding",
    "Vector",
    "get_code_embedder",
    "get_semantic_embedder",
    "initialize_registry",
]
