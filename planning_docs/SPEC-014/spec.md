# SPEC-014: Refactor search/results.py to Import RootCause and Lesson

## Summary

Remove duplicate `RootCause` and `Lesson` dataclass definitions from `src/clams/search/results.py` and import them from their canonical location in `src/clams/observation/models.py`.

## Problem

The `RootCause` and `Lesson` classes are defined in two places:

1. **Canonical location** (`src/clams/observation/models.py`):
   - Full implementations with `to_dict()` and `from_dict()` methods
   - Used by `GHAPEntry` and the observation subsystem

2. **Duplicate** (`src/clams/search/results.py`):
   - Simplified versions without serialization methods
   - Used by `ExperienceResult`

This duplication creates maintenance burden and risks divergence between the two definitions.

## Solution

1. Remove the `RootCause` and `Lesson` class definitions from `search/results.py`
2. Add import: `from clams.observation.models import RootCause, Lesson`
3. Verify all existing tests pass (no behavior change expected)

## Files to Modify

- `src/clams/search/results.py` - Remove duplicate classes, add import

## Acceptance Criteria

- [ ] `RootCause` and `Lesson` are imported from `observation.models` in `search/results.py`
- [ ] No duplicate class definitions remain in `search/results.py`
- [ ] All existing tests pass without modification
- [ ] Type checking (mypy) passes
- [ ] Linter (ruff) passes

## Risk Assessment

**Low risk**: This is a straightforward import refactoring. The classes have identical structures (same fields and types). The canonical versions have additional methods (`to_dict`/`from_dict`) that are not used by the search module, so compatibility is assured.
