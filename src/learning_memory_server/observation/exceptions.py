"""Exceptions for GHAP operations."""


class GHAPError(Exception):
    """Base exception for GHAP operations."""

    pass


class GHAPAlreadyActiveError(GHAPError):
    """Raised when trying to create GHAP while one is active."""

    pass


class NoActiveGHAPError(GHAPError):
    """Raised when trying to update/resolve with no active GHAP."""

    pass


class JournalCorruptedError(GHAPError):
    """Raised when journal files are corrupted."""

    pass
