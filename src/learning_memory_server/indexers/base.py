"""Base types and interfaces for code parsing and indexing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class UnitType(Enum):
    """Type of semantic unit extracted from code."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    CONSTANT = "constant"  # Module-level named constants


@dataclass
class SemanticUnit:
    """A semantic unit extracted from source code."""

    name: str
    qualified_name: str  # e.g., "module.ClassName.method_name"
    unit_type: UnitType
    signature: str  # e.g., "def foo(x: int) -> bool"
    content: str  # Full source code
    file_path: str
    start_line: int
    end_line: int
    language: str
    docstring: str | None = None
    complexity: int | None = None  # Cyclomatic complexity


@dataclass
class IndexingError:
    """Error encountered during indexing."""

    file_path: str
    error_type: str  # parse_error, encoding_error, io_error, embedding_error
    message: str


@dataclass
class IndexingStats:
    """Statistics from an indexing operation."""

    files_indexed: int
    units_indexed: int
    files_skipped: int
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0


class ParseError(Exception):
    """Exception raised during code parsing."""

    def __init__(self, error_type: str, message: str, file_path: str = "") -> None:
        self.error_type = error_type  # parse_error, encoding_error, io_error
        self.message = message
        self.file_path = file_path
        super().__init__(f"{error_type}: {message}")


class CodeParser(ABC):
    """Abstract interface for parsing code into semantic units."""

    @abstractmethod
    async def parse_file(self, path: str) -> list[SemanticUnit]:
        """Parse a file and extract semantic units.

        Must use run_in_executor for CPU-bound tree-sitter parsing.

        Raises:
            ParseError: If file cannot be parsed (encoding, IO, or syntax error)
        """
        pass

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of supported language identifiers."""
        pass

    @abstractmethod
    def detect_language(self, path: str) -> str | None:
        """Detect language from file extension."""
        pass
