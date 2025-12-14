"""Regression tests for BUG-054: Test isolation fixture for resource leaks.

This test verifies that the thread_leak_tracker fixture properly detects and
reports leaked threads. Prior to this fix, leaked resources would cause
pytest to hang silently during shutdown.

BUG-054: Test isolation fixture for resource leaks
Root cause: No automatic resource tracking or cleanup mechanism in tests.

Note: Async task leak detection was attempted but removed due to complexity
with pytest-asyncio's event loop management. Async task leaks will manifest
as test hangs or pytest-asyncio warnings, which are easier to debug than
silent hangs.
"""

import threading
import time

import pytest


class TestThreadLeakTracker:
    """Verify the thread leak tracker works correctly."""

    @pytest.mark.no_resource_tracking
    def test_clean_test_passes(self) -> None:
        """A test that cleans up threads properly should pass."""
        result = 1 + 1
        assert result == 2

    @pytest.mark.no_resource_tracking
    def test_joined_thread_does_not_leak(self) -> None:
        """A thread that is properly joined should not leak."""
        completed = threading.Event()

        def quick_worker() -> None:
            time.sleep(0.01)
            completed.set()

        thread = threading.Thread(target=quick_worker, name="quick-worker")
        thread.start()
        thread.join(timeout=1.0)
        assert completed.is_set()


class TestLeakDetectionMechanism:
    """Test that the detection mechanism works correctly."""

    @pytest.mark.no_resource_tracking
    def test_thread_leak_tracker_exists(self) -> None:
        """Verify the thread_leak_tracker fixture is defined in conftest."""
        from tests import conftest

        assert hasattr(conftest, "thread_leak_tracker")
        assert hasattr(conftest, "_is_tracked_thread")
        assert hasattr(conftest, "_check_thread_leaks")

    @pytest.mark.no_resource_tracking
    def test_ignored_thread_prefixes_configured(self) -> None:
        """Verify known background threads are configured to be ignored."""
        from tests.conftest import _IGNORED_THREAD_PREFIXES

        # These prefixes should be ignored to avoid false positives
        assert "MainThread" in _IGNORED_THREAD_PREFIXES
        assert "ThreadPoolExecutor" in _IGNORED_THREAD_PREFIXES
        assert "Tokenizer" in _IGNORED_THREAD_PREFIXES
        assert "torch" in _IGNORED_THREAD_PREFIXES
        assert "Thread-" in _IGNORED_THREAD_PREFIXES

    @pytest.mark.no_resource_tracking
    def test_daemon_threads_not_tracked(self) -> None:
        """Verify daemon threads are excluded from tracking."""
        from tests.conftest import _is_tracked_thread

        daemon_thread = threading.Thread(target=lambda: None, daemon=True)
        assert not _is_tracked_thread(daemon_thread)

    @pytest.mark.no_resource_tracking
    def test_main_thread_not_tracked(self) -> None:
        """Verify MainThread is excluded from tracking."""
        from tests.conftest import _is_tracked_thread

        main_thread = threading.main_thread()
        assert not _is_tracked_thread(main_thread)

    @pytest.mark.no_resource_tracking
    def test_custom_named_thread_is_tracked(self) -> None:
        """Verify custom-named non-daemon threads are tracked."""
        from tests.conftest import _is_tracked_thread

        custom_thread = threading.Thread(
            target=lambda: None, name="my-worker", daemon=False
        )
        assert _is_tracked_thread(custom_thread)

    @pytest.mark.no_resource_tracking
    def test_generic_numbered_threads_not_tracked(self) -> None:
        """Verify Thread-N style threads are not tracked (third-party libs)."""
        from tests.conftest import _is_tracked_thread

        # These are typically created by third-party libraries
        generic_thread = threading.Thread(
            target=lambda: None, name="Thread-1", daemon=False
        )
        assert not _is_tracked_thread(generic_thread)


