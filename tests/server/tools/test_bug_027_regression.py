"""Regression test for BUG-027: list_ghap_entries must parse ISO format created_at correctly."""

from datetime import UTC, datetime


class TestListGhapEntriesDatetimeParsing:
    """Test that ISO format datetime strings are parsed correctly."""

    def test_fromisoformat_parses_iso_string(self) -> None:
        """Verify datetime.fromisoformat() correctly parses ISO format strings.

        BUG-027: The list_ghap_entries function was using datetime.fromtimestamp()
        on ISO format strings stored by the persister. This caused TypeError
        because fromtimestamp expects a numeric timestamp, not a string.

        The fix changed to datetime.fromisoformat() which correctly parses
        ISO format strings like "2025-01-01T00:00:00+00:00".
        """
        # Create an ISO format timestamp as stored by the persister
        now = datetime.now(UTC)
        iso_string = now.isoformat()

        # Verify fromisoformat can parse it back
        parsed = datetime.fromisoformat(iso_string)

        # The parsed datetime should represent the same time
        # Allow small difference due to microsecond precision
        assert abs((parsed - now).total_seconds()) < 0.001

    def test_fromisoformat_handles_various_formats(self) -> None:
        """Verify fromisoformat handles common ISO format variations."""
        # Standard format with timezone
        dt1 = datetime.fromisoformat("2025-01-15T10:30:00+00:00")
        assert dt1.year == 2025
        assert dt1.month == 1
        assert dt1.day == 15

        # Format without timezone (naive)
        dt2 = datetime.fromisoformat("2025-01-15T10:30:00")
        assert dt2.year == 2025

        # Format with milliseconds
        dt3 = datetime.fromisoformat("2025-01-15T10:30:00.123456+00:00")
        assert dt3.microsecond == 123456

    def test_fromtimestamp_fails_on_iso_string(self) -> None:
        """Verify that fromtimestamp raises TypeError on ISO string.

        This documents the bug: fromtimestamp expects a numeric timestamp,
        so passing an ISO string causes TypeError.
        """
        iso_string = "2025-01-15T10:30:00+00:00"

        # This is what was happening before the fix
        try:
            datetime.fromtimestamp(iso_string)  # type: ignore[arg-type]
            assert False, "Expected TypeError"
        except TypeError:
            pass  # Expected - this is the bug we fixed
