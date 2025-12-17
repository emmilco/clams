"""HTTP API response schemas for validation.

This module provides Pydantic models for validating HTTP API responses,
enabling both test validation and documentation of the API contract.
"""

from tests.server.schemas.http import (
    ApiDictResponse,
    ApiErrorResponse,
    ApiStringResultResponse,
    HealthResponse,
)

__all__ = [
    "ApiDictResponse",
    "ApiErrorResponse",
    "ApiStringResultResponse",
    "HealthResponse",
]
