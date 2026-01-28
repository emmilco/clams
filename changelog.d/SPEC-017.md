## SPEC-017: Add schema conformance tests for enum validation

### Summary
Added tests verifying Python Enum classes stay in sync with validation constants and JSON schemas.

### Changes
- Enhanced `tests/server/test_enum_schema_conformance.py` with Python enum validation tests
- Tests Domain, Strategy, and OutcomeStatus enums against their constants
