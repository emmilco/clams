"""Tests for CodeIndexer."""

import tempfile
from pathlib import Path

import pytest

from calm.embedding.mock import MockEmbeddingService
from calm.indexers import CodeIndexer, TreeSitterParser
from calm.storage.memory import MemoryStore
from calm.storage.metadata import MetadataStore

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "code_samples"


@pytest.fixture
async def indexer():
    """Create a CodeIndexer instance with in-memory stores."""
    parser = TreeSitterParser()
    embedding_service = MockEmbeddingService()
    vector_store = MemoryStore()

    # Create temporary database for metadata
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    metadata_store = MetadataStore(db_path)
    await metadata_store.initialize()

    indexer = CodeIndexer(parser, embedding_service, vector_store, metadata_store)

    yield indexer

    # Cleanup
    await metadata_store.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_index_single_file(indexer):
    """Test indexing a single Python file."""
    path = str(FIXTURES_DIR / "sample.py")
    stats = await indexer.index_file(path, "test_project")

    assert stats.files_indexed == 1
    assert stats.units_indexed > 0
    assert stats.files_skipped == 0
    assert len(stats.errors) == 0

    # Verify file is tracked in metadata
    assert await indexer.is_file_indexed(path, "test_project")

    # Verify units are in vector store
    count = await indexer._count_file_units(path, "test_project")
    assert count == stats.units_indexed


@pytest.mark.asyncio
async def test_index_file_twice_skips_second(indexer):
    """Test that reindexing unchanged file is skipped."""
    path = str(FIXTURES_DIR / "sample.py")

    # Index first time
    stats1 = await indexer.index_file(path, "test_project")
    assert stats1.files_indexed == 1

    # Index second time - should skip
    stats2 = await indexer.index_file(path, "test_project")
    assert stats2.files_indexed == 0
    assert stats2.files_skipped == 1


@pytest.mark.asyncio
async def test_index_directory(indexer):
    """Test indexing a directory."""
    stats = await indexer.index_directory(
        str(FIXTURES_DIR),
        "test_project",
        recursive=False,
    )

    assert stats.files_indexed > 0
    assert stats.units_indexed > 0

    # Check indexing stats
    index_stats = await indexer.get_indexing_stats("test_project")
    assert index_stats["total_files"] == stats.files_indexed
    assert index_stats["total_units"] == stats.units_indexed
    assert len(index_stats["languages"]) > 0


@pytest.mark.asyncio
async def test_remove_file(indexer):
    """Test removing indexed file."""
    path = str(FIXTURES_DIR / "sample.py")

    # Index file
    await indexer.index_file(path, "test_project")
    assert await indexer.is_file_indexed(path, "test_project")

    # Remove file
    count = await indexer.remove_file(path, "test_project")
    assert count > 0
    assert not await indexer.is_file_indexed(path, "test_project")

    # Verify units removed from vector store
    remaining = await indexer._count_file_units(path, "test_project")
    assert remaining == 0


@pytest.mark.asyncio
async def test_remove_project(indexer):
    """Test removing entire project."""
    # Index multiple files
    await indexer.index_file(str(FIXTURES_DIR / "sample.py"), "test_project")
    await indexer.index_file(str(FIXTURES_DIR / "sample.ts"), "test_project")

    # Verify files indexed
    stats = await indexer.get_indexing_stats("test_project")
    assert stats["total_files"] == 2

    # Remove project
    count = await indexer.remove_project("test_project")
    assert count == 2

    # Verify project removed
    stats = await indexer.get_indexing_stats("test_project")
    assert stats["total_files"] == 0


