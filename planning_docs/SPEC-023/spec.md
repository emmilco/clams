# SPEC-023: Mock Interface Verification Tests

## Summary

This spec defines systematic tests to verify that mock classes implement the same interface as their production counterparts, preventing "works in test, fails in production" bugs caused by mock drift.

## Problem Statement

Several bugs (BUG-040, BUG-041) were caused by mock classes having different method signatures, field names, or return types than production classes. When tests use mocks that don't match production interfaces, tests pass but production code fails.

### Root Cause Examples

**BUG-040**: `MockSearcher` in `tests/context/test_assembler.py` had result types with different field names than `search.results` types:
- `start_line`/`end_line` vs `line_start`/`line_end`
- `cluster_size` vs `member_count`
- `lesson: dict` vs `lesson: Lesson` (dataclass)

**BUG-041**: The concrete `Searcher` class didn't inherit from the abstract `Searcher` ABC, creating type system fragmentation. Tests used `MockSearcher(Searcher)` inheriting from the ABC, but production used a different, unrelated class.

### Impact

- Tests pass with mocks but production code fails with `KeyError`, `AttributeError`
- Type checkers don't catch mismatches because mocks define their own interfaces
- Interface drift accumulates silently until production failures occur

## Current State

### Existing Mock Classes

| Mock Class | Location | Production Class | Status |
|------------|----------|------------------|--------|
| `MockSearcher` | `tests/context/test_assembler.py:19` | `clams.search.searcher.Searcher` (also ABC at `clams.context.searcher_types.Searcher`) | Covered by `test_mock_parity.py` |
| `MockEmbedder` | `tests/server/tools/test_bug_017_regression.py:17` | `clams.embedding.base.EmbeddingService` | Covered by `test_mock_parity.py` |
| `MockValue` | `tests/server/test_context_tools.py:12` | Simple dataclass, no production counterpart | Not critical |
| `MockExperienceResult` | `tests/server/test_context_tools.py:19` | `clams.search.results.ExperienceResult` | Needs coverage |
| `MockRootCause` | `tests/server/tools/test_bug_021_regression.py:18` | `clams.search.results.RootCause` | Test-internal helper |
| `MockLesson` | `tests/server/tools/test_bug_021_regression.py:24` | `clams.search.results.Lesson` | Test-internal helper |

### Existing Test Coverage

The file `tests/infrastructure/test_mock_parity.py` already provides comprehensive coverage:

1. **MockSearcher verification**: Tests against both ABC and concrete Searcher
   - `TestMockSearcherParityWithABC`: Verifies MockSearcher has all ABC methods, signatures match
   - `TestMockSearcherParityWithConcrete`: Verifies MockSearcher matches production Searcher
   - `TestConcreteMatchesABC`: Verifies concrete Searcher implements ABC correctly

2. **MockEmbedder verification**: Tests against EmbeddingService ABC
   - `TestMockEmbedderParity`: Verifies methods, signatures, and dimension property

3. **Return type verification**:
   - `TestMockSearcherReturnTypes`: Verifies return type annotations match
   - `TestMockEmbedderReturnTypes`: Verifies return type annotations match

4. **Parameterized comprehensive tests**:
   - `TestParameterizedMockParity`: Runs all verifications across all known mock/production pairs
   - `get_all_mock_production_pairs()`: Central registry of mock/production pairs

## Specification

### Objective

Enhance and systematize mock interface verification to prevent mock drift bugs. The goal is to ensure that:

1. All mock classes implement the complete interface of their production counterparts
2. Method signatures (parameter names, types, defaults) match exactly
3. Return type annotations match
4. New mocks are automatically included in verification

### Mock/Production Pairs to Verify

| # | Mock Class | Production Class(es) | Verification Level |
|---|------------|---------------------|-------------------|
| 1 | `MockSearcher` | `Searcher` ABC + concrete `Searcher` | Full (existing) |
| 2 | `MockEmbedder` | `EmbeddingService` ABC | Full (existing) |
| 3 | `MockExperienceResult` (test_context_tools) | `ExperienceResult` dataclass | Field names only |

### Verification Approach

#### 1. Method Coverage Verification

For each mock/production pair:
- Get all public methods from production class (excluding `_` prefixed)
- Verify mock has all the same methods
- Report any missing methods as failures

```python
def get_public_methods(cls: type) -> set[str]:
    return {
        name for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name))
    }
```

#### 2. Signature Matching Verification

For each shared method:
- Compare parameter names (excluding `self`)
- Compare parameter kinds (POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, etc.)
- Verify mock doesn't have extra required parameters
- Report any signature mismatches

```python
def compare_signatures(prod_cls: type, mock_cls: type, method_name: str) -> list[str]:
    # Returns list of differences (empty if signatures match)
```

#### 3. Return Type Verification

For each shared method:
- Compare return type annotations
- Allow for subtype compatibility where appropriate
- Report mismatches that could cause runtime failures

