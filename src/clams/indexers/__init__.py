"""Code parsing and indexing for semantic search."""

from .base import (
    CodeParser,
    IndexingError,
    IndexingStats,
    ParseError,
    SemanticUnit,
    UnitType,
)
from .indexer import CodeIndexer
from .tree_sitter import TreeSitterParser
from .utils import EXTENSION_MAP, compute_file_hash, generate_unit_id

__all__ = [
    "CodeParser",
    "CodeIndexer",
    "TreeSitterParser",
    "SemanticUnit",
    "UnitType",
    "IndexingError",
    "IndexingStats",
    "ParseError",
    "EXTENSION_MAP",
    "generate_unit_id",
    "compute_file_hash",
]