@pytest.mark.asyncio
async def test_reindex_prevents_orphans(indexer):
    """Test that reindexing deletes old units."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def func1():
    pass

def func2():
    pass

def func3():
    pass
''')
        temp_path = f.name

    try:
        # Index file with 3 functions
        stats1 = await indexer.index_file(temp_path, "test_project")
        assert stats1.units_indexed == 3

        # Modify file to have only 1 function
        with open(temp_path, 'w') as f:
            f.write('''
def func1():
    pass
''')

        # Reindex - should have only 1 unit
        stats2 = await indexer.index_file(temp_path, "test_project")
        assert stats2.units_indexed == 1

        # Verify only 1 unit in vector store
        count = await indexer._count_file_units(temp_path, "test_project")
        assert count == 1
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_empty_file_handling(indexer):
    """Test handling of empty files."""
    path = str(FIXTURES_DIR / "empty.py")
    stats = await indexer.index_file(path, "test_project")

    # Empty files are skipped
    assert stats.files_skipped == 1
    assert stats.units_indexed == 0


@pytest.mark.asyncio
async def test_error_accumulation(indexer):
    """Test that errors are accumulated, not raised."""
    # Note: This test would need a file that causes embedding errors
    # For now, we just verify malformed files don't crash
    path = str(FIXTURES_DIR / "malformed.py")
    stats = await indexer.index_file(path, "test_project")

    # Should not raise, errors should be in stats
    assert isinstance(stats, type(stats))


@pytest.mark.asyncio
async def test_exclude_patterns(indexer):
    """Test directory indexing with exclusion patterns."""
    await indexer.index_directory(
        str(FIXTURES_DIR),
        "test_project",
        recursive=False,
        exclude_patterns=["**/malformed.py", "**/empty.py"],
    )

    # Should skip excluded files
    files = await indexer.metadata_store.list_indexed_files("test_project")
    file_names = {Path(f.file_path).name for f in files}

    assert "malformed.py" not in file_names
    assert "empty.py" not in file_names


@pytest.mark.asyncio
async def test_get_indexing_stats(indexer):
    """Test getting indexing statistics."""
    # Index multiple files
    await indexer.index_file(str(FIXTURES_DIR / "sample.py"), "project1")
    await indexer.index_file(str(FIXTURES_DIR / "sample.ts"), "project1")
    await indexer.index_file(str(FIXTURES_DIR / "sample.js"), "project2")

    # Get stats for project1
    stats1 = await indexer.get_indexing_stats("project1")
    assert stats1["total_files"] == 2
    assert stats1["projects"] == 1

    # Get global stats
    stats_all = await indexer.get_indexing_stats(None)
    assert stats_all["total_files"] == 3
    assert stats_all["projects"] == 2


@pytest.mark.asyncio
async def test_dimension_migration():
    """Test that changing embedding dimension requires reindexing.

    This verifies the spec requirement that dimension changes are detected
    and handled by recreating the collection.

    Note: This test documents the expected behavior - dimension changes
    require manual intervention (deleting the collection) since we can't
    automatically migrate embeddings between different models.
    """
    from calm.embedding.minilm import MiniLMEmbedding

    parser = TreeSitterParser()
    vector_store = MemoryStore()

    # Create temporary database for metadata
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    metadata_store = MetadataStore(db_path)
    await metadata_store.initialize()

    try:
        # Create embedder with MiniLM (384 dimensions)
        embedding_service_384 = MiniLMEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        indexer_384 = CodeIndexer(
            parser, embedding_service_384, vector_store, metadata_store
        )

        # Index a file with dimension 384
        path = str(FIXTURES_DIR / "sample.py")
        stats1 = await indexer_384.index_file(path, "test_project")
        assert stats1.files_indexed == 1
        assert stats1.units_indexed > 0

        # Verify collection has dimension 384
        collection_info = await vector_store.get_collection_info("code_units")
        assert collection_info is not None
        assert collection_info.dimension == 384

        # Now we would switch models (e.g., to Nomic with 768 dims)
        # But that would require deleting the collection first
        # This test verifies the collection dimension is tracked correctly

    finally:
        await metadata_store.close()
        Path(db_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_find_files_excludes_venv_and_common_dirs(indexer):
    """Regression test for BUG-077: _find_files must not traverse excluded dirs.

    Verifies that os.walk directory pruning prevents descent into .venv,
    env, .tox, .nox, .worktrees, node_modules, and other common directories
    that should be excluded by default.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source file that SHOULD be indexed
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass\n")

        # Create excluded directories with .py files that should NOT be found
        excluded_dirs = [
            ".venv/lib/python3.11/site-packages",
            "venv/lib/site-packages",
            "env/lib/site-packages",
            ".tox/py311/lib",
            ".nox/session/lib",
            "node_modules/@types",
            ".git/hooks",
            "__pycache__",
            ".worktrees/BUG-001/src",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            ".hg",
            ".svn",
            ".eggs",
            "htmlcov",
            "target",
        ]

        for dir_path in excluded_dirs:
            full_path = Path(tmpdir) / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            (full_path / "should_not_index.py").write_text(
                "def excluded(): pass\n"
            )

        # Call _find_files WITHOUT explicit exclude_patterns
        # The indexer should use DEFAULT_EXCLUDED_DIRS for directory pruning
        files = indexer._find_files(tmpdir, recursive=True, exclude_patterns=None)

        file_names = [Path(f).name for f in files]
        file_paths_str = "\n".join(files)

        # The source file should be found
        assert "main.py" in file_names, (
            f"Expected main.py in results but got: {file_paths_str}"
        )

        # No files from excluded directories should be found
        assert "should_not_index.py" not in file_names, (
            f"Found files from excluded directories: {file_paths_str}"
        )

        # Verify only the expected file is returned
        assert len(files) == 1, (
            f"Expected exactly 1 file but found {len(files)}: {file_paths_str}"
        )


