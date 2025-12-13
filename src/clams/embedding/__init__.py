"""Embedding generation and management.

IMPORTANT: This module avoids importing concrete embedding implementations
(MiniLM, Nomic) at module level to prevent loading PyTorch before daemonization.

To get embedders, use the registry functions:
    from clams.embedding import initialize_registry, get_code_embedder, get_semantic_embedder

    initialize_registry(code_model, semantic_model)
    embedder = get_code_embedder()  # Loads model lazily

For direct class access (will load PyTorch):
    from clams.embedding.minilm import MiniLMEmbedding
    from clams.embedding.nomic import NomicEmbedding
"""

from .base import (
    EmbeddingModelError,
    EmbeddingService,
    EmbeddingSettings,
    Vector,
)
from .registry import (
    EmbeddingRegistry,
    get_code_embedder,
    get_semantic_embedder,
    initialize_registry,
)

# Note: MiniLMEmbedding, NomicEmbedding, MockEmbedding are NOT imported here
# to avoid loading PyTorch at module level. Import them directly if needed:
#   from clams.embedding.minilm import MiniLMEmbedding
#   from clams.embedding.nomic import NomicEmbedding
#   from clams.embedding.mock import MockEmbedding

__all__ = [
    "EmbeddingModelError",
    "EmbeddingRegistry",
    "EmbeddingService",
    "EmbeddingSettings",
    "Vector",
    "get_code_embedder",
    "get_semantic_embedder",
    "initialize_registry",
]
