# SPEC-046: Token Counting Utility (R15-C)

## Problem Statement

The current token estimation in `src/clams/context/tokens.py` uses a simple 4-chars-per-token heuristic. While this is reasonable for English text, it may not accurately reflect actual token counts for code, JSON responses, or multilingual content.

Response size assertions (SPEC-044, SPEC-045) use byte measurements, but token counts are what ultimately matter for LLM context window management. Having a dedicated token counting utility would allow more precise budget management.

## Proposed Solution

Add a token counting utility that can estimate tokens more accurately than the current simple heuristic, while remaining fast and not requiring external API calls.

## Acceptance Criteria

- [ ] `estimate_tokens()` function exists in `src/clams/context/tokens.py` (existing function)
- [ ] Tests exist in `tests/context/test_tokens.py` that verify token estimation accuracy
- [ ] Tests verify estimation is within 20% of actual for sample texts:
  - Plain English text
  - Python code
  - JSON with nested structures
  - Markdown with formatting
- [ ] Tests document the expected behavior and rationale for the heuristic
- [ ] Tests verify edge cases:
  - Empty string returns 0
  - Single character returns 1
  - Unicode characters handled correctly
- [ ] Tests verify `truncate_to_tokens()` preserves content integrity
- [ ] Tests verify `distribute_budget()` allocates correctly across sources

## Implementation Notes

- The existing `estimate_tokens()` uses `len(text) // 4` which is conservative
- Reference: OpenAI's tiktoken averages ~4 chars/token for English, less for code
- No need to add tiktoken dependency - the heuristic is sufficient for budget estimation
- Focus is on testing the existing implementation, not changing it
- Example test pattern:
  ```python
  class TestTokenEstimation:
      """Verify token estimation accuracy and edge cases."""

      def test_english_text_estimation(self):
          """English text should be within 20% of 4 chars/token."""
          text = "The quick brown fox jumps over the lazy dog."
          estimated = estimate_tokens(text)
          # 44 chars / 4 = 11 tokens expected
          assert 9 <= estimated <= 13  # Within 20%

      def test_code_estimation(self):
          """Code typically has more tokens per char due to punctuation."""
          code = "def foo(x): return x * 2"
          estimated = estimate_tokens(code)
          # 24 chars / 4 = 6 tokens minimum
          assert estimated >= 6

      def test_empty_string(self):
          """Empty string should return 0 tokens."""
          assert estimate_tokens("") == 0
  ```

## Testing Requirements

- Tests should use representative sample texts
- Document why each test case matters
- Tests should not depend on external tokenizers
- Tests should be deterministic (no randomness)

## Out of Scope

- Adding tiktoken or other tokenizer dependencies
- Changing the existing heuristic (just testing it)
- Per-model token counting differences
