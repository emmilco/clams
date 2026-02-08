"""Collection name constants and experience axis mapping."""


class InvalidAxisError(Exception):
    """Raised when an invalid experience axis is specified."""

    pass


class CollectionName:
    """Collection name constants for all vector stores."""

    MEMORIES = "memories"
    CODE = "code"
    EXPERIENCES_FULL = "ghap_full"
    EXPERIENCES_STRATEGY = "ghap_strategy"
    EXPERIENCES_SURPRISE = "ghap_surprise"
    EXPERIENCES_ROOT_CAUSE = "ghap_root_cause"
    VALUES = "values"
    COMMITS = "commits"

    EXPERIENCE_AXES: dict[str, str] = {
        "full": EXPERIENCES_FULL,
        "strategy": EXPERIENCES_STRATEGY,
        "surprise": EXPERIENCES_SURPRISE,
        "root_cause": EXPERIENCES_ROOT_CAUSE,
    }

    @classmethod
    def get_experience_collection(cls, axis: str) -> str:
        """Get collection name for experience axis."""
        if axis not in cls.EXPERIENCE_AXES:
            valid = ", ".join(cls.EXPERIENCE_AXES.keys())
            raise InvalidAxisError(
                f"Invalid axis '{axis}'. Valid axes: {valid}"
            )
        return cls.EXPERIENCE_AXES[axis]
