## SPEC-044: Response Size Assertions for GHAP Tests (R15-A)

### Summary
Added regression tests to verify GHAP tool responses stay within token-efficient size limits, preventing the 50k+ token waste seen in BUG-030.

### Changes
- Added `TestGHAPResponseEfficiency` class in `tests/server/test_response_efficiency.py`
- 8 tests covering all GHAP tools: start, update, resolve, get_active, list
- Verified size limits: 500 bytes for simple operations, 2000 bytes for active GHAP with history
- Added minimum 10-byte checks to catch broken endpoints
- All tests use `json.dumps()` for accurate serialized size measurement
