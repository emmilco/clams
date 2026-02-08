"""Regression tests for BUG-034: Float timeout truncation.

Bug: int() cast on timeout values truncates floats (0.5 -> 0, 5.9 -> 5).
This is problematic because:
- Qdrant client accepts float timeouts at runtime
- The underlying httpx library supports float timeouts
- int(0.5) = 0 changes 500ms timeout to infinite timeout (in httpx, 0 = no timeout)

Fix: Remove int() cast, pass float timeout directly to AsyncQdrantClient.
"""

from unittest.mock import patch


class TestBug034FloatTimeoutRegression:
    """Regression tests for BUG-034: Float timeout should not be truncated."""

    def test_subsecond_timeout_not_truncated_to_zero(self) -> None:
        """Verify sub-second timeout (0.5) is not truncated to 0.

        Bug: int(0.5) = 0, which changes timeout semantics entirely.
        In httpx, timeout=0 means no timeout (infinite wait).
        Fix: Pass float directly without int() cast.
        """
        from calm.storage.qdrant import QdrantVectorStore

        with patch("calm.storage.qdrant.AsyncQdrantClient") as mock_client:
            # Create store with sub-second timeout
            QdrantVectorStore(url=":memory:", timeout=0.5)

            # Verify AsyncQdrantClient was called
            mock_client.assert_called_once()

            # Verify the timeout was NOT truncated to 0
            call_kwargs = mock_client.call_args.kwargs
            timeout_value = call_kwargs.get("timeout")

            assert timeout_value == 0.5, (
                f"Expected timeout=0.5, got timeout={timeout_value}. "
                "Bug: int(0.5) truncates to 0, changing timeout semantics."
            )

    def test_float_timeout_preserves_decimal(self) -> None:
        """Verify decimal portion of timeout is preserved.

        Bug: int(5.9) = 5, losing 0.9 seconds of timeout.
        Fix: Pass float directly without int() cast.
        """
        from calm.storage.qdrant import QdrantVectorStore

        with patch("calm.storage.qdrant.AsyncQdrantClient") as mock_client:
            # Create store with float timeout
            QdrantVectorStore(url=":memory:", timeout=5.9)

            # Verify AsyncQdrantClient was called
            mock_client.assert_called_once()

            # Verify the decimal portion is preserved
            call_kwargs = mock_client.call_args.kwargs
            timeout_value = call_kwargs.get("timeout")

            assert timeout_value == 5.9, (
                f"Expected timeout=5.9, got timeout={timeout_value}. "
                "Bug: int(5.9) truncates to 5, losing 0.9 seconds."
            )

    def test_integer_timeout_still_works(self) -> None:
        """Verify integer timeouts continue to work.

        This ensures the fix doesn't break existing behavior for integer values.
        """
        from calm.storage.qdrant import QdrantVectorStore

        with patch("calm.storage.qdrant.AsyncQdrantClient") as mock_client:
            # Create store with integer timeout
            QdrantVectorStore(url=":memory:", timeout=30)

            # Verify AsyncQdrantClient was called
            mock_client.assert_called_once()

            # Verify integer timeout works correctly
            call_kwargs = mock_client.call_args.kwargs
            timeout_value = call_kwargs.get("timeout")

            assert timeout_value == 30, (
                f"Expected timeout=30, got timeout={timeout_value}."
            )

    def test_url_mode_timeout_not_truncated(self) -> None:
        """Verify timeout is not truncated in URL mode (non-memory).

        The bug affected both in-memory and URL modes.
        """
        from calm.storage.qdrant import QdrantVectorStore

        with patch("calm.storage.qdrant.AsyncQdrantClient") as mock_client:
            # Create store with URL (not :memory:)
            QdrantVectorStore(url="http://localhost:6333", timeout=0.75)

            # Verify AsyncQdrantClient was called
            mock_client.assert_called_once()

            # Verify the timeout was NOT truncated
            call_kwargs = mock_client.call_args.kwargs
            timeout_value = call_kwargs.get("timeout")

            assert timeout_value == 0.75, (
                f"Expected timeout=0.75, got timeout={timeout_value}. "
                "Bug: int(0.75) truncates to 0 in URL mode."
            )
