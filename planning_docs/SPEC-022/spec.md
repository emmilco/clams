# SPEC-022: HTTP API Schema Tests

## Summary

Add comprehensive tests to verify that all HTTP API responses conform to documented schemas, preventing integration failures between hook scripts and the CLAMS server.

## Background

The CLAMS server exposes an HTTP API that serves two primary use cases:
1. **Hook script integration** via POST at `/api/call` endpoint
2. **Health monitoring** via GET at `/health` endpoint

Note: The SSE endpoint (`/sse`) for Claude Code integration is out of scope for this spec due to its streaming nature requiring different testing approaches.

Previous bugs (e.g., BUG-033) have demonstrated that schema mismatches between hooks and server can cause integration failures. While `test_http_schemas.py` and `test_tool_response_schemas.py` already exist and provide substantial coverage, there are gaps in coverage that this spec addresses.

## Current State Analysis

### Existing Test Coverage

**`tests/server/test_http_schemas.py`** (678 lines):
- Request schema validation for `/api/call`
- Response schema validation for success/error cases
- HTTP status code verification
- Malformed request handling
- JSON-RPC style compatibility

**`tests/server/test_tool_response_schemas.py`** (1320 lines):
- MCP tool response structure validation
- Enum value conformance (DOMAINS, STRATEGIES, VALID_AXES, etc.)
- Success/error response patterns per tool category
- Memory, GHAP, Learning, Search, Session, and Context tools

**`tests/server/test_http.py`** (255 lines):
- Basic HTTP server initialization
- Health endpoint response structure
- API call endpoint basic functionality
- Daemon management functions

### Identified Gaps

1. **Health endpoint schema completeness**: The `/health` endpoint response schema is tested minimally - only verifies `status`, `server`, and `version` keys exist, but doesn't validate types or exhaustive field coverage.

2. **SSE endpoint schema**: The `/sse` endpoint behavior is not directly tested for schema conformance (though this is complex due to streaming nature).

3. **CORS headers validation**: CORS configuration is set but not verified in tests.

4. **Content-Type header consistency**: Only partially tested across endpoints.

5. **Known edge cases marked xfail**: Two tests in `test_http_schemas.py` are marked `xfail` for null/array body handling - these represent actual server bugs that should be fixed.

## Endpoints to Test

Note: Only `/health` and `/api/call` are in scope. The `/sse` endpoint requires separate testing due to its streaming nature.

### GET /health

**Current response schema (from `src/clams/server/http.py:92-101`)**:
```json
{
  "status": "healthy",
  "server": "clams",
  "version": "0.1.0"
}
```

**Required tests**:
- All fields present with correct types
- Status is always "healthy" when server responds
- Version follows semver format
- Content-Type is `application/json`
- CORS headers present

### POST /api/call

**Request schema** (JSON-RPC inspired):
```json
{
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {...}
  }
}
```

**Success response schemas** (vary by result type):
```json
// Dict results - returned directly
{"key": "value", ...}

// List results - returned directly
[{"item": 1}, ...]

// String results - wrapped
{"result": "string value"}
```

**Error response schema**:
```json
{
  "error": "error message"
}
```

**Required tests** (beyond existing):
- Validate error response schema consistency across all error types
- Test HTTP method restrictions (GET should return 405)
- Verify OPTIONS preflight for CORS
- Test request size limits (if any)

## Schema Validation Approach

### 1. Use Pydantic Models for Schema Definitions

Define response schemas as Pydantic models in test fixtures:

```python
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: Literal["healthy"]
    server: str
    version: str  # Could add regex validation for semver

class ApiErrorResponse(BaseModel):
    error: str

class ApiSuccessResponse(BaseModel):
    # For wrapped string results
    result: str | None = None
    # Allow additional fields for dict passthrough
    model_config = ConfigDict(extra='allow')
```

### 2. Response Validation Fixtures

```python
@pytest.fixture
def validate_health_response():
    def _validate(response: dict) -> None:
        HealthResponse.model_validate(response)
    return _validate
```

### 3. Parameterized Tests for Tool Responses

Leverage existing tool registry to verify all tools return valid schemas:

```python
@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_tool_returns_valid_schema(http_client, tool_name, tool_args):
    response = http_client.post("/api/call", json={
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": tool_args[tool_name]}
    })
    # Validate against tool-specific schema
```

## Test Scenarios

### 1. Health Endpoint Schema Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_health_response_schema_complete` | All required fields present | status, server, version keys |
| `test_health_response_types` | Field types correct | status: str, server: str, version: str |
| `test_health_response_values` | Field values valid | status="healthy", server="clams" |
| `test_health_content_type` | Content-Type header | application/json |
| `test_health_cors_headers` | CORS headers present | Access-Control-Allow-* |

### 2. API Call Error Response Schema Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_error_400_schema` | Bad request errors | {"error": str}, status 400 |
| `test_error_404_schema` | Unknown tool errors | {"error": str}, status 404 |
| `test_error_500_schema` | Internal errors | {"error": str}, status 500 |
| `test_error_content_type` | All errors return JSON | application/json |

### 3. API Call Success Response Schema Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_dict_response_passthrough` | Dict tools | Direct JSON object |
| `test_list_response_passthrough` | List tools | Direct JSON array |
| `test_string_response_wrapped` | String tools | {"result": str} |
| `test_none_response_handling` | Tools returning None | Defined behavior |

### 4. CORS and Security Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_options_preflight` | OPTIONS request handling | CORS headers |
| `test_cors_allow_origin` | Origin header | Access-Control-Allow-Origin |
| `test_cors_allow_methods` | Allowed methods | GET, POST |

### 5. Edge Case Tests (Fix xfail tests)

| Test | Description | Current Status |
|------|-------------|----------------|
| `test_null_body` | JSON null body | xfail - server crashes |
| `test_array_body` | JSON array body | xfail - server crashes |

## Acceptance Criteria

1. **Health endpoint fully tested**: All fields validated for presence, type, and value constraints.

2. **Error response consistency verified**: All error conditions return the documented `{"error": str}` schema with appropriate HTTP status codes.

3. **Success response schemas documented and tested**: Each response shape (dict passthrough, list passthrough, string wrapped) has explicit schema validation.

4. **CORS configuration verified**: Preflight requests and CORS headers tested.

5. **Edge cases handled gracefully**: The two xfail tests either:
   - Pass after fixing server bugs (preferred)
   - Remain xfail with documented rationale if intentional behavior

6. **No regression in existing tests**: All existing tests in `test_http.py`, `test_http_schemas.py`, and `test_tool_response_schemas.py` continue to pass.

7. **Schema definitions centralized**: Pydantic models or equivalent schema definitions extracted for reuse and documentation.

## Implementation Notes

### File Organization

New tests should be added to `tests/server/test_http_schemas.py` to keep HTTP API schema tests consolidated. If the file grows too large, consider:

```
tests/server/
  test_http_schemas/
    __init__.py
    test_health.py
    test_api_call.py
    test_cors.py
    conftest.py  # Shared fixtures and schema definitions
```

### Dependencies

- `pydantic` (already in project) for schema validation
- `starlette.testclient` (already used) for HTTP testing

### Out of Scope

- SSE endpoint streaming behavior (complex to test, separate spec)
- Performance testing of API endpoints
- Authentication/authorization (not implemented)
- Rate limiting (not implemented)
