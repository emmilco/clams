## SPEC-016: Create schema generation utility for JSON schema enums

### Summary
Added utility module for generating and validating JSON schema definitions from Python Enum classes.

### Changes
- Added `src/clams/utils/schema.py` with functions for enum schema generation and validation
- Added 38 tests in `tests/utils/test_schema.py`
- Updated `src/clams/utils/__init__.py` to export new functions