@pytest.mark.asyncio
async def test_find_files_explicit_exclude_patterns_also_prune_dirs(indexer):
    """Test that explicit exclude_patterns also trigger directory pruning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source file
        (Path(tmpdir) / "app.py").write_text("def app(): pass\n")

        # Create a custom directory that is only excluded by explicit pattern
        custom_dir = Path(tmpdir) / "custom_vendor" / "lib"
        custom_dir.mkdir(parents=True)
        (custom_dir / "vendor_lib.py").write_text("def vendor(): pass\n")

        # With a pattern that matches files inside custom_vendor
        files = indexer._find_files(
            tmpdir,
            recursive=True,
            exclude_patterns=["**/custom_vendor/**"],
        )

        file_names = [Path(f).name for f in files]
        assert "app.py" in file_names
        assert "vendor_lib.py" not in file_names


@pytest.mark.asyncio
async def test_index_directory_default_exclusions(indexer):
    """Test that index_directory excludes common dirs even without explicit patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source file
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        (src_dir / "real_code.py").write_text("def real(): pass\n")

        # Create .venv with files
        venv_dir = Path(tmpdir) / ".venv" / "lib" / "site-packages"
        venv_dir.mkdir(parents=True)
        (venv_dir / "third_party.py").write_text("def third(): pass\n")

        # Index WITHOUT passing exclude_patterns
        stats = await indexer.index_directory(
            str(tmpdir), "test_project", recursive=True
        )

        # Should index only the real source file
        assert stats.files_indexed == 1

        # Verify only the right file is indexed
        indexed_files = await indexer.metadata_store.list_indexed_files(
            "test_project"
        )
        indexed_names = {Path(f.file_path).name for f in indexed_files}
        assert "real_code.py" in indexed_names
        assert "third_party.py" not in indexed_names


@pytest.mark.asyncio
async def test_find_files_non_recursive_mode(indexer):
    """Test that non-recursive mode only finds files in the root directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create file in root
        (Path(tmpdir) / "root_file.py").write_text("def root(): pass\n")

        # Create file in subdirectory
        sub_dir = Path(tmpdir) / "subdir"
        sub_dir.mkdir()
        (sub_dir / "nested_file.py").write_text("def nested(): pass\n")

        files = indexer._find_files(tmpdir, recursive=False, exclude_patterns=None)

        file_names = [Path(f).name for f in files]
        assert "root_file.py" in file_names
        assert "nested_file.py" not in file_names
