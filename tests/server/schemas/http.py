"""HTTP API response schemas for validation.

These Pydantic models define the expected structure of HTTP API responses,
enabling both test validation and documentation of the API contract.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class HealthResponse(BaseModel):
    """Schema for GET /health response.

    The health endpoint always returns these three fields when the server
    is responding. The version follows semantic versioning format.
    """

    status: Literal["healthy"]
    server: Literal["clams"]
    version: str

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        """Validate version is semver-like (x.y.z format)."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError(f"Version must be semver format (x.y.z), got: {v}")
        for part in parts:
            if not part.isdigit():
                raise ValueError(f"Version parts must be numeric, got: {v}")
        return v


class ApiErrorResponse(BaseModel):
    """Schema for error responses from POST /api/call.

    All error responses use this consistent format with a single "error"
    field containing a human-readable error message.
    """

    error: str


class ApiStringResultResponse(BaseModel):
    """Schema for string results wrapped in {"result": str}.

    When a tool returns a string, it gets wrapped in this format.
    """

    result: str


class ApiDictResponse(BaseModel):
    """Schema for dict results passed through directly.

    Dict results are returned as-is without wrapping.
    Allows extra fields since the dict content is tool-specific.
    """

    model_config = ConfigDict(extra="allow")


# Type alias for all valid success response types
ApiSuccessResponse = ApiDictResponse | ApiStringResultResponse | list
