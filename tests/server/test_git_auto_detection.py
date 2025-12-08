"""Tests for git repository auto-detection in service initialization.

This module tests BUG-002 fix: ensuring git tools auto-detect the repository
from the current working directory when repo_path is not explicitly configured.
"""

import os

import pytest
from git import Repo

from clams.embedding import EmbeddingSettings, NomicEmbedding
from clams.server.config import ServerSettings
from clams.server.tools import initialize_services

# Mark as slow tests (load heavy embedding models)
pytestmark = pytest.mark.slow


@pytest.fixture
def embedding_service():
    """Create a real embedding service for testing."""
    settings = EmbeddingSettings(model_name="nomic-ai/nomic-embed-text-v1.5")
    return NomicEmbedding(settings=settings)


@pytest.mark.asyncio
async def test_git_auto_detection_in_repo(tmp_path, embedding_service):
    """Test that git tools auto-detect repo when in a git directory."""
    # Setup: Create a git repo
    repo = Repo.init(tmp_path)
    (tmp_path / "test.txt").write_text("test")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")

    # Change to repo directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    services = None

    try:
        # Action: Initialize services without repo_path config
        settings = ServerSettings(
            repo_path=None,  # Not configured
            qdrant_url="http://localhost:6333",
            sqlite_path=str(tmp_path / "test.db"),
        )
        services = await initialize_services(settings, embedding_service)

        # Assert: Git analyzer should be initialized
        assert services.git_analyzer is not None
        assert services.git_analyzer.git_reader.get_repo_root() == str(tmp_path)
    finally:
        if services:
            await services.close()
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_git_explicit_config_overrides_auto_detection(tmp_path, embedding_service):
    """Test that explicit repo_path config takes precedence."""
    # Setup: Create two git repos
    repo1 = Repo.init(tmp_path / "repo1")
    (tmp_path / "repo1" / "test.txt").write_text("repo1")
    repo1.index.add(["test.txt"])
    repo1.index.commit("Initial commit")

    repo2 = Repo.init(tmp_path / "repo2")
    (tmp_path / "repo2" / "test.txt").write_text("repo2")
    repo2.index.add(["test.txt"])
    repo2.index.commit("Initial commit")

    # Change to repo1
    original_cwd = os.getcwd()
    os.chdir(tmp_path / "repo1")
    services = None

    try:
        # Action: Initialize with explicit path to repo2
        settings = ServerSettings(
            repo_path=str(tmp_path / "repo2"),  # Explicit config
            qdrant_url="http://localhost:6333",
            sqlite_path=str(tmp_path / "test.db"),
        )
        services = await initialize_services(settings, embedding_service)

        # Assert: Should use repo2, not auto-detected repo1
        assert services.git_analyzer is not None
        assert services.git_analyzer.git_reader.get_repo_root() == str(tmp_path / "repo2")
    finally:
        if services:
            await services.close()
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_git_graceful_failure_when_not_in_repo(tmp_path, embedding_service):
    """Test that git tools are None when not in a git repository."""
    # Setup: Non-git directory
    os.makedirs(tmp_path / "not_a_repo", exist_ok=True)

    original_cwd = os.getcwd()
    os.chdir(tmp_path / "not_a_repo")
    services = None

    try:
        # Action: Initialize services
        settings = ServerSettings(
            repo_path=None,  # Not configured
            qdrant_url="http://localhost:6333",
            sqlite_path=str(tmp_path / "test.db"),
        )
        services = await initialize_services(settings, embedding_service)

        # Assert: Git analyzer should be None (graceful degradation)
        assert services.git_analyzer is None
    finally:
        if services:
            await services.close()
        os.chdir(original_cwd)
