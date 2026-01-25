"""Embedding generation and management.

Fork Safety Note
----------------

This module does NOT import heavy dependencies (torch, sentence_transformers)
at the top level. All embedding implementations use lazy imports to avoid:

1. Fork safety issues with MPS backend (BUG-042)
2. Slow import times causing hook timeouts (BUG-037)

See ``src/clams/server/main.py`` docstring for the full constraint documentation.

Usage
-----

To get embedders, use the registry functions::

    from clams.embedding import (
        initialize_registry, get_code_embedder, get_semantic_embedder
    )

    initialize_registry(code_model, semantic_model)
    embedder = get_code_embedder()  # Loads model lazily

For direct class access (will load PyTorch immediately)::

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
