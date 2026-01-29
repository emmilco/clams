# SPEC-046: Token Counting Utility - Technical Proposal

## Problem Statement

The codebase needs a general-purpose token estimation utility for:
1. **Response size assertions** - Verifying tool responses stay within token-efficient limits
2. **Context budget management** - Estimating content size before assembly
3. **Future token-aware features** - Any feature that needs to estimate text size in tokens

Currently, `src/clams/context/tokens.py` provides token estimation, but it is:
- Tightly coupled to context assembly (includes budget distribution, item capping)
- Uses only character-based estimation (no alternative methods)
- Does not validate input types (no `TypeError` for non-strings)

The spec requires a standalone utility in `src/clams/utils/tokens.py` with:
- Simple, focused API (`estimate_tokens()` only)
- Multiple estimation methods ("chars" and "words")
- Proper input validation (`TypeError` for non-strings)

## Proposed Solution

### New Module: `src/clams/utils/tokens.py`

Create a new, focused token estimation utility separate from the context-specific token module.

```python
"""Token estimation utilities.

Provides heuristic-based token counting for budget estimation and size assertions.
These are approximations, not exact counts - use for soft limits only.

Estimation accuracy (vs actual tokenization):
- English prose: ~4.5 chars/token actual, our estimate is conservative at 4 chars/token
- Code: More variable due to punctuation, our estimate is reasonable
- CJK/Unicode: Significantly underestimates (counts code points, not actual tokens)
"""

from typing import Literal


def estimate_tokens(
    text: str,
    method: Literal["chars", "words"] = "chars"
) -> int:
    """Estimate the number of tokens in text.

    Args:
        text: The text to estimate tokens for
        method: Estimation method
            - "chars": len(text) // 4 (conservative, ~4 chars/token)
            - "words": int(len(text.split()) * 1.3) (30% overhead for subwords)

    Returns:
        Estimated token count (always >= 0)

    Raises:
        TypeError: If text is not a string

    Examples:
        >>> estimate_tokens("Hello, world!")
        3
        >>> estimate_tokens("Hello, world!", method="words")
        2
        >>> estimate_tokens("")
        0
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    if method == "chars":
        return max(0, len(text) // 4)
    else:  # method == "words"
        return max(0, int(len(text.split()) * 1.3))
```

### API Design Rationale

**Why two methods?**
- **Character-based (default)**: Simple, fast, works for all content types. Conservative estimate that accounts for markdown overhead. Best for budget limits where over-estimation is acceptable.
- **Word-based**: Better for prose with clear word boundaries. Adds 30% for subword tokenization (common words split into multiple tokens). Better when estimating content that will be displayed to users.

**Why `TypeError` for non-strings?**
- Explicit failure is better than silent bugs
- Prevents accidental `None` or numeric input from causing subtle issues
- Consistent with Python's type safety conventions

**Why in `utils/` instead of enhancing `context/tokens.py`?**
- Separation of concerns: general utility vs. context-specific logic
- The context module has budget distribution, item capping, source weights - all specific to context assembly
- Other modules (response tests, future features) shouldn't import from context

### Module Exports

Update `src/clams/utils/__init__.py`:

```python
from clams.utils.tokens import estimate_tokens

__all__ = [
    # ... existing exports ...
    # Token utilities
    "estimate_tokens",
]
```

### Relationship to Existing Code

The new `utils/tokens.py` is **independent** of `context/tokens.py`:
- `context/tokens.py` continues to exist with its specialized functions
- `context/tokens.py` could optionally be refactored to use `utils/tokens.py` internally, but this is out of scope for SPEC-046

## Test Strategy

### Test Location

`tests/utils/test_tokens.py` (new file)

### Test Classes

