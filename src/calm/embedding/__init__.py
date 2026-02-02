"""Embedding services for CALM."""

from .base import EmbeddingModelError, EmbeddingService, Vector
from .minilm import MiniLMEmbedding
from .mock import MockEmbeddingService
from .nomic import NomicEmbedding
from .registry import get_code_embedder, get_semantic_embedder

__all__ = [
    "EmbeddingService",
    "EmbeddingModelError",
    "Vector",
    "NomicEmbedding",
    "MiniLMEmbedding",
    "MockEmbeddingService",
    "get_semantic_embedder",
    "get_code_embedder",
]
