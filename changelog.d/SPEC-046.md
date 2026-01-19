## SPEC-046: Token Counting Utility Tests (R15-C)

### Summary
Added comprehensive tests for the token estimation utility to verify accuracy and catch edge cases.

### Changes
- Added 20 new tests to `tests/context/test_tokens.py` (32 total)
- `TestEstimateTokensAccuracy`: Verifies 4-char/token heuristic for English, code, JSON, markdown
- `TestEstimateTokensEdgeCases`: Covers single chars, Unicode (CJK, emojis), whitespace, long text
- `TestTruncateToTokensIntegrity`: Verifies budget enforcement and newline boundary handling
- `TestDistributeBudgetValidation`: Tests error handling and budget distribution
