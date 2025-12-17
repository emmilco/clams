# SPEC-013: Consolidate VALID_AXES Import in values/store.py

## Problem Statement

The `VALID_AXES` constant is defined in two locations with different types:

| Location | Definition | Type |
|----------|-----------|------|
| `src/clams/server/tools/enums.py:45` | `VALID_AXES = ["full", "strategy", "surprise", "root_cause"]` | `list[str]` |
| `src/clams/values/store.py:18` | `VALID_AXES = {"full", "strategy", "surprise", "root_cause"}` | `set[str]` |

This duplication creates maintenance risk: if axes are added or removed, both locations must be updated. The type inconsistency (list vs set) could also cause subtle bugs in code that depends on ordering.

## Single Source of Truth

**Canonical Location**: `src/clams/server/tools/enums.py`

This is the established location for all enum constants (DOMAINS, STRATEGIES, ROOT_CAUSE_CATEGORIES, VALID_AXES, OUTCOME_STATUS_VALUES) and validation helper functions (`validate_axis()`, etc.).

## Files to Update

### 1. `src/clams/values/store.py`

- **Remove**: Line 18 (`VALID_AXES = {"full", "strategy", "surprise", "root_cause"}`)
- **Add**: Import `VALID_AXES` from `clams.server.tools.enums`
- **Update**: Any usages that depend on set behavior (membership tests with `in` work identically for lists and sets)

### 2. No Other Changes Required

The duplicate in `values/store.py` is isolated. All other usages already import from `enums.py` (as verified by existing tests in `test_schema_consistency.py` and `test_enum_schema_conformance.py`).

## Acceptance Criteria

- [ ] `values/store.py` imports `VALID_AXES` from `clams.server.tools.enums`
- [ ] Local `VALID_AXES` definition removed from `values/store.py`
- [ ] All existing tests pass (no behavioral change)
- [ ] `mypy --strict` passes
- [ ] `ruff check` passes