class TestLeakDetectionLogic:
    """Verify the leak detection logic works correctly."""

    @pytest.mark.no_resource_tracking
    def test_leaked_thread_detection_logic(self) -> None:
        """Verify that leaked threads are correctly identified."""
        from tests.conftest import _check_thread_leaks, _is_tracked_thread

        baseline_threads = {
            t for t in threading.enumerate() if _is_tracked_thread(t)
        }

        completed = threading.Event()

        def quick_worker() -> None:
            completed.wait(timeout=1.0)

        # Create a thread (simulating a leak)
        thread = threading.Thread(
            target=quick_worker, name="test-leak-thread", daemon=False
        )
        thread.start()

        # Check that the new thread is detected
        error_parts = _check_thread_leaks(baseline_threads)

        assert len(error_parts) == 1, "Should detect exactly one leaked thread"
        assert "test-leak-thread" in error_parts[0]

        # Clean up
        completed.set()
        thread.join(timeout=1.0)

    @pytest.mark.no_resource_tracking
    def test_multiple_leaked_threads_detected(self) -> None:
        """Verify multiple leaked threads are all detected."""
        from tests.conftest import _check_thread_leaks, _is_tracked_thread

        baseline_threads = {
            t for t in threading.enumerate() if _is_tracked_thread(t)
        }

        completed = threading.Event()

        def quick_worker() -> None:
            completed.wait(timeout=1.0)

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=quick_worker, name=f"leak-thread-{i}", daemon=False
            )
            thread.start()
            threads.append(thread)

        # Check detection
        error_parts = _check_thread_leaks(baseline_threads)

        assert len(error_parts) == 1, "Should have one error message"
        assert "3 thread(s)" in error_parts[0], "Should report 3 leaked threads"

        # Clean up
        completed.set()
        for thread in threads:
            thread.join(timeout=1.0)

    @pytest.mark.no_resource_tracking
    def test_cleaned_thread_not_reported(self) -> None:
        """Verify properly cleaned threads are not reported as leaks."""
        from tests.conftest import _check_thread_leaks, _is_tracked_thread

        baseline_threads = {
            t for t in threading.enumerate() if _is_tracked_thread(t)
        }

        completed = threading.Event()

        def quick_worker() -> None:
            completed.set()

        # Create and properly clean up a thread
        thread = threading.Thread(
            target=quick_worker, name="cleaned-thread", daemon=False
        )
        thread.start()
        thread.join(timeout=1.0)

        # No leaks should be detected
        error_parts = _check_thread_leaks(baseline_threads)
        assert len(error_parts) == 0, "Should not detect any leaks"


class TestNoResourceTrackingMarker:
    """Verify the opt-out marker works correctly."""

    @pytest.mark.no_resource_tracking
    def test_marker_disables_tracking(self) -> None:
        """Tests with no_resource_tracking marker should skip leak checking.

        Note: This test itself uses the marker, so if it passes, the marker
        is working. We can't directly test that leaks are ignored without
        causing an actual leak in a non-marked test.
        """
        # This test simply verifies the marker is recognized
        # The fixture will yield early when it sees the marker
        pass


class TestRealWorldScenarios:
    """Test scenarios that match the original bug reports."""

    @pytest.mark.no_resource_tracking
    def test_background_worker_pattern_with_cleanup(self) -> None:
        """Test the common pattern of background workers with proper cleanup."""
        results: list[int] = []
        should_stop = threading.Event()

        def background_worker() -> None:
            while not should_stop.is_set():
                results.append(1)
                time.sleep(0.01)

        # Start worker
        worker = threading.Thread(
            target=background_worker, name="background-worker"
        )
        worker.start()

        # Let it run briefly
        time.sleep(0.05)

        # Signal stop and wait
        should_stop.set()
        worker.join(timeout=1.0)

        assert len(results) > 0, "Worker should have produced some results"
        assert not worker.is_alive(), "Worker should have stopped"

    @pytest.mark.no_resource_tracking
    def test_thread_pool_pattern_with_cleanup(self) -> None:
        """Test pattern where multiple threads process work items."""
        from queue import Empty, Queue

        work_queue: Queue[int | None] = Queue()
        results: list[int] = []
        results_lock = threading.Lock()

        def worker() -> None:
            while True:
                try:
                    item = work_queue.get(timeout=0.1)
                    if item is None:
                        break
                    with results_lock:
                        results.append(item * 2)
                except Empty:
                    continue

        # Start workers
        workers = []
        for i in range(3):
            w = threading.Thread(target=worker, name=f"pool-worker-{i}")
            w.start()
            workers.append(w)

        # Add work
        for i in range(5):
            work_queue.put(i)

        # Signal workers to stop
        for _ in workers:
            work_queue.put(None)

        # Wait for completion
        for w in workers:
            w.join(timeout=1.0)

        assert len(results) == 5, "All work items should be processed"
