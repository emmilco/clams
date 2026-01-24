## SPEC-031: Cross-Component Integration Tests

### Summary
Added integration tests verifying contracts at component boundaries, catching field mismatches and type incompatibilities.

### Changes
- Added `tests/integration/test_boundary_contracts.py` with 40 tests covering:
  - Storage boundary contracts (GHAP, Memory, Code, Commit payloads)
  - Retrieval boundary contracts (search results, filter handling)
  - Context assembly contracts (experience ordering, value handling)
  - Embedding service contracts (dimension consistency, batch handling)
- Defined contract specifications: GHAP_PAYLOAD_CONTRACT, MEMORY_PAYLOAD_CONTRACT, etc.
- Added regression tests for BUG-006, BUG-019, BUG-027, BUG-036, BUG-040, BUG-041
- Tests verify field names match across storage, retrieval, and assembly layers
