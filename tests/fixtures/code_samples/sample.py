"""Sample Python module for testing code parsing."""

# Module-level constant
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30


def simple_function(x: int, y: int) -> int:
    """Add two numbers together.

    Args:
        x: First number
        y: Second number

    Returns:
        Sum of x and y
    """
    return x + y


def complex_function(items: list[int]) -> int:
    """Calculate sum with branching logic.

    This function has higher cyclomatic complexity.
    """
    total = 0
    for item in items:
        if item > 0:
            total += item
        elif item < 0:
            total -= item
        else:
            continue

    while total > 100:
        total = total // 2

    return total


class Calculator:
    """A simple calculator class."""

    def __init__(self, initial_value: int = 0):
        """Initialize calculator with optional initial value."""
        self.value = initial_value

    def add(self, x: int) -> int:
        """Add to current value."""
        self.value += x
        return self.value

    def multiply(self, x: int) -> int:
        """Multiply current value."""
        if x == 0:
            self.value = 0
        else:
            self.value *= x
        return self.value
