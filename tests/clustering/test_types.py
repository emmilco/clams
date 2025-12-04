"""Unit tests for clustering types."""


from learning_memory_server.clustering import CONFIDENCE_WEIGHTS, get_weight


def test_confidence_weights_mapping() -> None:
    """Test confidence weights are correctly defined."""
    assert CONFIDENCE_WEIGHTS["gold"] == 1.0
    assert CONFIDENCE_WEIGHTS["silver"] == 0.8
    assert CONFIDENCE_WEIGHTS["bronze"] == 0.5
    assert CONFIDENCE_WEIGHTS["abandoned"] == 0.2


def test_get_weight_valid_tiers() -> None:
    """Test get_weight with valid tier names."""
    assert get_weight("gold") == 1.0
    assert get_weight("silver") == 0.8
    assert get_weight("bronze") == 0.5
    assert get_weight("abandoned") == 0.2


def test_get_weight_case_insensitive() -> None:
    """Test get_weight is case-insensitive."""
    assert get_weight("GOLD") == 1.0
    assert get_weight("Gold") == 1.0
    assert get_weight("SiLvEr") == 0.8


def test_get_weight_none() -> None:
    """Test get_weight with None returns bronze weight."""
    assert get_weight(None) == 0.5


def test_get_weight_invalid() -> None:
    """Test get_weight with invalid tier returns bronze weight."""
    assert get_weight("unknown") == 0.5
    assert get_weight("") == 0.5
    assert get_weight("platinum") == 0.5
