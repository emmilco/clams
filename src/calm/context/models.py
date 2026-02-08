"""Data models for context assembly."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextItem:
    """A single piece of context from any source."""

    source: str  # "memory", "code", "experience", "value", "commit"
    content: str
    relevance: float
    metadata: dict[str, Any]

    def __hash__(self) -> int:
        return hash((self.source, self.content[:100], len(self.content)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContextItem):
            return False
        return self.source == other.source and self.content == other.content


@dataclass
class FormattedContext:
    """Complete formatted context ready for injection."""

    markdown: str
    items: list[ContextItem]
    token_count: int
    sources_used: dict[str, int]
    budget_exceeded: bool = False
    truncated_items: list[str] = field(default_factory=list)


class ContextAssemblyError(Exception):
    """Base exception for context assembly."""

    pass


class InvalidContextTypeError(ContextAssemblyError):
    """Raised when invalid context type requested."""

    def __init__(self, invalid_type: str, valid_types: list[str]):
        self.invalid_type = invalid_type
        self.valid_types = valid_types
        super().__init__(
            f"Invalid context type '{invalid_type}'. "
            f"Valid types: {', '.join(valid_types)}"
        )
