# SPEC-047: Proposal

## Overview

Add a dedicated test module `tests/context/test_data_contracts.py` to verify that `ContextItem` maintains Python's hash/eq contract. The tests will ensure that equal items always have equal hashes, and that set/dict operations behave correctly.

The current implementation uses `(source, content[:100], len(content))` for hashing and `(source, content)` for equality. While this includes `len(content)` to reduce collisions, we need comprehensive tests to verify the contract holds for all cases and to prevent future regressions.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/context/test_data_contracts.py` | Create | New test module for hash/eq contract verification |

## Implementation Details

### Test Module Structure

```python
"""Tests for ContextItem hash/eq contract.

Python's hash/eq contract requires:
- If a == b, then hash(a) == hash(b)
- If hash(a) != hash(b), then a != b

Violating this contract causes silent bugs in set/dict operations.
Reference: BUG-028 - ContextItem hash/eq contract violation
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clams.context.models import ContextItem
```

### Test Categories

#### 1. Contract Invariant Tests

**`test_equal_items_have_equal_hashes`**
- Create two `ContextItem` instances with identical fields
- Assert that if `item1 == item2`, then `hash(item1) == hash(item2)`
- This is the fundamental contract requirement

**`test_contract_holds_for_various_lengths`**
- Test items with content shorter than 100 chars
- Test items with content exactly 100 chars
- Test items with content longer than 100 chars
- For each case, verify equal items have equal hashes

#### 2. Edge Case Tests

**`test_prefix_collision_items_are_not_equal`**
- Create items with identical first 100 chars but different suffixes
- Assert they are NOT equal (different content)
- Assert that if they somehow were equal (regression), hashes would match

**`test_whitespace_difference_items`**
- Items with only trailing whitespace differences
- Items with only internal whitespace differences
- Verify hash/eq contract holds regardless

**`test_empty_content`**
- Items with empty string content
- Items with single character content
- Verify contract holds at boundaries

**`test_unicode_content`**
- Items with unicode characters
- Items where first 100 chars cross unicode boundaries
- Verify slicing doesn't break contract

#### 3. Set/Dict Behavior Tests

**`test_set_membership_consistent`**
- Add item1 to a set
- Create item2 with same fields
- Assert `item2 in items` returns True
- This would fail if contract is violated

**`test_dict_key_lookup_consistent`**
- Use item1 as dict key
- Create item2 with same fields
- Assert `d[item2]` finds the same value
- This would fail if contract is violated

**`test_set_deduplication_works`**
- Add multiple equal items to a set
- Assert set contains only one item
- Verifies set deduplication relies on correct hash/eq

**`test_dict_overwrite_with_equal_key`**
- Set `d[item1] = "first"`
- Set `d[item2] = "second"` where item2 == item1
- Assert `d[item1] == "second"` and `len(d) == 1`

#### 4. Property-Based Tests (Hypothesis)

**`test_contract_invariant_property`**
- Use hypothesis to generate random content strings
- For any two items with same source and content:
  - Assert `hash(a) == hash(b)` when `a == b`
- Provides broader coverage than example-based tests

```python
@given(
    source=st.text(min_size=1, max_size=20),
    content=st.text(min_size=0, max_size=500),
    relevance=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_contract_invariant_property(
    source: str, content: str, relevance: float
) -> None:
    """Property: equal items MUST have equal hashes."""
    item1 = ContextItem(source, content, relevance, {"id": "1"})
    item2 = ContextItem(source, content, relevance, {"id": "2"})

    # These have same source and content, so they're equal
    assert item1 == item2, "Items with same source/content must be equal"
    # Contract: equal items must have equal hashes
    assert hash(item1) == hash(item2), (
        f"Contract violation: equal items have different hashes.\n"
        f"content length={len(content)}, first 100 chars match={content[:100]==content[:100]}"
    )
```

**`test_unequal_items_can_have_same_hash`**
- Document that hash collisions are allowed (just not the reverse)
- Different items MAY have the same hash
- Different items with different hashes MUST NOT be equal

### Helper Utilities

No additional helpers needed. Tests use standard pytest fixtures and hypothesis strategies.

### Complete Test List

1. `TestContextItemContract` class:
   - `test_equal_items_have_equal_hashes`
   - `test_contract_holds_for_short_content`
   - `test_contract_holds_for_exact_100_chars`
   - `test_contract_holds_for_long_content`
   - `test_prefix_collision_items_are_not_equal`
   - `test_whitespace_only_differences`
   - `test_empty_content`
   - `test_unicode_content`

2. `TestContextItemSetBehavior` class:
   - `test_set_membership_consistent`
   - `test_set_deduplication_works`

3. `TestContextItemDictBehavior` class:
   - `test_dict_key_lookup_consistent`
   - `test_dict_overwrite_with_equal_key`

4. Property-based tests:
   - `test_contract_invariant_property`
   - `test_unequal_items_can_collide`

## Testing Strategy

The tests themselves will be verified by:

1. **Running the test suite**: `pytest tests/context/test_data_contracts.py -v`
2. **Mutation testing**: Temporarily break the hash/eq implementation to verify tests catch it:
   - Change `__hash__` to only use `content[:50]` - should fail prefix collision tests
   - Change `__hash__` to exclude `len(content)` - should fail some contract tests
   - Change `__eq__` to only compare `source` - should fail content comparison tests
3. **Hypothesis coverage**: The property-based test will generate many edge cases automatically

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tests pass but don't catch real violations | Medium | Include mutation testing during review; use hypothesis for broader coverage |
| Hypothesis tests are slow | Low | Use `@settings(max_examples=100)` to limit iterations |
| Unicode edge cases missed | Low | Include explicit unicode tests with multi-byte characters |
| Test file location conflicts | Very Low | Using `test_data_contracts.py` which doesn't exist |

## Notes

- The current `ContextItem` implementation appears to already be fixed (includes `len(content)` in hash)
- These tests serve as regression tests to prevent future violations
- The tests are intentionally comprehensive to serve as documentation of the contract requirements
- Test docstrings explain the contract and reference BUG-028 for context
