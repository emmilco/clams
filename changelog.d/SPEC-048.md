## SPEC-048: Hash/Eq Contract Tests for Other Hashable Classes

### Summary
Extended hash/eq contract testing beyond ContextItem to cover all hashable classes in the codebase. Added comprehensive tests for PlatformInfo and created a reusable helper function for contract verification.

### Changes
- Added `verify_hash_eq_contract()` reusable helper function in `tests/context/test_data_contracts.py`
- Added comprehensive audit documentation header with audit date (2026-01-28)
- Created `tests/utils/test_platform_contracts.py` with 6 contract tests for PlatformInfo
- Fixed `clams/` to `clams_scripts/` path in test_config.py (namespace rename fix)

### Classes Audited
- **ContextItem** (src/clams/context/models.py) - custom `__hash__/__eq__`, already tested by SPEC-047
- **PlatformInfo** (src/clams/utils/platform.py) - `@dataclass(frozen=True)`, new tests added
- Enums (Domain, Strategy, OutcomeStatus, ConfidenceTier, UnitType) - excluded, Python guarantees their contract

### Reference
BUG-028 (original hash/eq contract violation), SPEC-047 (ContextItem tests), R16-B recommendation
