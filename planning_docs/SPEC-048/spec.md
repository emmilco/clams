# SPEC-048: Hash/Eq Contract Tests for Other Hashable Classes

## Summary

Extend hash/eq contract testing (established in SPEC-047 for ContextItem) to all other hashable classes in the codebase. This ensures all classes implementing `__hash__` and `__eq__` maintain the contract: if a == b, then hash(a) == hash(b).

## Background

BUG-028 showed `ContextItem.__hash__` using first 100 chars but `__eq__` using full content, violating the hash/eq contract. SPEC-047 added contract tests for ContextItem. This spec extends coverage to all other hashable classes.

**Reference**: See `planning_docs/tickets/recommendations-r14-r17.md` section R16-B for full context.

## Requirements

### 1. Audit Hashable Classes

Audit the codebase for all classes implementing `__hash__` or `__eq__`:

```bash
grep -r "__hash__" src/clams/ --include="*.py"
grep -r "__eq__" src/clams/ --include="*.py"
```

Document all discovered classes in `tests/test_data_contracts.py`.

### 2. Reusable Test Helper

Add a reusable helper function for contract verification:

```python
def verify_hash_eq_contract(cls, *args, **kwargs):
    """
    Verify hash/eq contract for any class.

    Usage:
        verify_hash_eq_contract(MyClass, arg1, arg2, kwarg1=value)
    """
    obj1 = cls(*args, **kwargs)
    obj2 = cls(*args, **kwargs)

    if obj1 == obj2:
        assert hash(obj1) == hash(obj2), (
            f"{cls.__name__} violates hash/eq contract: "
            f"equal objects have different hashes"
        )
```

### 3. Contract Tests for Each Hashable Class

For each discovered hashable class, add tests verifying:
- Equal objects have equal hashes
- Set membership is consistent
- Dict key lookup is consistent

### 4. Document Audit Results

Document in `tests/test_data_contracts.py`:
- Which classes were audited
- Date of audit
- Any classes that were found but intentionally excluded (with reason)

## Acceptance Criteria

- [ ] Codebase audited for classes with `__hash__` or `__eq__` methods
- [ ] Audit results documented in test file
- [ ] Reusable `verify_hash_eq_contract()` helper function created
- [ ] Contract tests added for each discovered hashable class
- [ ] Tests verify: if a == b, then hash(a) == hash(b)
- [ ] Tests verify set membership consistency
- [ ] Tests verify dict key lookup consistency
- [ ] All tests pass

## Out of Scope

- Pre-commit hook for detecting new hash/eq implementations (covered by SPEC-049)
- Fixing any contract violations found (should be filed as separate bugs)

## Dependencies

- SPEC-047 (Hash/eq contract tests for ContextItem) - provides base test file and patterns

## Testing Requirements

- Tests should fail if any class violates the contract
- Tests should include property-based testing with hypothesis if available
- Test values should exercise edge cases (empty strings, very long content, unicode, etc.)

## Error Handling

- If a class violates the contract, the test error message should clearly state:
  - Which class failed
  - What the hash values were
  - What the equality result was
