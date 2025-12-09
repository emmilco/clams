"""Data models for context assembly."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextItem:
    """A single piece of context from any source."""

    source: str  # "memory", "code", "experience", "value", "commit"
    content: str  # Formatted content for display
    relevance: float  # Similarity score (0.0-1.0)
    metadata: dict[str, Any]  # Source-specific metadata

    def __hash__(self) -> int:
        """Make hashable for set operations (deduplication).

        Uses source, first 100 chars, and content length to reduce collisions
        while maintaining performance. This ensures items with same prefix
        but different lengths have different hashes.
        """
        return hash((self.source, self.content[:100], len(self.content)))

    def __eq__(self, other: object) -> bool:
        """Compare for equality (deduplication)."""
        if not isinstance(other, ContextItem):
            return False
        return self.source == other.source and self.content == other.content


@dataclass
class FormattedContext:
    """Complete formatted context ready for injection."""

    markdown: str  # Formatted markdown text
    items: list[ContextItem]  # Individual items (for inspection)
    token_count: int  # Approximate token count
    sources_used: dict[str, int]  # Count by source type
    budget_exceeded: bool = False  # True if max_tokens was exceeded
    # IDs of items that were truncated
    truncated_items: list[str] = field(default_factory=list)


class ContextAssemblyError(Exception):
    """Base exception for context assembly."""

    pass


class InvalidContextTypeError(ContextAssemblyError):
    """Raised when invalid context type requested."""

    def __init__(self, invalid_type: str, valid_types: list[str]):
        """
        Initialize error with invalid type and valid options.

        Args:
            invalid_type: The invalid context type that was provided
            valid_types: List of valid context type options
        """
        self.invalid_type = invalid_type
        self.valid_types = valid_types
        super().__init__(
            f"Invalid context type '{invalid_type}'. "
            f"Valid types: {', '.join(valid_types)}"
        )
