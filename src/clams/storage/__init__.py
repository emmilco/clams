"""Vector storage and retrieval.

Note: StorageSettings has been removed as part of SPEC-029.
All configuration should now be sourced from clams.server.config.ServerSettings.
"""

from .base import CollectionInfo, SearchResult, Vector, VectorStore
from .memory import InMemoryVectorStore
from .metadata import CallGraphEntry, IndexedFile, MetadataStore, ProjectConfig
from .qdrant import QdrantVectorStore

__all__ = [
    "CallGraphEntry",
    "CollectionInfo",
    "IndexedFile",
    "InMemoryVectorStore",
    "MetadataStore",
    "ProjectConfig",
    "QdrantVectorStore",
    "SearchResult",
    "Vector",
    "VectorStore",
]
