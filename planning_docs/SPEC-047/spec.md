# SPEC-047: Hash/Eq Contract Tests for ContextItem (R16-A)

## Problem Statement

BUG-028 showed `ContextItem.__hash__` using first 100 chars but `__eq__` using full content. This violates Python's hash/eq contract: equal objects must have equal hashes.

When hash/eq contract is violated:
1. Set operations become unpredictable (item not found even though equal item exists)
2. Dict key lookups fail silently
3. Deduplication produces wrong results

## Proposed Solution

Add tests that verify `ContextItem` maintains the hash/eq contract, including edge cases and practical consequences.

## Acceptance Criteria

- [ ] Test file exists at `tests/context/test_data_contracts.py`
- [ ] Test verifies: `if a == b then hash(a) == hash(b)` for ContextItem
- [ ] Test covers edge cases:
  - Items with identical first 100 chars, different suffix
  - Items with identical content
  - Items shorter than 100 chars
  - Items with only whitespace differences
- [ ] Test verifies set membership is consistent
- [ ] Test verifies dict key lookup is consistent
- [ ] Test documents the contract requirement in docstring
- [ ] Optional: Use property-based testing (hypothesis) for thorough coverage

## Implementation Notes

- Python's hash/eq contract requires:
  - If `a == b`, then `hash(a) == hash(b)`
  - If `hash(a) != hash(b)`, then `a != b`
- Violations cause silent bugs in set/dict operations
- Reference: BUG-028 - ContextItem hash/eq contract violation
- ContextItem is in `src/clams/context/models.py` or similar
- Example tests:
  ```python
  class TestContextItemContract:
      """Verify ContextItem maintains hash/eq contract."""

      def test_equal_items_have_equal_hashes(self):
          """INVARIANT: if a == b then hash(a) == hash(b)"""
          item1 = ContextItem(content="identical content", source="test")
          item2 = ContextItem(content="identical content", source="test")

          if item1 == item2:
              assert hash(item1) == hash(item2), (
                  "Contract violation: equal items must have equal hashes"
              )

      def test_prefix_collision_does_not_break_equality(self):
          """Items with same first 100 chars but different content."""
          prefix = "x" * 100
          item1 = ContextItem(content=prefix + "suffix_a", source="test")
          item2 = ContextItem(content=prefix + "suffix_b", source="test")

          # These must NOT be equal (different content)
          assert item1 != item2, "Items with different content must not be equal"

          # If they ARE equal (which would be a bug), hashes must match
          if item1 == item2:
              assert hash(item1) == hash(item2), "Contract violation detected"

      def test_set_membership_consistent(self):
          """Equal items should have consistent set membership."""
          items = set()
          item1 = ContextItem(content="test content", source="test")
          item2 = ContextItem(content="test content", source="test")

          items.add(item1)

          # If contract holds, item2 should be "in" the set
          assert item2 in items, "Equal item not found in set (contract violation)"

      def test_dict_key_lookup_consistent(self):
          """Equal items should work as dict keys consistently."""
          d = {}
          item1 = ContextItem(content="test content", source="test")
          item2 = ContextItem(content="test content", source="test")

          d[item1] = "value"

          # If contract holds, item2 should find the same entry
          assert d.get(item2) == "value", (
              "Equal item cannot find dict entry (contract violation)"
          )
  ```

## Testing Requirements

- Tests should catch BUG-028 style violations
- If ContextItem is already fixed, tests should pass
- Run as part of standard test suite
- Tests must fail if hash uses different data than eq

## Out of Scope

- Testing other hashable classes (covered by SPEC-048)
- Pre-commit hook for hash/eq (covered by SPEC-049)
- Fixing ContextItem if it's broken (separate bug fix)
