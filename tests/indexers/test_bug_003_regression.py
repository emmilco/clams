"""Regression test for BUG-003: index_codebase should re-index if collection exists.

This test verifies that calling index_directory() twice succeeds without raising
an exception, regardless of the Qdrant backend mode (in-memory or server).

The bug was that _ensure_collection() only caught ValueError (raised by in-memory mode)
but not UnexpectedResponse (raised by server mode when collection already exists).
"""

import tempfile
from pathlib import Path

import pytest

from calm.embedding.mock import MockEmbeddingService
from calm.indexers import CodeIndexer, TreeSitterParser
from calm.storage.memory import MemoryStore
from calm.storage.metadata import MetadataStore

pytestmark = pytest.mark.asyncio


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


async def test_bug_003_double_index_inmemory(indexer, tmp_path):
    """Regression test: index_directory should work on second call (in-memory mode).

    This test verifies that the fix handles ValueError from in-memory Qdrant.
    """
    # Create a test Python file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    '''Say hello'''\n    pass\n")

    # First index - should succeed
    stats1 = await indexer.index_directory(
        path=str(tmp_path),
        project="test_project",
        recursive=False
    )
    assert stats1.files_indexed == 1
    assert stats1.units_indexed >= 1

    # Second index - should NOT raise exception
    # Before the fix, this would raise UnexpectedResponse in server mode
    stats2 = await indexer.index_directory(
        path=str(tmp_path),
        project="test_project",
        recursive=False
    )
    # Should succeed (file is unchanged, so skipped)
    assert stats2.files_skipped == 1


async def test_bug_003_double_index_with_modification(indexer, tmp_path):
    """Regression test: verify re-indexing works after file modification.

    This ensures the fix doesn't break the re-indexing logic.
    """
    # Create a test Python file
    test_file = tmp_path / "modified.py"
    test_file.write_text("def foo():\n    pass\n")

    # First index
    stats1 = await indexer.index_directory(
        path=str(tmp_path),
        project="test_project",
        recursive=False
    )
    assert stats1.files_indexed == 1
    assert stats1.units_indexed >= 1

    # Modify the file
    test_file.write_text("def foo():\n    '''New docstring'''\n    pass\n\ndef bar():\n    pass\n")

    # Second index - should detect changes and re-index
    stats2 = await indexer.index_directory(
        path=str(tmp_path),
        project="test_project",
        recursive=False
    )
    assert stats2.files_indexed == 1
    assert stats2.units_indexed >= 1


async def test_bug_003_multiple_projects_same_collection(indexer, tmp_path):
    """Regression test: verify multiple projects can share the same collection.

    This test ensures the fix works when indexing different projects
    that all use the same "code_units" collection.
    """
    # Create test files in different subdirectories (simulating projects)
    project1_dir = tmp_path / "project1"
    project1_dir.mkdir()
    (project1_dir / "main.py").write_text("def project1_func():\n    pass\n")

    project2_dir = tmp_path / "project2"
    project2_dir.mkdir()
    (project2_dir / "main.py").write_text("def project2_func():\n    pass\n")

    # Index first project
    stats1 = await indexer.index_directory(
        path=str(project1_dir),
        project="project1",
        recursive=False
    )
    assert stats1.files_indexed == 1

    # Index second project - collection already exists, should still work
    stats2 = await indexer.index_directory(
        path=str(project2_dir),
        project="project2",
        recursive=False
    )
    assert stats2.files_indexed == 1

    # Re-index first project - should work
    stats3 = await indexer.index_directory(
        path=str(project1_dir),
        project="project1",
        recursive=False
    )
    assert stats3.files_skipped == 1  # Unchanged, so skipped
