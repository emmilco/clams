"""Tests for error types."""

import pytest

from learning_memory_server.server.tools.errors import (
    InsufficientDataError,
    MCPError,
    NotFoundError,
    ValidationError,
)


def test_mcp_error_is_exception() -> None:
    """Test MCPError is an Exception."""
    assert issubclass(MCPError, Exception)
    error = MCPError("test message")
    assert str(error) == "test message"


def test_validation_error_is_mcp_error() -> None:
    """Test ValidationError inherits from MCPError."""
    assert issubclass(ValidationError, MCPError)
    error = ValidationError("invalid input")
    assert str(error) == "invalid input"


def test_not_found_error_is_mcp_error() -> None:
    """Test NotFoundError inherits from MCPError."""
    assert issubclass(NotFoundError, MCPError)
    error = NotFoundError("resource not found")
    assert str(error) == "resource not found"


def test_insufficient_data_error_is_mcp_error() -> None:
    """Test InsufficientDataError inherits from MCPError."""
    assert issubclass(InsufficientDataError, MCPError)
    error = InsufficientDataError("not enough data")
    assert str(error) == "not enough data"


def test_errors_can_be_raised() -> None:
    """Test errors can be raised and caught."""
    with pytest.raises(ValidationError, match="test"):
        raise ValidationError("test")

    with pytest.raises(NotFoundError, match="not found"):
        raise NotFoundError("not found")

    with pytest.raises(InsufficientDataError, match="insufficient"):
        raise InsufficientDataError("insufficient")
