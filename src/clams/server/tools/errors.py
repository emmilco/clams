"""Custom error types for MCP tools."""


class MCPError(Exception):
    """Base error for MCP tool failures."""

    pass


class ValidationError(MCPError):
    """Input validation failed."""

    pass


class NotFoundError(MCPError):
    """Resource not found."""

    pass


class InsufficientDataError(MCPError):
    """Not enough data for operation."""

    pass
