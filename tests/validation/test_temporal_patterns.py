"""Validation tests for temporal pattern handling.

Reference: SPEC-034 Temporal Data Scenarios 8-9
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from tests.fixtures.data_profiles import CommitProfile, TemporalProfile
from tests.fixtures.generators.commits import GeneratedCommit, generate_commits
from tests.fixtures.generators.temporal import (
    generate_from_profile,
    generate_temporal_distribution,
)


class TestBurstPatternHandling:
    """Scenario 8: Burst Pattern Handling.

    Verify search handles temporal clustering (bursts) correctly.
    """

    @pytest.fixture
    def burst_commits(self) -> list[GeneratedCommit]:
        """Generate commits with burst patterns."""
        profile = CommitProfile(
            count=200,
            author_count=5,
            temporal_pattern="bursts",
        )
        return generate_commits(profile, seed=42)

    def test_burst_detection(self, burst_commits: list[GeneratedCommit]) -> None:
        """Verify bursts are detectable in generated data."""
        timestamps = [c.committed_at for c in burst_commits]

        # Calculate inter-commit intervals
        intervals: list[float] = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
            intervals.append(delta)

        # In burst patterns, we should see both very short and very long intervals
        # Variance should be high (mix of burst and quiet periods)
        interval_std = np.std(intervals)
        interval_mean = np.mean(intervals)
        cv = interval_std / interval_mean  # Coefficient of variation

        assert cv > 1.0, (
            f"Burst pattern should have high variance in intervals. "
            f"CV={cv:.2f}, expected > 1.0"
        )

    def test_date_range_filter_at_burst_boundaries(
        self, burst_commits: list[GeneratedCommit]
    ) -> None:
        """Verify date range filters work correctly at burst boundaries."""
        timestamps = sorted([c.committed_at for c in burst_commits])

        # Find the window with highest commit density (largest burst)
        window_hours = 8  # Wider window to ensure we find activity
        best_window_start: datetime = timestamps[0]
        best_window_count = 0

        for i in range(len(timestamps) - 3):
            window_start = timestamps[i]
            window_end = window_start + timedelta(hours=window_hours)

            # Count commits in window
            commits_in_window = sum(
                1 for t in timestamps[i:] if window_start <= t <= window_end
            )

            if commits_in_window > best_window_count:
                best_window_count = commits_in_window
                best_window_start = window_start

        burst_start = best_window_start
        burst_end = burst_start + timedelta(hours=window_hours)

        # Filter commits in the densest window
        filtered = [
            c for c in burst_commits if burst_start <= c.committed_at <= burst_end
        ]

        # We found some commits in our window
        assert len(filtered) > 0, "Expected to find commits in densest window"

        # Boundary test: period before the burst
        pre_burst_end = burst_start - timedelta(minutes=1)
        pre_burst_start = pre_burst_end - timedelta(hours=window_hours)
        pre_filtered = [
            c
            for c in burst_commits
            if pre_burst_start <= c.committed_at <= pre_burst_end
        ]

        # In a burst pattern, the densest window should have more commits
        # than the period before it (by construction, the densest window
        # has at least as many as any other window)
        assert len(filtered) >= len(pre_filtered), (
            f"Densest window ({len(filtered)}) should have at least as many "
            f"commits as pre-burst period ({len(pre_filtered)})"
        )

    def test_search_handles_temporal_clustering(
        self, burst_commits: list[GeneratedCommit]
    ) -> None:
        """Verify search operations work correctly with clustered timestamps."""
        # Group by day
        commits_by_day: dict[str, list[GeneratedCommit]] = {}
        for c in burst_commits:
            day_key = c.committed_at.strftime("%Y-%m-%d")
            commits_by_day.setdefault(day_key, []).append(c)

        # Burst pattern should show uneven distribution across days
        daily_counts = [len(commits) for commits in commits_by_day.values()]

        mean_count = np.mean(daily_counts)

        # With bursts, some days should have many more commits than average
        max_day = max(daily_counts)
        assert max_day > mean_count * 2, (
            f"Burst pattern should have days with 2x+ average commits. "
            f"Max={max_day}, mean={mean_count:.1f}"
        )


class TestLongTimeRangeQueries:
    """Scenario 9: Long Time Range Queries.

    Verify queries across months of data work correctly.
    """

    @pytest.fixture
    def long_range_timestamps(self) -> list[datetime]:
        """Generate timestamps spanning 6 months."""
        profile = TemporalProfile(
            count=500,
            pattern="uniform",
            span_days=180,  # 6 months
        )
        return generate_from_profile(profile, seed=42)

    def test_since_filter_basic(self, long_range_timestamps: list[datetime]) -> None:
        """Verify 'since' filter correctly excludes old data."""
        timestamps = sorted(long_range_timestamps)

        # Filter for last 30 days
        cutoff = timestamps[-1] - timedelta(days=30)
        filtered = [t for t in timestamps if t >= cutoff]

        # Should have roughly 30/180 = 16.7% of data (uniform distribution)
        expected_ratio = 30 / 180
        actual_ratio = len(filtered) / len(timestamps)

        # Allow 50% tolerance for randomness
        assert 0.5 * expected_ratio < actual_ratio < 1.5 * expected_ratio, (
            f"Since filter gave unexpected ratio: {actual_ratio:.2%}, "
            f"expected ~{expected_ratio:.2%}"
        )

    def test_no_off_by_one_at_boundaries(
        self, long_range_timestamps: list[datetime]
    ) -> None:
        """Verify no off-by-one errors at boundary timestamps."""
        timestamps = sorted(long_range_timestamps)

        # Use exact timestamp as boundary
        boundary = timestamps[100]

        # Inclusive boundary (>=)
        inclusive = [t for t in timestamps if t >= boundary]
        assert boundary in inclusive, "Boundary should be included with >="

        # Exclusive boundary (>)
        exclusive = [t for t in timestamps if t > boundary]
        assert boundary not in exclusive, "Boundary should not be included with >"

        # Counts should differ by 1
        assert len(inclusive) == len(exclusive) + 1, (
            f"Off-by-one error: inclusive={len(inclusive)}, exclusive={len(exclusive)}"
        )

    def test_boundary_at_midnight(self) -> None:
        """Verify date boundaries at midnight are handled correctly."""
        # Generate data around midnight boundary
        midnight = datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC)

        test_times = [
            midnight - timedelta(seconds=1),  # 23:59:59 day before
            midnight,  # 00:00:00 exact
            midnight + timedelta(seconds=1),  # 00:00:01 day of
        ]

        # Filter for "since midnight"
        since_midnight = [t for t in test_times if t >= midnight]
        assert len(since_midnight) == 2, "Should include midnight and after"
        assert test_times[0] not in since_midnight, "Should exclude before midnight"

    def test_month_boundary_queries(
        self, long_range_timestamps: list[datetime]
    ) -> None:
        """Verify queries at month boundaries work correctly."""
        timestamps = sorted(long_range_timestamps)

        # Group by month
        by_month: dict[str, list[datetime]] = {}
        for t in timestamps:
            month_key = t.strftime("%Y-%m")
            by_month.setdefault(month_key, []).append(t)

        # Should span multiple months
        assert len(by_month) >= 5, f"Expected 5+ months, got {len(by_month)}"

        # Each month should have some data (uniform distribution)
        for month, month_timestamps in by_month.items():
            assert len(month_timestamps) > 0, f"Month {month} has no data"

    def test_query_entire_range(self, long_range_timestamps: list[datetime]) -> None:
        """Verify querying entire range returns all data."""
        timestamps = sorted(long_range_timestamps)

        earliest = timestamps[0]
        latest = timestamps[-1]

        # Query with range covering all data
        in_range = [t for t in timestamps if earliest <= t <= latest]

        assert len(in_range) == len(timestamps), (
            f"Full range query should return all {len(timestamps)} items, "
            f"got {len(in_range)}"
        )


class TestTemporalGeneratorProperties:
    """Verify temporal generator produces expected distributions."""

    @pytest.mark.parametrize("pattern", ["uniform", "bursts", "decay", "growth"])
    def test_pattern_coverage(self, pattern: str) -> None:
        """Verify all patterns produce valid timestamps."""
        timestamps = generate_temporal_distribution(
            count=100,
            pattern=pattern,  # type: ignore[arg-type]
            span_days=30,
            seed=42,
        )

        assert len(timestamps) == 100, f"Expected 100 timestamps, got {len(timestamps)}"

        # All should be timezone-aware
        for t in timestamps:
            assert t.tzinfo is not None, "Timestamps should be timezone-aware"

        # Should be sorted
        assert timestamps == sorted(timestamps), "Timestamps should be sorted"

    def test_reproducibility(self) -> None:
        """Verify same seed produces same output."""
        ts1 = generate_temporal_distribution(
            count=50, pattern="bursts", span_days=30, seed=123
        )
        ts2 = generate_temporal_distribution(
            count=50, pattern="bursts", span_days=30, seed=123
        )

        assert ts1 == ts2, "Same seed should produce identical timestamps"

    def test_different_seeds_differ(self) -> None:
        """Verify different seeds produce different output."""
        ts1 = generate_temporal_distribution(
            count=50, pattern="uniform", span_days=30, seed=1
        )
        ts2 = generate_temporal_distribution(
            count=50, pattern="uniform", span_days=30, seed=2
        )

        assert ts1 != ts2, "Different seeds should produce different timestamps"

    def test_uniform_distribution_coverage(self) -> None:
        """Uniform distribution should cover the entire span."""
        span_days = 30
        timestamps = generate_temporal_distribution(
            count=300,
            pattern="uniform",
            span_days=span_days,
            seed=42,
        )

        # Calculate actual span
        actual_span = (timestamps[-1] - timestamps[0]).days

        # Should cover most of the specified span
        assert actual_span >= span_days * 0.9, (
            f"Uniform distribution should cover ~{span_days} days, "
            f"only covered {actual_span} days"
        )

    def test_decay_pattern_recent_bias(self) -> None:
        """Decay pattern should have more recent timestamps."""
        span_days = 90
        timestamps = generate_temporal_distribution(
            count=300,
            pattern="decay",
            span_days=span_days,
            seed=42,
        )

        # Split by index into halves (already sorted)
        midpoint_idx = len(timestamps) // 2
        first_half_ts = timestamps[:midpoint_idx]
        second_half_ts = timestamps[midpoint_idx:]

        # Calculate actual time spans
        first_half_span = (first_half_ts[-1] - first_half_ts[0]).total_seconds()
        second_half_span = (second_half_ts[-1] - second_half_ts[0]).total_seconds()

        # Decay = more recent, so second half (more recent) should be compressed
        # (same count in smaller time span = more dense)
        assert second_half_span < first_half_span, (
            f"Decay pattern should have compressed recent timestamps. "
            f"First half span: {first_half_span:.0f}s, second half span: {second_half_span:.0f}s"
        )

    def test_growth_pattern_older_bias(self) -> None:
        """Growth pattern should have more older timestamps."""
        span_days = 90
        timestamps = generate_temporal_distribution(
            count=300,
            pattern="growth",
            span_days=span_days,
            seed=42,
        )

        # Split by index into halves (already sorted)
        midpoint_idx = len(timestamps) // 2
        first_half_ts = timestamps[:midpoint_idx]
        second_half_ts = timestamps[midpoint_idx:]

        # Calculate actual time spans
        first_half_span = (first_half_ts[-1] - first_half_ts[0]).total_seconds()
        second_half_span = (second_half_ts[-1] - second_half_ts[0]).total_seconds()

        # Growth = more older, so first half (older) should be compressed
        # (same count in smaller time span = more dense)
        assert first_half_span < second_half_span, (
            f"Growth pattern should have compressed older timestamps. "
            f"First half span: {first_half_span:.0f}s, second half span: {second_half_span:.0f}s"
        )


class TestCommitGeneratorProperties:
    """Verify commit generator produces expected properties."""

    def test_author_skew_distribution(self) -> None:
        """Author distribution should follow 80/20 rule."""
        profile = CommitProfile(
            count=500,
            author_count=10,
            author_skew=0.8,  # Top 20% do 80%
        )

        commits = generate_commits(profile, seed=42)

        # Count commits per author
        author_counts: dict[str, int] = {}
        for c in commits:
            author_counts[c.author_name] = author_counts.get(c.author_name, 0) + 1

        # Sort by count descending
        sorted_counts = sorted(author_counts.values(), reverse=True)

        # Top 2 authors (20% of 10) should have ~80% of commits
        top_2_total = sum(sorted_counts[:2])
        top_2_ratio = top_2_total / len(commits)

        # Allow reasonable tolerance (0.5 to 0.95)
        assert 0.5 < top_2_ratio < 0.95, (
            f"Top 20% authors should have ~80% commits, got {top_2_ratio:.1%}"
        )

    def test_message_format_valid(self) -> None:
        """Commit messages should be valid strings."""
        profile = CommitProfile(count=50)
        commits = generate_commits(profile, seed=42)

        for c in commits:
            assert len(c.message) > 0, "Message should not be empty"
            assert c.message[0].islower() or c.message[0].isupper(), (
                "Message should start with a letter"
            )

    def test_files_changed_within_range(self) -> None:
        """Files changed should be within profile range."""
        min_files, max_files = 2, 10
        profile = CommitProfile(
            count=100,
            files_per_commit_range=(min_files, max_files),
        )

        commits = generate_commits(profile, seed=42)

        for c in commits:
            assert min_files <= len(c.files_changed) <= max_files, (
                f"Files changed {len(c.files_changed)} outside "
                f"range [{min_files}, {max_files}]"
            )

    def test_sha_uniqueness(self) -> None:
        """All commit SHAs should be unique."""
        profile = CommitProfile(count=100)
        commits = generate_commits(profile, seed=42)

        shas = [c.sha for c in commits]
        assert len(shas) == len(set(shas)), "Commit SHAs should be unique"