```python
class TestEstimateTokensCharMethod:
    """Test character-based token estimation (default method)."""

    def test_basic_estimation(self) -> None:
        """Basic character counting: len(text) // 4."""
        assert estimate_tokens("a" * 400) == 100
        assert estimate_tokens("a" * 4) == 1

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert estimate_tokens("") == 0

    def test_whitespace_only(self) -> None:
        """Whitespace counts as characters."""
        assert estimate_tokens("    ") == 1  # 4 spaces
        assert estimate_tokens("\n\n\n\n") == 1


class TestEstimateTokensWordMethod:
    """Test word-based token estimation."""

    def test_basic_word_counting(self) -> None:
        """Word count * 1.3, truncated to int."""
        text = "one two three four"  # 4 words
        assert estimate_tokens(text, method="words") == 5  # int(4 * 1.3)

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert estimate_tokens("", method="words") == 0

    def test_single_word(self) -> None:
        """Single word gets 1.3x multiplier."""
        assert estimate_tokens("hello", method="words") == 1  # int(1 * 1.3)


class TestEstimateTokensEdgeCases:
    """Test edge cases for both methods."""

    def test_unicode_chars_method(self) -> None:
        """Unicode characters counted by code points (chars method)."""
        cjk = "\u4f60\u597d\u4e16\u754c"  # 4 CJK characters
        assert estimate_tokens(cjk) == 1  # 4 code points / 4

    def test_unicode_words_method(self) -> None:
        """Unicode words counted normally (words method)."""
        cjk = "\u4f60\u597d \u4e16\u754c"  # 2 "words" separated by space
        assert estimate_tokens(cjk, method="words") == 2  # int(2 * 1.3)

    def test_very_short_text(self) -> None:
        """Short text returns 0 for chars, 1 for words."""
        assert estimate_tokens("hi") == 0  # 2 // 4 = 0
        assert estimate_tokens("hi", method="words") == 1  # int(1 * 1.3)


class TestEstimateTokensTypeValidation:
    """Test input type validation."""

    def test_none_raises_typeerror(self) -> None:
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(None)  # type: ignore

    def test_int_raises_typeerror(self) -> None:
        """Integer input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(123)  # type: ignore

    def test_bytes_raises_typeerror(self) -> None:
        """Bytes input raises TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            estimate_tokens(b"hello")  # type: ignore
```

### Test Coverage Matrix

| Requirement | Test |
|-------------|------|
| `estimate_tokens()` in `utils/tokens.py` | Module import test |
| Character-based: `len(text) // 4` | `TestEstimateTokensCharMethod.test_basic_estimation` |
| Word-based: `int(len(text.split()) * 1.3)` | `TestEstimateTokensWordMethod.test_basic_word_counting` |
| Empty string returns 0 | Both methods tested |
| Unicode handled | `TestEstimateTokensEdgeCases.test_unicode_*` |
| `TypeError` for None | `TestEstimateTokensTypeValidation.test_none_raises_typeerror` |
| `TypeError` for non-string | `TestEstimateTokensTypeValidation.test_*_raises_typeerror` |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/clams/utils/tokens.py` | Create | New token estimation module |
| `src/clams/utils/__init__.py` | Modify | Export `estimate_tokens` |
| `tests/utils/test_tokens.py` | Create | Comprehensive tests |

## Alternative Approaches Considered

### 1. Enhance `context/tokens.py` with method parameter

**Pros:** No new module, reuses existing code
**Cons:**
- Mixes general utility with context-specific logic
- Other modules would need to import from `context`
- More changes to existing code

**Decision:** Rejected - separation of concerns is cleaner

### 2. Use tiktoken or similar library for exact counts

**Pros:** Accurate token counts
**Cons:**
- External dependency
- API calls or model downloads required
- Overkill for heuristic budget limits

**Decision:** Rejected - spec explicitly excludes exact counting

### 3. Only implement character-based method

**Pros:** Simpler API
**Cons:**
- Less flexible for prose-heavy content
- Spec explicitly requires both methods

**Decision:** Rejected - spec requires both methods

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Unicode underestimation | Document in docstring; acceptable for English-focused use |
| Integer division edge cases (0 for < 4 chars) | Document behavior; use `max(0, ...)` |
| Method parameter typos | Type checker catches invalid literals |

## Acceptance Criteria Verification

| Criterion | Implementation |
|-----------|----------------|
| `src/clams/utils/tokens.py` exists | New file created |
| Function signature matches spec | `estimate_tokens(text: str, method: Literal["chars", "words"] = "chars") -> int` |
| Character-based: `len(text) // 4` | Default method implementation |
| Word-based: `int(len(text.split()) * 1.3)` | Alternative method implementation |
| Empty string returns 0 | `max(0, ...)` ensures this |
| Unicode handled | Counts code points/words normally |
| `TypeError` for None/non-string | Explicit type check at start |
| Tests verify both methods | Separate test classes |
| Tests verify edge cases | Dedicated edge case class |
| Docstring explains formulas | Comprehensive docstring with examples |

## Implementation Order

1. Create `src/clams/utils/tokens.py` with `estimate_tokens()`
2. Update `src/clams/utils/__init__.py` to export function
3. Create `tests/utils/test_tokens.py` with all test classes
4. Run tests to verify implementation
5. Run mypy to verify type annotations

## Estimated Effort

- Implementation: ~30 minutes
- Tests: ~45 minutes
- Documentation/review: ~15 minutes

**Total: ~1.5 hours**
