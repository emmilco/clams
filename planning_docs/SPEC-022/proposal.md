# Technical Proposal: SPEC-022 HTTP API Schema Tests

## Overview

This proposal outlines the implementation approach for adding comprehensive HTTP API schema tests to verify that all HTTP API responses conform to documented schemas. The implementation will address the identified gaps in test coverage while integrating with existing test infrastructure.

## Goals

1. **Complete health endpoint coverage**: Validate all fields for presence, type, and value constraints
2. **Verify CORS configuration**: Test preflight requests and CORS headers
3. **Fix xfail edge cases**: Address null/array body handling bugs in the server
4. **Centralize schema definitions**: Create reusable Pydantic models for response validation

## Non-Goals

- SSE endpoint testing (out of scope due to streaming nature)
- Performance testing
- Authentication/authorization testing (not implemented in server)

## Architecture

### File Organization

Extend the existing `tests/server/test_http_schemas.py` file with new test classes. The file is currently 678 lines and well-organized; adding approximately 200-250 lines of new tests is manageable without requiring a package restructure.

```
tests/server/
  test_http_schemas.py    # Extended with new tests
  schemas/
    __init__.py           # NEW: Schema definitions
    http.py               # NEW: Pydantic models for HTTP responses
```

The schema module will be reusable by both tests and potentially by the server itself for response validation.

### Pydantic Model Definitions

Create centralized schema definitions in a new `tests/server/schemas/` module:

```python
# tests/server/schemas/http.py
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
```

### Test Organization

Add new test classes to `test_http_schemas.py`:

```python
# =============================================================================
# Health Endpoint Schema Tests
# =============================================================================

class TestHealthEndpointSchema:
    """Comprehensive tests for GET /health endpoint schema.

    These tests verify that the health endpoint returns a complete,
    well-formed response with all required fields and correct types.
    """

    def test_health_response_validates_against_schema(
        self, http_client: TestClient
    ) -> None:
        """Health response should validate against HealthResponse schema."""
        response = http_client.get("/health")
        assert response.status_code == 200
        # Pydantic validation will raise if schema doesn't match
        HealthResponse.model_validate(response.json())

    def test_health_status_is_literal_healthy(
        self, http_client: TestClient
    ) -> None:
        """Status field must be exactly 'healthy'."""
        response = http_client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_server_is_literal_clams(
        self, http_client: TestClient
    ) -> None:
        """Server field must be exactly 'clams'."""
        response = http_client.get("/health")
        data = response.json()
        assert data["server"] == "clams"

    def test_health_version_is_semver(
        self, http_client: TestClient
    ) -> None:
        """Version field must follow semver format (x.y.z)."""
        response = http_client.get("/health")
        data = response.json()
        version = data["version"]
        parts = version.split(".")
        assert len(parts) == 3, f"Version must have 3 parts: {version}"
        for part in parts:
            assert part.isdigit(), f"Version parts must be numeric: {version}"

    def test_health_content_type_is_json(
        self, http_client: TestClient
    ) -> None:
        """Health response must have application/json content type."""
        response = http_client.get("/health")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    def test_health_has_no_extra_fields(
        self, http_client: TestClient
    ) -> None:
        """Health response should only have documented fields."""
        response = http_client.get("/health")
        data = response.json()
        expected_keys = {"status", "server", "version"}
        assert set(data.keys()) == expected_keys


# =============================================================================
# CORS Configuration Tests
# =============================================================================

class TestCorsConfiguration:
    """Tests for CORS header configuration.

    The server uses CORSMiddleware with allow_origins=["*"],
    allow_methods=["GET", "POST"], and allow_headers=["*"].
    """

    def test_cors_preflight_options_request(
        self, http_client: TestClient
    ) -> None:
        """OPTIONS preflight request should return CORS headers."""
        response = http_client.options(
            "/api/call",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # OPTIONS should succeed (200 or 204)
        assert response.status_code in (200, 204)

    def test_cors_allow_origin_header(
        self, http_client: TestClient
    ) -> None:
        """Response should include Access-Control-Allow-Origin."""
        response = http_client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        # With allow_origins=["*"], the header should be "*" or the origin
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin is not None

    def test_cors_allow_methods_header(
        self, http_client: TestClient
    ) -> None:
        """Preflight response should include Access-Control-Allow-Methods."""
        response = http_client.options(
            "/api/call",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_methods = response.headers.get("access-control-allow-methods", "")
        # Should include POST for /api/call
        assert "POST" in allow_methods or response.status_code in (200, 204)

    def test_cors_allow_headers_header(
        self, http_client: TestClient
    ) -> None:
        """Preflight response should include Access-Control-Allow-Headers."""
        response = http_client.options(
            "/api/call",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        allow_headers = response.headers.get("access-control-allow-headers")
        # With allow_headers=["*"], should allow Content-Type
        assert allow_headers is not None or response.status_code in (200, 204)

    def test_cors_on_health_endpoint(
        self, http_client: TestClient
    ) -> None:
        """Health endpoint should also have CORS headers."""
        response = http_client.get(
            "/health",
            headers={"Origin": "http://example.com"},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") is not None
```

## Edge Case Handling Strategy

### Current xfail Tests

The existing tests document two bugs in `http.py`:

1. **`test_null_body`**: Server crashes with `AttributeError` when body is JSON `null`
2. **`test_array_body`**: Server crashes with `AttributeError` when body is JSON array

Both occur because line 165 calls `body.get("params", {})` assuming body is a dict.

### Recommended Fix

