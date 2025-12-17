## SPEC-014: Refactor search/results.py imports

### Summary
Removed duplicate RootCause and Lesson class definitions.

### Changes
- Removed local RootCause and Lesson dataclass definitions from search/results.py
- Added import from clams.observation.models
- Added __all__ export list to maintain API compatibility
