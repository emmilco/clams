"""Common error types for MCP tools."""


class MCPError(Exception):
    """Base error for MCP tool failures."""

    pass


class ValidationError(MCPError):
    """Input validation failed."""

    pass


class StorageError(MCPError):
    """Storage operation failed."""

    pass


class EmbeddingError(MCPError):
    """Embedding generation failed."""

    pass


class GitError(MCPError):
    """Git operation failed."""

    pass
