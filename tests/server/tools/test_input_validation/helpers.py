"""Helper functions for input validation tests.

These helpers handle the dual error handling pattern used by MCP tools:
some tools raise ValidationError exceptions, while others return
error response dictionaries.
"""

from typing import Any

from calm.tools.validation import ValidationError


async def assert_validation_error_async(
    coro: Any,
    field_name: str | None = None,
    valid_options: list[str] | None = None,
    message_contains: str | None = None,
) -> dict[str, Any]:
    """Assert that the coroutine raises or returns a validation error.

    Args:
        coro: Coroutine to execute
        field_name: Field name that should appear in error message
        valid_options: Valid enum options that should appear in error message
        message_contains: Substring that should appear in error message

    Returns:
        The error dict if returned (for further assertions)

    Raises:
        AssertionError: If no validation error is raised or returned
    """
    try:
        result = await coro
        # If we get here, it returned a result instead of raising
        assert "error" in result, f"Expected error in result: {result}"
        assert result["error"]["type"] == "validation_error", (
            f"Expected validation_error, got {result['error']['type']}"
        )
        error_msg = result["error"]["message"]
        if field_name:
            assert field_name.lower() in error_msg.lower(), (
                f"Expected '{field_name}' in error message: {error_msg}"
            )
        if valid_options:
            for opt in valid_options:
                assert opt in error_msg, (
                    f"Expected '{opt}' in error message: {error_msg}"
                )
        if message_contains:
            assert message_contains.lower() in error_msg.lower(), (
                f"Expected '{message_contains}' in error message: {error_msg}"
            )
        return result
    except ValidationError as e:
        error_msg = str(e)
        if field_name:
            assert field_name.lower() in error_msg.lower(), (
                f"Expected '{field_name}' in error message: {error_msg}"
            )
        if valid_options:
            for opt in valid_options:
                assert opt in error_msg, (
                    f"Expected '{opt}' in error message: {error_msg}"
                )
        if message_contains:
            assert message_contains.lower() in error_msg.lower(), (
                f"Expected '{message_contains}' in error message: {error_msg}"
            )
        return {"error": {"type": "validation_error", "message": error_msg}}


def assert_error_response(
    result: dict[str, Any],
    error_type: str = "validation_error",
    field_name: str | None = None,
    message_contains: str | None = None,
) -> None:
    """Assert that a result dict contains an error response.

    Args:
        result: Result dict from tool call
        error_type: Expected error type (default validation_error)
        field_name: Field name that should appear in error message
        message_contains: Substring that should appear in error message
    """
    assert "error" in result, f"Expected error in result: {result}"
    assert result["error"]["type"] == error_type, (
        f"Expected {error_type}, got {result['error']['type']}"
    )
    error_msg = result["error"]["message"]
    if field_name:
        assert field_name.lower() in error_msg.lower(), (
            f"Expected '{field_name}' in error message: {error_msg}"
        )
    if message_contains:
        assert message_contains.lower() in error_msg.lower(), (
            f"Expected '{message_contains}' in error message: {error_msg}"
        )
