# SPEC-046: Token Counting Utility (R15-C)

## Overview

Create a utility function for estimating token counts in text, to be used in response size assertions and context budget management.

## Background

To enforce response size limits effectively, we need a way to estimate token counts. This utility will be used by:
- Response size assertion tests
- Context assembly budget management
- Any future token-aware features

## Technical Design

### Function Signature

```python
from typing import Literal

def estimate_tokens(
    text: str,
    method: Literal["chars", "words"] = "chars"
) -> int:
    """Estimate the number of tokens in text.

    Args:
        text: The text to estimate tokens for
        method: Estimation method - "chars" (default) or "words"

    Returns:
        Estimated token count (always >= 0)

    Raises:
        TypeError: If text is not a string
    """
```

### Estimation Formulas

**Character-based (default)**: `max(0, len(text) // 4)`
- Approximates ~4 characters per token (common for English)
- Simple and fast
- Works well for mixed content

**Word-based**: `max(0, int(len(text.split()) * 1.3))`
- Counts words and adds 30% for subword tokenization
- Better for prose with clear word boundaries
- Less accurate for code or dense text

### Error Handling

- `None` input: raises `TypeError`
- Non-string input: raises `TypeError`
- Empty string: returns 0
- Whitespace-only string: returns 0 (chars) or small value (words)

## Requirements

### Functional Requirements

1. Create `src/clams/utils/tokens.py` with `estimate_tokens()` function
2. Support two estimation methods: character-based (default) and word-based
3. Handle edge cases: empty string (returns 0), whitespace, unicode
4. Raise `TypeError` for non-string inputs

### Non-Functional Requirements

1. No external API calls (local estimation only)
2. Fast execution (< 1ms for typical inputs)
3. Type annotations with Literal type for method parameter
4. Docstring with examples

## Acceptance Criteria

- [ ] `src/clams/utils/tokens.py` exists with `estimate_tokens()` function
- [ ] Function signature matches design: `estimate_tokens(text: str, method: Literal["chars", "words"] = "chars") -> int`
- [ ] Character-based: `len(text) // 4`
- [ ] Word-based: `int(len(text.split()) * 1.3)`
- [ ] Empty string returns 0
- [ ] Unicode text handled (counts characters/words normally)
- [ ] `TypeError` raised for None or non-string input
- [ ] Tests verify both estimation methods
- [ ] Tests verify edge cases (empty, whitespace, unicode)
- [ ] Docstring explains formulas and accuracy expectations

## Out of Scope

- Exact token counting (would require tokenizer)
- Model-specific token counting
- Token counting for images or other media
- Accuracy guarantees (this is a heuristic)
