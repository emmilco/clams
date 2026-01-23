"""Type validation decorators for function parameters.

These decorators enforce contracts at function boundaries, providing
clear error messages when inputs don't meet requirements. They are
designed to work with both sync and async functions.
"""

import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from clams.utils.datetime import is_valid_datetime_format

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["validate_datetime_params", "validate_numeric_range"]


def validate_datetime_params(
    *param_names: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate datetime string parameters are ISO 8601 format.

    Validates that specified parameters (when not None) are valid ISO 8601
    datetime strings that can be parsed by deserialize_datetime().

    Args:
        *param_names: Names of parameters to validate

    Returns:
        Decorator function

    Raises:
        ValueError: If a specified parameter is not valid ISO 8601 format

    Usage:
        @validate_datetime_params("since", "until")
        def query_events(since: str | None = None, until: str | None = None):
            ...

        @validate_datetime_params("timestamp")
        async def log_event(timestamp: str):
            ...

    Error message format:
        "Parameter 'since' must be ISO 8601 format
        (e.g., '2024-12-15T10:30:00+00:00'), got: 'invalid'"
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        sig = inspect.signature(func)

        def validate_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            """Validate datetime parameters from args/kwargs."""
            # Build a mapping of param_name -> value
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            for param_name in param_names:
                if param_name not in bound.arguments:
                    continue
                value = bound.arguments[param_name]
                if value is None:
                    continue  # None is allowed for optional params
                if not isinstance(value, str):
                    raise ValueError(
                        f"Parameter '{param_name}' must be a string, "
                        f"got {type(value).__name__}"
                    )
                if not is_valid_datetime_format(value):
                    raise ValueError(
                        f"Parameter '{param_name}' must be ISO 8601 format "
                        f"(e.g., '2024-12-15T10:30:00+00:00'), got: '{value}'"
                    )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(
                *args: P.args, **kwargs: P.kwargs
            ) -> R:
                validate_args(args, kwargs)
                result: R = await func(*args, **kwargs)
                return result

            # Mypy cannot match Coroutine return with R for async wrappers
            return async_wrapper  # type: ignore[return-value]
        else:

            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def validate_numeric_range(
    param_name: str, min_val: float, max_val: float
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to validate numeric parameter is in range.

    Validates that the specified parameter (when not None) is within
    the given range [min_val, max_val] inclusive.

    Args:
        param_name: Name of parameter to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        Decorator function

    Raises:
        ValueError: If parameter is outside the valid range

    Usage:
        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0):
            ...

        @validate_numeric_range("limit", 1, 100)
        async def fetch_items(limit: int = 10):
            ...

    Error message format:
        "Parameter 'timeout' must be in range [0.1, 300.0], got: 500.0"
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        sig = inspect.signature(func)

        def validate_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            """Validate numeric parameter from args/kwargs."""
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            if param_name not in bound.arguments:
                return
            value = bound.arguments[param_name]
            if value is None:
                return  # None is allowed for optional params
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Parameter '{param_name}' must be numeric, "
                    f"got {type(value).__name__}"
                )
            if not (min_val <= value <= max_val):
                raise ValueError(
                    f"Parameter '{param_name}' must be in range "
                    f"[{min_val}, {max_val}], got: {value}"
                )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(
                *args: P.args, **kwargs: P.kwargs
            ) -> R:
                validate_args(args, kwargs)
                result: R = await func(*args, **kwargs)
                return result

            # Mypy cannot match Coroutine return with R for async wrappers
            return async_wrapper  # type: ignore[return-value]
        else:

            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                validate_args(args, kwargs)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
