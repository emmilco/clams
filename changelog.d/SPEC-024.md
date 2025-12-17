## SPEC-024: Configuration Parity Verification

### Summary
Adds a comprehensive test framework to detect configuration drift between test fixtures and production code, preventing silent bugs caused by test/production mismatches.

### Changes
- Added `tests/infrastructure/test_config_parity.py` with tests verifying hooks config matches ServerSettings
- Added `tests/infrastructure/test_mock_parity.py` verifying mock classes match production interfaces
- Added `tests/infrastructure/test_fixture_parity.py` verifying fixture values match production defaults
- Tests verify embedding dimensions, clustering parameters, timeouts, and server commands are consistent
- All parity tests produce clear error messages referencing the canonical source

### References
- Related bugs: BUG-031, BUG-033, BUG-040, BUG-041