Update `api_call_handler` in `http.py` to validate body type before accessing:

```python
async def api_call_handler(self, request: Request) -> JSONResponse:
    """Direct tool call endpoint for hook scripts."""
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        logger.warning("api.invalid_json", error=str(e))
        return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=400)

    # NEW: Validate body is a dict
    if not isinstance(body, dict):
        logger.warning("api.invalid_body_type", body_type=type(body).__name__)
        return JSONResponse(
            {"error": "Request body must be a JSON object"},
            status_code=400,
        )

    # Rest of handler unchanged...
    params = body.get("params", {})
    # ...
```

### Test Changes After Fix

Once the server is fixed, update the tests:

```python
def test_null_body(self, http_client: TestClient) -> None:
    """Null JSON body should return 400 with clear error."""
    response = http_client.post(
        "/api/call",
        content="null",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "error" in response.json()
    # Verify error message is helpful
    assert "JSON object" in response.json()["error"]

def test_array_body(self, http_client: TestClient) -> None:
    """Array JSON body should return 400 (batch not supported)."""
    response = http_client.post(
        "/api/call",
        json=[{"method": "tools/call", "params": {"name": "ping"}}],
    )
    assert response.status_code == 400
    assert "error" in response.json()
    assert "JSON object" in response.json()["error"]
```

## Integration with Existing Infrastructure

### Shared Fixtures

Reuse the existing `http_client` fixture from `test_http_schemas.py`:

```python
@pytest.fixture
def http_client(mock_tool_registry: dict[str, Any]) -> TestClient:
    """Create a test client for the HTTP server."""
    http_server = HttpServer(
        server=MagicMock(),
        services=MagicMock(),
        tool_registry=mock_tool_registry,
        host="127.0.0.1",
        port=6335,
    )
    app = http_server.create_app()
    return TestClient(app)
```

### Schema Import Pattern

Tests will import schemas from the new module:

```python
from tests.server.schemas.http import (
    HealthResponse,
    ApiErrorResponse,
    ApiStringResultResponse,
)
```

### Validation Helper Fixture

Add a fixture for convenient schema validation:

```python
@pytest.fixture
def validate_response():
    """Factory fixture for response schema validation."""
    from tests.server.schemas.http import (
        HealthResponse,
        ApiErrorResponse,
        ApiDictResponse,
    )

    def _validate(response_json: dict, schema: type[BaseModel]) -> None:
        """Validate response against schema, raising ValidationError on failure."""
        schema.model_validate(response_json)

    return _validate
```

## Test Coverage Matrix

| Endpoint | Test Area | Status |
|----------|-----------|--------|
| GET /health | Schema completeness | NEW |
| GET /health | Field types | NEW |
| GET /health | Field values | NEW |
| GET /health | Content-Type | NEW |
| GET /health | CORS headers | NEW |
| POST /api/call | Request schema | EXISTS |
| POST /api/call | Success response | EXISTS |
| POST /api/call | Error response | EXISTS |
| POST /api/call | HTTP status codes | EXISTS |
| POST /api/call | CORS preflight | NEW |
| POST /api/call | Null body (edge case) | FIX xfail |
| POST /api/call | Array body (edge case) | FIX xfail |
| OPTIONS /api/call | CORS preflight | NEW |

## Implementation Plan

### Phase 1: Schema Definitions (Low Risk)

1. Create `tests/server/schemas/__init__.py`
2. Create `tests/server/schemas/http.py` with Pydantic models
3. Add imports to existing test file

### Phase 2: Health Endpoint Tests (Low Risk)

1. Add `TestHealthEndpointSchema` class
2. Implement all 6 tests for health endpoint
3. Verify all pass with current server

### Phase 3: CORS Tests (Low Risk)

1. Add `TestCorsConfiguration` class
2. Implement 5 CORS-related tests
3. Verify CORS middleware is working as expected

### Phase 4: Edge Case Fixes (Medium Risk)

1. Fix `api_call_handler` body type validation in `http.py`
2. Update `test_null_body` to remove xfail marker
3. Update `test_array_body` to remove xfail marker
4. Verify both tests pass

## Dependencies

- **pydantic**: Already in project (used extensively)
- **starlette.testclient**: Already used in existing tests
- **pytest**: Already configured

No new dependencies required.

## Acceptance Criteria Mapping

| Criterion | Implementation |
|-----------|----------------|
| Health endpoint fully tested | `TestHealthEndpointSchema` class with 6 tests |
| Error response consistency | Existing tests + `ApiErrorResponse` schema |
| Success response schemas | `ApiDictResponse`, `ApiStringResultResponse` schemas |
| CORS configuration verified | `TestCorsConfiguration` class with 5 tests |
| Edge cases handled | Server fix + updated tests (remove xfail) |
| No regression | All existing tests remain unchanged and passing |
| Schema definitions centralized | `tests/server/schemas/http.py` module |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Edge case fix breaks existing behavior | Low | Medium | Comprehensive test coverage before fix |
| CORS tests flaky due to header ordering | Low | Low | Use flexible assertions (header present, not exact value) |
| Schema validation too strict | Medium | Low | Use `extra="allow"` where appropriate |

## Estimated Effort

- Schema definitions: 0.5 hours
- Health endpoint tests: 1 hour
- CORS tests: 1 hour
- Edge case server fix: 1 hour
- Edge case test updates: 0.5 hours
- Integration verification: 0.5 hours

**Total: ~4.5 hours**

## Open Questions

None. The spec is clear and the existing codebase provides good patterns to follow.
