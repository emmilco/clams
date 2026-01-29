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
