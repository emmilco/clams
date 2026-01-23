"""Tests for validation decorators.

Tests that decorators work with both sync and async functions,
preserve function signatures, and provide clear error messages.
"""

import pytest

from clams.utils.validation import validate_datetime_params, validate_numeric_range


class TestValidateDatetimeParams:
    """Tests for validate_datetime_params decorator."""

    def test_valid_datetime_passes(self) -> None:
        """Valid ISO 8601 datetime passes validation."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query("2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    def test_valid_datetime_without_timezone(self) -> None:
        """Valid ISO 8601 without timezone passes validation."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query("2024-12-15T10:30:00")
        assert result == "2024-12-15T10:30:00"

    def test_valid_date_only(self) -> None:
        """Valid date-only format passes validation."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query("2024-12-15")
        assert result == "2024-12-15"

    def test_invalid_datetime_raises(self) -> None:
        """Invalid datetime raises ValueError with clear message."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        with pytest.raises(ValueError) as exc_info:
            query("invalid")
        assert "since" in str(exc_info.value)
        assert "ISO 8601" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    def test_empty_string_raises(self) -> None:
        """Empty string raises ValueError."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        with pytest.raises(ValueError, match="since"):
            query("")

    def test_none_allowed(self) -> None:
        """None value is allowed for optional params."""

        @validate_datetime_params("since")
        def query(since: str | None = None) -> str | None:
            return since

        assert query(None) is None
        assert query() is None

    def test_multiple_params(self) -> None:
        """Multiple params can be validated."""

        @validate_datetime_params("since", "until")
        def query(
            since: str | None = None, until: str | None = None
        ) -> tuple[str | None, str | None]:
            return (since, until)

        result = query("2024-01-01", "2024-12-31")
        assert result == ("2024-01-01", "2024-12-31")

    def test_multiple_params_one_invalid(self) -> None:
        """Error message includes the specific invalid parameter name."""

        @validate_datetime_params("since", "until")
        def query(
            since: str | None = None, until: str | None = None
        ) -> tuple[str | None, str | None]:
            return (since, until)

        with pytest.raises(ValueError, match="until"):
            query("2024-01-01", "invalid")

    def test_preserves_function_name(self) -> None:
        """Decorator preserves function name."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        assert query.__name__ == "query"

    def test_preserves_docstring(self) -> None:
        """Decorator preserves function docstring."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            """Query with since parameter."""
            return since

        assert query.__doc__ == "Query with since parameter."

    def test_positional_arg(self) -> None:
        """Validation works with positional arguments."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query("2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    def test_keyword_arg(self) -> None:
        """Validation works with keyword arguments."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        result = query(since="2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    def test_non_string_type_raises(self) -> None:
        """Non-string type raises ValueError."""

        @validate_datetime_params("since")
        def query(since: str) -> str:
            return since

        with pytest.raises(ValueError, match="must be a string"):
            query(12345)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_async_function(self) -> None:
        """Decorator works with async functions."""

        @validate_datetime_params("since")
        async def query(since: str) -> str:
            return since

        result = await query("2024-12-15T10:30:00+00:00")
        assert result == "2024-12-15T10:30:00+00:00"

    @pytest.mark.asyncio
    async def test_async_function_invalid(self) -> None:
        """Async function raises on invalid datetime."""

        @validate_datetime_params("since")
        async def query(since: str) -> str:
            return since

        with pytest.raises(ValueError, match="since"):
            await query("invalid")

    @pytest.mark.asyncio
    async def test_async_function_preserves_name(self) -> None:
        """Async decorated function preserves name."""

        @validate_datetime_params("since")
        async def query(since: str) -> str:
            return since

        assert query.__name__ == "query"


class TestValidateNumericRange:
    """Tests for validate_numeric_range decorator."""

    def test_value_in_range_passes(self) -> None:
        """Value in range passes validation."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        assert connect(30.0) == 30.0
        assert connect(0.1) == 0.1
        assert connect(300.0) == 300.0

    def test_value_below_range_raises(self) -> None:
        """Value below range raises ValueError."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError) as exc_info:
            connect(0.0)
        assert "timeout" in str(exc_info.value)
        assert "[0.1, 300.0]" in str(exc_info.value)

    def test_value_above_range_raises(self) -> None:
        """Value above range raises ValueError."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError) as exc_info:
            connect(500.0)
        assert "timeout" in str(exc_info.value)
        assert "500.0" in str(exc_info.value)

    def test_none_allowed(self) -> None:
        """None value is allowed for optional params."""

        @validate_numeric_range("limit", 1, 100)
        def fetch(limit: int | None = None) -> int | None:
            return limit

        assert fetch(None) is None
        assert fetch() is None

    def test_int_values(self) -> None:
        """Integer values work correctly."""

        @validate_numeric_range("limit", 1, 100)
        def fetch(limit: int = 10) -> int:
            return limit

        assert fetch(1) == 1
        assert fetch(50) == 50
        assert fetch(100) == 100

    def test_int_out_of_range(self) -> None:
        """Integer out of range raises ValueError."""

        @validate_numeric_range("limit", 1, 100)
        def fetch(limit: int = 10) -> int:
            return limit

        with pytest.raises(ValueError, match="limit"):
            fetch(0)
        with pytest.raises(ValueError, match="limit"):
            fetch(101)

    def test_preserves_function_name(self) -> None:
        """Decorator preserves function name."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            return timeout

        assert connect.__name__ == "connect"

    def test_preserves_docstring(self) -> None:
        """Decorator preserves function docstring."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float = 30.0) -> float:
            """Connect with timeout."""
            return timeout

        assert connect.__doc__ == "Connect with timeout."

    def test_positional_arg(self) -> None:
        """Validation works with positional arguments."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float) -> float:
            return timeout

        assert connect(30.0) == 30.0

    def test_keyword_arg(self) -> None:
        """Validation works with keyword arguments."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float) -> float:
            return timeout

        assert connect(timeout=30.0) == 30.0

    def test_non_numeric_type_raises(self) -> None:
        """Non-numeric type raises ValueError."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        def connect(timeout: float) -> float:
            return timeout

        with pytest.raises(ValueError, match="must be numeric"):
            connect("30.0")  # type: ignore[arg-type]

    def test_negative_range(self) -> None:
        """Negative ranges work correctly."""

        @validate_numeric_range("temperature", -40.0, -10.0)
        def set_temp(temperature: float) -> float:
            return temperature

        assert set_temp(-25.0) == -25.0
        with pytest.raises(ValueError):
            set_temp(0.0)

    @pytest.mark.asyncio
    async def test_async_function(self) -> None:
        """Decorator works with async functions."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        async def connect(timeout: float = 30.0) -> float:
            return timeout

        result = await connect(30.0)
        assert result == 30.0

    @pytest.mark.asyncio
    async def test_async_function_invalid(self) -> None:
        """Async function raises on invalid value."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        async def connect(timeout: float = 30.0) -> float:
            return timeout

        with pytest.raises(ValueError, match="timeout"):
            await connect(0.0)

    @pytest.mark.asyncio
    async def test_async_function_preserves_name(self) -> None:
        """Async decorated function preserves name."""

        @validate_numeric_range("timeout", 0.1, 300.0)
        async def connect(timeout: float = 30.0) -> float:
            return timeout

        assert connect.__name__ == "connect"


class TestCombinedDecorators:
    """Tests for combining multiple decorators."""

    def test_datetime_then_numeric(self) -> None:
        """Can combine datetime and numeric validators."""

        @validate_datetime_params("since")
        @validate_numeric_range("limit", 1, 100)
        def query(since: str, limit: int = 10) -> tuple[str, int]:
            return (since, limit)

        result = query("2024-12-15", 50)
        assert result == ("2024-12-15", 50)

    def test_combined_datetime_invalid(self) -> None:
        """Combined decorator catches datetime error."""

        @validate_datetime_params("since")
        @validate_numeric_range("limit", 1, 100)
        def query(since: str, limit: int = 10) -> tuple[str, int]:
            return (since, limit)

        with pytest.raises(ValueError, match="since"):
            query("invalid", 50)

    def test_combined_numeric_invalid(self) -> None:
        """Combined decorator catches numeric error."""

        @validate_datetime_params("since")
        @validate_numeric_range("limit", 1, 100)
        def query(since: str, limit: int = 10) -> tuple[str, int]:
            return (since, limit)

        with pytest.raises(ValueError, match="limit"):
            query("2024-12-15", 200)
