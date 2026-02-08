"""Pytest configuration and fixtures for server tests.

Import fixtures from tools/conftest.py to make them available to all
server tests, including response efficiency tests.
"""

# Re-export fixtures from tools/conftest.py for use in tests at this level
from tests.server.tools.conftest import (  # noqa: F401
    MockServices,
    mock_code_embedder,
    mock_metadata_store,
    mock_search_result,
    mock_semantic_embedder,
    mock_services,
    mock_vector_store,
)
