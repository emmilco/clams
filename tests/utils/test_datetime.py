"""Tests for datetime serialization/deserialization utilities.

Reference: R11-A - Centralized Datetime Utilities
Reference: BUG-027 - datetime stored as ISO string but read expecting numeric timestamp
"""

from datetime import datetime, timezone, timedelta
import pytest

from clams.utils.datetime import serialize_datetime, deserialize_datetime


class TestSerializeDatetime:
    """Tests for serialize_datetime function."""

    def test_serialize_utc_datetime(self) -> None:
        """Serialize UTC-aware datetime to ISO 8601 string."""
        dt = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T10:30:00+00:00"

    def test_serialize_naive_datetime_assumes_utc(self) -> None:
        """Naive datetime is assumed to be UTC."""
        dt = datetime(2024, 12, 14, 10, 30, 0)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T10:30:00+00:00"

    def test_serialize_datetime_with_microseconds(self) -> None:
        """Microseconds are preserved in serialization."""
        dt = datetime(2024, 12, 14, 10, 30, 0, 123456, tzinfo=timezone.utc)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T10:30:00.123456+00:00"

    def test_serialize_datetime_with_other_timezone(self) -> None:
        """Non-UTC timezone is preserved in serialization."""
        # UTC+5:30 (e.g., India Standard Time)
        ist = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2024, 12, 14, 16, 0, 0, tzinfo=ist)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T16:00:00+05:30"

    def test_serialize_datetime_midnight(self) -> None:
        """Midnight time serializes correctly."""
        dt = datetime(2024, 12, 14, 0, 0, 0, tzinfo=timezone.utc)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T00:00:00+00:00"

    def test_serialize_datetime_end_of_day(self) -> None:
        """End of day serializes correctly."""
        dt = datetime(2024, 12, 14, 23, 59, 59, 999999, tzinfo=timezone.utc)
        result = serialize_datetime(dt)
        assert result == "2024-12-14T23:59:59.999999+00:00"


