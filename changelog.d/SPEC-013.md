## SPEC-013: Consolidate VALID_AXES import

### Summary
Removed duplicate VALID_AXES definition from values/store.py.

### Changes
- Removed local VALID_AXES definition from values/store.py
- Added import from clams.server.tools.enums
- Eliminates code duplication for axis constants
