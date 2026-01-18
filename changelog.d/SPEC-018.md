## SPEC-018: Cold-Start Integration Tests for Vector Store Collections

### Summary
Add integration tests that verify all vector store collections can be properly created on first use against a real Qdrant instance.

### Changes
- Added `tests/integration/test_cold_start_collections.py` with 16 integration tests
- Tests cover all 5 collection types: memories, commits, values, code_units, and GHAP collections
- Each test verifies: collection deletion, non-existence check, lazy creation, dimension verification (768), and data round-trip
- Tests fail (not skip) if Qdrant is unavailable, ensuring CI catches infrastructure issues
