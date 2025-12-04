# Debug Log: SPEC-002-07

## Issue: MockEmbedding Instantiation Error

### Date
2025-12-03

### Root Cause
The test fixture `mock_embedding_service` in `tests/git/test_analyzer.py` was incorrectly instantiating `MockEmbedding` with a `dimension=768` keyword argument, but the `MockEmbedding` class does not accept any constructor parameters (it has a hardcoded dimension).

### Error Details
```
ERROR at setup of TestGitAnalyzer.test_index_commits_initial

@pytest.fixture
async def mock_embedding_service():
    """Create a mock embedding service."""
>   return MockEmbedding(dimension=768)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: MockEmbedding.__init__() got an unexpected keyword argument 'dimension'
```

### Diagnosis Process
1. Ran tests to identify the error
2. Examined the error traceback showing `TypeError` for unexpected keyword argument
3. Checked the `MockEmbedding` class implementation to verify it doesn't accept dimension parameter
4. Identified that `MockEmbedding` has a fixed dimension defined internally

### Fix Applied
Changed line 19 in `tests/git/test_analyzer.py`:

**Before:**
```python
return MockEmbedding(dimension=768)
```

**After:**
```python
return MockEmbedding()
```

### Verification
- All tests now pass: 115 passed, 1 skipped
- No errors or failures
- Execution time: ~38 seconds

### Commit
- SHA: `06c659714a98e5d1dd208eb35aab6444e66e699e`
- Message: "Fix MockEmbedding instantiation (no dimension arg)"

### Additional Notes
The `MockEmbedding` class uses a hardcoded dimension value (likely 768) internally, so there's no need to pass it as a parameter. This is consistent with the mock embedding design pattern where test fixtures should use default configurations.
