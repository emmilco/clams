"""Tests for GitReader implementations."""

import tempfile
from datetime import UTC
from pathlib import Path

import git
import pytest

from clams.git import (
    BinaryFileError,
    FileNotInRepoError,
    GitPythonReader,
    RepositoryNotFoundError,
)


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        repo = git.Repo.init(repo_path)

        # Configure git for commits
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        yield repo_path, repo


@pytest.fixture
def empty_repo(temp_repo):
    """Create an empty git repository."""
    repo_path, repo = temp_repo
    return repo_path, repo


@pytest.fixture
def single_commit_repo(temp_repo):
    """Create a repository with a single commit."""
    repo_path, repo = temp_repo

    # Create a file and commit
    test_file = repo_path / "test.txt"
    test_file.write_text("Hello, World!")

    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")

    return repo_path, repo


@pytest.fixture
def multi_commit_repo(temp_repo):
    """Create a repository with multiple commits."""
    repo_path, repo = temp_repo

    # Commit 1
    test_file = repo_path / "test.txt"
    test_file.write_text("Line 1\n")
    repo.index.add(["test.txt"])
    repo.index.commit("Add test.txt")

    # Commit 2
    test_file.write_text("Line 1\nLine 2\n")
    repo.index.add(["test.txt"])
    repo.index.commit("Update test.txt")

    # Commit 3
    new_file = repo_path / "new.txt"
    new_file.write_text("New file\n")
    repo.index.add(["new.txt"])
    repo.index.commit("Add new.txt")

    return repo_path, repo


@pytest.fixture
def binary_file_repo(temp_repo):
    """Create a repository with a binary file."""
    repo_path, repo = temp_repo

    # Create a binary file
    binary_file = repo_path / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04")
    repo.index.add(["binary.bin"])
    repo.index.commit("Add binary file")

    return repo_path, repo


