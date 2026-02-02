"""Exceptions for GHAP operations."""


class GHAPError(Exception):
    """Base exception for GHAP operations."""

    pass


class GHAPActiveError(GHAPError):
    """Raised when trying to create GHAP while one is active."""

    pass


class GHAPNotFoundError(GHAPError):
    """Raised when trying to update/resolve with no active GHAP."""

    pass


class GHAPValidationError(GHAPError):
    """Raised when GHAP data validation fails."""

    pass


class JournalCorruptedError(GHAPError):
    """Raised when journal files are corrupted."""

    pass