```python
def compare_return_types(prod_cls: type, mock_cls: type, method_name: str) -> list[str]:
    # Returns list of differences (empty if types match)
```

#### 4. Central Mock Registry

Maintain a registry of all mock/production pairs:

```python
def get_all_mock_production_pairs() -> list[tuple[type, type, str, set[str] | None]]:
    """Return all known mock/production class pairs for verification."""
    return [
        (SearcherABC, MockSearcher, "MockSearcher vs ABC", {"register"}),
        (ConcreteSearcher, MockSearcher, "MockSearcher vs Concrete", {"register"}),
        (EmbeddingService, MockEmbedder, "MockEmbedder vs ABC", {"register"}),
        # Add new pairs here when new mocks are created
    ]
```

### Test Scenarios

#### Scenario 1: Mock has all production methods
- **Given**: A mock/production pair
- **When**: Comparing public methods
- **Then**: Mock should have all methods defined in production class

#### Scenario 2: Method signatures match
- **Given**: A method that exists in both mock and production
- **When**: Comparing signatures
- **Then**: Parameter names should match, mock should not have extra required params

#### Scenario 3: Return types match
- **Given**: A method with return type annotations in both classes
- **When**: Comparing return types
- **Then**: Types should be identical or compatible

#### Scenario 4: ABC implementation verified
- **Given**: A concrete class and its ABC
- **When**: Checking inheritance
- **Then**: Concrete class should be subclass of ABC

#### Scenario 5: New mock automatically verified
- **Given**: A new mock class added to the registry
- **When**: Running parameterized tests
- **Then**: New mock should be verified without modifying test code

### Test Categories

1. **Individual class tests**: Specific tests for each mock/production pair with detailed assertions
2. **Parameterized tests**: Generic tests that run across all pairs in the registry
3. **Helper function tests**: Tests for the verification utilities themselves

### File Organization

```
tests/
  infrastructure/
    test_mock_parity.py          # Main mock verification tests (existing)
  context/
    test_assembler.py            # Contains MockSearcher (existing)
  server/
    tools/
      test_bug_017_regression.py # Contains MockEmbedder (existing)
      test_bug_021_regression.py # Contains MockRootCause, MockLesson
    test_context_tools.py        # Contains MockValue, MockExperienceResult
```

## Acceptance Criteria

### Core Requirements

- [ ] AC1: `MockSearcher` is verified against both `Searcher` ABC and concrete `Searcher` implementation
- [ ] AC2: `MockEmbedder` is verified against `EmbeddingService` ABC
- [ ] AC3: All public methods are verified to exist in mocks
- [ ] AC4: Method signatures are verified to match (parameter names, no extra required params)
- [ ] AC5: Return type annotations are verified to match where present
- [ ] AC6: Central registry exists for all mock/production pairs
- [ ] AC7: Parameterized tests automatically verify all registered pairs

### Error Messages

- [ ] AC8: Missing method errors clearly identify which methods are missing
- [ ] AC9: Signature mismatch errors identify specific parameter differences
- [ ] AC10: Error messages reference relevant bug reports (BUG-040, BUG-041)

### Maintainability

- [ ] AC11: Adding a new mock/production pair requires only adding to the registry
- [ ] AC12: Helper functions are reusable and well-documented
- [ ] AC13: Tests are organized in `tests/infrastructure/test_mock_parity.py`

### Documentation

- [ ] AC14: Mock classes include comments warning about interface parity requirements
- [ ] AC15: References to `test_mock_parity.py` in mock class docstrings

## Implementation Notes

### Existing Implementation

The current `tests/infrastructure/test_mock_parity.py` already implements most of this specification:

1. **Helper functions**: `get_public_methods()`, `get_method_signature()`, `compare_signatures()`, `compare_return_types()`
2. **Specific test classes**: `TestMockSearcherParityWithABC`, `TestMockSearcherParityWithConcrete`, `TestMockEmbedderParity`
3. **Parameterized tests**: `TestParameterizedMockParity` with `get_all_mock_production_pairs()`
4. **Comprehensive verification**: `verify_mock_interface_complete()`

### Gaps to Address

1. **MockExperienceResult coverage**: The mock in `test_context_tools.py` is not currently in the registry
2. **Documentation**: Ensure all mock classes have docstrings pointing to `test_mock_parity.py`

### Test Execution

```bash
# Run all mock parity tests
pytest tests/infrastructure/test_mock_parity.py -v

# Run specific test class
pytest tests/infrastructure/test_mock_parity.py::TestMockSearcherParityWithABC -v

# Run parameterized tests
pytest tests/infrastructure/test_mock_parity.py::TestParameterizedMockParity -v
```

## Related Bugs

- **BUG-040**: Duplicate result type definitions with incompatible fields
- **BUG-041**: Searcher class conflict - abstract vs concrete incompatible interfaces

## Related Specifications

- **R10-B** (from `recommendations-r9-r13.md`): Add Mock-to-Production Interface Verification