class TestGitPythonReader:
    """Tests for GitPythonReader."""

    def test_init_with_valid_repo(self, single_commit_repo):
        """Test initialization with valid repository."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))
        assert reader.get_repo_root() == str(repo_path.resolve())

    def test_init_with_invalid_repo(self):
        """Test initialization with invalid repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(RepositoryNotFoundError):
                GitPythonReader(tmpdir)

    def test_init_with_nonexistent_path(self):
        """Test initialization with nonexistent path."""
        with pytest.raises(RepositoryNotFoundError):
            GitPythonReader("/nonexistent/path")

    async def test_get_commits_empty_repo(self, empty_repo):
        """Test get_commits on empty repository."""
        repo_path, _ = empty_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits()
        assert commits == []

    async def test_get_commits_single_commit(self, single_commit_repo):
        """Test get_commits with single commit."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits()
        assert len(commits) == 1

        commit = commits[0]
        assert "Initial commit" in commit.message
        assert commit.author == "Test User"
        assert commit.author_email == "test@example.com"
        assert "test.txt" in commit.files_changed
        assert commit.timestamp.tzinfo == UTC

    async def test_get_commits_multiple_commits(self, multi_commit_repo):
        """Test get_commits with multiple commits."""
        repo_path, _ = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits()
        assert len(commits) == 3

        # Commits should be ordered by timestamp descending
        assert commits[0].message.startswith("Add new.txt")
        assert commits[1].message.startswith("Update test.txt")
        assert commits[2].message.startswith("Add test.txt")

    async def test_get_commits_with_limit(self, multi_commit_repo):
        """Test get_commits with limit parameter."""
        repo_path, _ = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits(limit=2)
        assert len(commits) == 2

    async def test_get_commits_with_path_filter(self, multi_commit_repo):
        """Test get_commits with path filter."""
        repo_path, _ = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits(path="new.txt")
        assert len(commits) == 1
        assert commits[0].message.startswith("Add new.txt")

    async def test_get_commits_with_date_filter(self, multi_commit_repo):
        """Test get_commits with date filter."""
        repo_path, repo = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        # Get timestamp of second commit
        all_commits = await reader.get_commits()
        second_commit_time = all_commits[1].timestamp

        # Get commits since second commit
        commits = await reader.get_commits(since=second_commit_time)

        # Should get commits at or after that time
        assert len(commits) >= 1

    async def test_get_blame_text_file(self, single_commit_repo):
        """Test get_blame on text file."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        blame_entries = await reader.get_blame("test.txt")
        assert len(blame_entries) == 1

        entry = blame_entries[0]
        assert entry.author == "Test User"
        assert entry.author_email == "test@example.com"
        assert entry.line_start == 1
        assert entry.content == "Hello, World!"
        assert entry.timestamp.tzinfo == UTC

    async def test_get_blame_nonexistent_file(self, single_commit_repo):
        """Test get_blame on nonexistent file."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        with pytest.raises(FileNotInRepoError):
            await reader.get_blame("nonexistent.txt")

    async def test_get_blame_binary_file(self, binary_file_repo):
        """Test get_blame on binary file."""
        repo_path, _ = binary_file_repo
        reader = GitPythonReader(str(repo_path))

        with pytest.raises(BinaryFileError):
            await reader.get_blame("binary.bin")

    async def test_get_file_history(self, multi_commit_repo):
        """Test get_file_history."""
        repo_path, _ = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_file_history("test.txt")
        assert len(commits) == 2  # Two commits modified test.txt

        # Should be ordered by timestamp descending
        assert commits[0].message.startswith("Update test.txt")
        assert commits[1].message.startswith("Add test.txt")

    async def test_get_head_sha(self, single_commit_repo):
        """Test get_head_sha."""
        repo_path, repo = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        head_sha = await reader.get_head_sha()
        assert head_sha == repo.head.commit.hexsha
        assert len(head_sha) == 40

    async def test_get_head_sha_empty_repo(self, empty_repo):
        """Test get_head_sha on empty repository."""
        repo_path, _ = empty_repo
        reader = GitPythonReader(str(repo_path))

        with pytest.raises(Exception):  # GitReaderError
            await reader.get_head_sha()

    async def test_commit_timezone_aware(self, single_commit_repo):
        """Test that all commit timestamps are timezone-aware."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits()
        for commit in commits:
            assert commit.timestamp.tzinfo is not None
            assert commit.timestamp.tzinfo == UTC

    async def test_blame_timezone_aware(self, single_commit_repo):
        """Test that all blame timestamps are timezone-aware."""
        repo_path, _ = single_commit_repo
        reader = GitPythonReader(str(repo_path))

        blame_entries = await reader.get_blame("test.txt")
        for entry in blame_entries:
            assert entry.timestamp.tzinfo is not None
            assert entry.timestamp.tzinfo == UTC

    async def test_files_changed_relative_paths(self, multi_commit_repo):
        """Test that files_changed contains relative paths."""
        repo_path, _ = multi_commit_repo
        reader = GitPythonReader(str(repo_path))

        commits = await reader.get_commits()
        for commit in commits:
            for file_path in commit.files_changed:
                # Should not start with / or contain repo path
                assert not file_path.startswith("/")
                assert str(repo_path) not in file_path


@pytest.mark.asyncio
async def test_integration_with_real_repo():
    """Integration test using the actual clams repository."""
    # Use the current repository (worktree path)
    import os

    repo_path = os.getcwd()

    try:
        reader = GitPythonReader(repo_path)

        # Test get_commits
        commits = await reader.get_commits(limit=10)
        assert len(commits) > 0

        # Verify commit structure
        for commit in commits:
            assert len(commit.sha) == 40
            assert commit.message
            assert commit.author
            assert commit.timestamp.tzinfo == UTC

        # Test get_head_sha
        head_sha = await reader.get_head_sha()
        assert len(head_sha) == 40

        # Test get_file_history if pyproject.toml exists
        if Path(repo_path) / "pyproject.toml":
            file_commits = await reader.get_file_history("pyproject.toml", limit=5)
            assert len(file_commits) > 0

    except RepositoryNotFoundError:
        pytest.skip("Not in a git repository")