class TestDeserializeDatetime:
    """Tests for deserialize_datetime function."""

    def test_deserialize_iso_string_with_utc(self) -> None:
        """Deserialize ISO 8601 string with UTC timezone."""
        result = deserialize_datetime("2024-12-14T10:30:00+00:00")
        expected = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_deserialize_naive_iso_string_assumes_utc(self) -> None:
        """Naive ISO string is assumed to be UTC."""
        result = deserialize_datetime("2024-12-14T10:30:00")
        expected = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_deserialize_iso_string_with_microseconds(self) -> None:
        """Microseconds are preserved in deserialization."""
        result = deserialize_datetime("2024-12-14T10:30:00.123456+00:00")
        expected = datetime(2024, 12, 14, 10, 30, 0, 123456, tzinfo=timezone.utc)
        assert result == expected

    def test_deserialize_iso_string_with_z_suffix(self) -> None:
        """ISO string with Z suffix (Zulu time) is parsed correctly."""
        # Python 3.11+ supports Z suffix natively in fromisoformat
        # For older versions, this test documents expected behavior
        try:
            result = deserialize_datetime("2024-12-14T10:30:00Z")
            expected = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
            assert result == expected
        except ValueError:
            # Python < 3.11 doesn't support Z suffix
            pytest.skip("Z suffix not supported in Python < 3.11")

    def test_deserialize_unix_timestamp_int(self) -> None:
        """Deserialize Unix timestamp as integer."""
        # 2024-12-14T10:30:00 UTC
        timestamp = 1734172200
        result = deserialize_datetime(timestamp)
        expected = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_deserialize_unix_timestamp_float(self) -> None:
        """Deserialize Unix timestamp as float with microseconds."""
        timestamp = 1734172200.123456
        result = deserialize_datetime(timestamp)
        assert result.tzinfo == timezone.utc
        # Float precision may vary slightly
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 14
        assert result.hour == 10
        assert result.minute == 30

    def test_deserialize_zero_timestamp(self) -> None:
        """Deserialize Unix epoch (timestamp 0)."""
        result = deserialize_datetime(0)
        expected = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_deserialize_negative_timestamp(self) -> None:
        """Deserialize negative timestamp (before Unix epoch)."""
        # 1969-12-31 23:00:00 UTC
        result = deserialize_datetime(-3600)
        expected = datetime(1969, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_deserialize_invalid_iso_string_raises_value_error(self) -> None:
        """Invalid ISO string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse ISO datetime string"):
            deserialize_datetime("not-a-date")

    def test_deserialize_date_only_iso_string(self) -> None:
        """Date-only ISO string deserializes to midnight UTC (Python 3.11+)."""
        result = deserialize_datetime("2024-12-14")
        expected = datetime(2024, 12, 14, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected
        assert result.tzinfo == timezone.utc

    def test_deserialize_malformed_iso_string_raises_value_error(self) -> None:
        """Malformed ISO string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse ISO datetime string"):
            deserialize_datetime("2024-13-45")  # Invalid month/day

    def test_deserialize_invalid_type_raises_type_error(self) -> None:
        """Non-string/numeric type raises TypeError."""
        with pytest.raises(TypeError, match="Cannot deserialize datetime from"):
            deserialize_datetime(None)  # type: ignore[arg-type]

    def test_deserialize_list_raises_type_error(self) -> None:
        """List type raises TypeError."""
        with pytest.raises(TypeError, match="Cannot deserialize datetime from list"):
            deserialize_datetime([2024, 12, 14])  # type: ignore[arg-type]

    def test_deserialize_dict_raises_type_error(self) -> None:
        """Dict type raises TypeError."""
        with pytest.raises(TypeError, match="Cannot deserialize datetime from dict"):
            deserialize_datetime({"year": 2024})  # type: ignore[arg-type]


class TestRoundTrip:
    """Tests for serialization/deserialization round-trip consistency."""

    def test_round_trip_utc_datetime(self) -> None:
        """UTC datetime survives round-trip serialization."""
        original = datetime(2024, 12, 14, 10, 30, 0, tzinfo=timezone.utc)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == original

    def test_round_trip_naive_datetime(self) -> None:
        """Naive datetime round-trips as UTC."""
        original = datetime(2024, 12, 14, 10, 30, 0)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        # Original was naive, but deserialized is UTC-aware
        expected = original.replace(tzinfo=timezone.utc)
        assert deserialized == expected

    def test_round_trip_with_microseconds(self) -> None:
        """Microseconds are preserved through round-trip."""
        original = datetime(2024, 12, 14, 10, 30, 0, 123456, tzinfo=timezone.utc)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == original
        assert deserialized.microsecond == 123456

    def test_round_trip_other_timezone(self) -> None:
        """Non-UTC timezone is preserved through round-trip."""
        # UTC-5 (e.g., Eastern Standard Time)
        est = timezone(timedelta(hours=-5))
        original = datetime(2024, 12, 14, 5, 30, 0, tzinfo=est)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        # The datetime should be equivalent (same instant in time)
        assert deserialized == original

    @pytest.mark.parametrize("year", [1970, 2000, 2024, 2050, 2100])
    def test_round_trip_various_years(self, year: int) -> None:
        """Various years round-trip correctly."""
        original = datetime(year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        serialized = serialize_datetime(original)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == original


class TestTimezoneHandling:
    """Tests for timezone handling edge cases."""

    def test_utc_is_default_for_naive_serialize(self) -> None:
        """Naive datetime serializes with UTC timezone."""
        naive = datetime(2024, 12, 14, 10, 30, 0)
        result = serialize_datetime(naive)
        assert "+00:00" in result

    def test_utc_is_default_for_naive_deserialize(self) -> None:
        """Naive ISO string deserializes with UTC timezone."""
        result = deserialize_datetime("2024-12-14T10:30:00")
        assert result.tzinfo == timezone.utc

    def test_positive_offset_timezone(self) -> None:
        """Positive timezone offset is preserved."""
        # UTC+9 (e.g., Japan Standard Time)
        jst = timezone(timedelta(hours=9))
        dt = datetime(2024, 12, 14, 19, 30, 0, tzinfo=jst)
        serialized = serialize_datetime(dt)
        assert "+09:00" in serialized
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_negative_offset_timezone(self) -> None:
        """Negative timezone offset is preserved."""
        # UTC-8 (e.g., Pacific Standard Time)
        pst = timezone(timedelta(hours=-8))
        dt = datetime(2024, 12, 14, 2, 30, 0, tzinfo=pst)
        serialized = serialize_datetime(dt)
        assert "-08:00" in serialized
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_half_hour_offset_timezone(self) -> None:
        """Half-hour timezone offset is preserved."""
        # UTC+5:30 (e.g., India Standard Time)
        ist = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2024, 12, 14, 16, 0, 0, tzinfo=ist)
        serialized = serialize_datetime(dt)
        assert "+05:30" in serialized
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_old_date(self) -> None:
        """Very old dates can be serialized/deserialized."""
        # Year 1000
        dt = datetime(1000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        serialized = serialize_datetime(dt)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_far_future_date(self) -> None:
        """Far future dates can be serialized/deserialized."""
        # Year 9999 (max for Python datetime)
        dt = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        serialized = serialize_datetime(dt)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_leap_second_boundary(self) -> None:
        """Dates near leap second boundaries work correctly."""
        # 2016-12-31 23:59:59 UTC (just before leap second)
        dt = datetime(2016, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        serialized = serialize_datetime(dt)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_leap_year_feb_29(self) -> None:
        """Leap year February 29 works correctly."""
        dt = datetime(2024, 2, 29, 12, 0, 0, tzinfo=timezone.utc)
        serialized = serialize_datetime(dt)
        deserialized = deserialize_datetime(serialized)
        assert deserialized == dt

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse ISO datetime string"):
            deserialize_datetime("")

    def test_whitespace_string_raises_value_error(self) -> None:
        """Whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse ISO datetime string"):
            deserialize_datetime("   ")
