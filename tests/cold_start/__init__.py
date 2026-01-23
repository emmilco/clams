"""Cold-start tests for verifying behavior with no pre-existing data.

This package contains tests that verify all major operations work correctly
when starting from a fresh installation with no pre-existing collections or data.

These tests are marked with @pytest.mark.cold_start and can be run separately:
    pytest -m cold_start -v

Reference:
- BUG-043: memories, commits, values collections never created
- BUG-016: GHAP collections missing on first start
"""
