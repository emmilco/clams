"""Pytest configuration and fixtures."""

import os

import pytest

# Suppress HuggingFace tokenizers parallelism warnings in forked processes
# These warnings are noisy and don't affect test correctness
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Enable pytest-asyncio for all tests
pytest_plugins = ("pytest_asyncio",)

# Import cold-start fixtures to make them available project-wide
# These fixtures simulate first-use scenarios (no pre-existing data)
# Reference: BUG-043, BUG-016 - cold start issues
from tests.fixtures.cold_start import (  # noqa: E402, F401
    cold_start_db,
    cold_start_env,
    cold_start_qdrant,
    db_state,
    populated_db,
    populated_env,
    populated_qdrant,
    qdrant_state,
    storage_env,
)


@pytest.fixture
def sample_fixture() -> str:
    """Sample fixture for testing."""
    return "test_value"
