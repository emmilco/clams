## SPEC-033: Platform-Specific Pre-Checks

### Summary

Added centralized platform detection and pytest integration to handle platform-specific test requirements consistently, addressing issues with MPS fork safety (BUG-042), memory leaks (BUG-014), and scattered ad-hoc platform checks.

### Changes

- Added `src/clams/utils/platform.py` with `PlatformInfo` dataclass, `get_platform_info()`, `check_requirements()`, and `format_report()` functions
- Added pytest markers: `requires_mps`, `requires_cuda`, `requires_ripgrep`, `requires_docker`, `requires_qdrant`, `macos_only`, `linux_only`
- Added `pytest_collection_modifyitems` hook to auto-skip tests when platform requirements not met
- Added `.claude/gates/check_platform.sh` for pre-flight platform capability reporting
- Modified `check_tests.sh` and `check_tests_python.sh` to distinguish platform skips (allowed) from code skips (fail gate)
- Migrated existing tests to use new markers instead of inline `skipif` decorators
- Added `tests/utils/test_platform.py` with comprehensive tests for platform module
- Updated `pyproject.toml` with marker documentation
