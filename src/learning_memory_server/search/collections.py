"""Collection name constants and experience axis mapping."""


class InvalidAxisError(Exception):
    """Raised when an invalid experience axis is specified."""

    pass


class CollectionName:
    """Collection name constants for all vector stores.

    Using a class with string constants (not Enum) for:
    - Simple string usage without .value
    - Easy typing in function signatures
    - Clear namespace grouping
    """

    MEMORIES = "memories"
    CODE = "code"
    EXPERIENCES_FULL = "experiences_full"
    EXPERIENCES_STRATEGY = "experiences_strategy"
    EXPERIENCES_SURPRISE = "experiences_surprise"
    EXPERIENCES_ROOT_CAUSE = "experiences_root_cause"
    VALUES = "values"
    COMMITS = "commits"

    # Experience axis mapping
    # Note: 'domain' is NOT a separate collection - it's stored as
    # metadata on experiences_full
    EXPERIENCE_AXES: dict[str, str] = {
        "full": EXPERIENCES_FULL,
        "strategy": EXPERIENCES_STRATEGY,
        "surprise": EXPERIENCES_SURPRISE,
        "root_cause": EXPERIENCES_ROOT_CAUSE,
    }

    @classmethod
    def get_experience_collection(cls, axis: str) -> str:
        """Get collection name for experience axis.

        Args:
            axis: Experience clustering axis

        Returns:
            Collection name

        Raises:
            InvalidAxisError: If axis is not valid
        """
        if axis not in cls.EXPERIENCE_AXES:
            valid = ", ".join(cls.EXPERIENCE_AXES.keys())
            raise InvalidAxisError(
                f"Invalid axis '{axis}'. Valid axes: {valid}"
            )
        return cls.EXPERIENCE_AXES[axis]
