"""Validation test configuration.

Validation tests use production-like data profiles and may take longer
than unit tests. They are marked for selective execution.

Reference: SPEC-034 - Parameter Validation with Production Data
"""

from collections.abc import Generator

import numpy as np
import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register validation test markers."""
    config.addinivalue_line(
        "markers", "validation: mark test as validation test (uses production-like data)"
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Add validation marker to all tests in validation directory."""
    for item in items:
        if "validation" in str(item.fspath):
            item.add_marker(pytest.mark.validation)


# Shared fixtures for validation tests
@pytest.fixture
def deterministic_seed() -> int:
    """Fixed seed for reproducible test data."""
    return 42


@pytest.fixture(autouse=True)
def ensure_reproducibility() -> Generator[None, None, None]:
    """Ensure tests are deterministic."""
    np.random.seed(42)
    yield
