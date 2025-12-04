"""Pytest configuration and fixtures."""

import os

import pytest

# Suppress HuggingFace tokenizers parallelism warnings in forked processes
# These warnings are noisy and don't affect test correctness
os.environ["TOKENIZERS_PARALLELISM"] = "false"


@pytest.fixture
def sample_fixture() -> str:
    """Sample fixture for testing."""
    return "test_value"
