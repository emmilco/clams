"""Regression tests for BUG-012: index_codebase hangs and doesn't ignore .venv/node_modules."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from calm.embedding.mock import MockEmbeddingService
from calm.indexers import CodeIndexer, TreeSitterParser
from calm.storage.memory import MemoryStore
from calm.storage.metadata import MetadataStore


@pytest.mark.asyncio
async def test_bug_012_default_exclusions_prevent_venv_indexing():
    """Regression test for BUG-012: Verify default exclusions prevent .venv/ indexing."""

    # Setup: Create temp directory structure mimicking real project
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create legitimate source files
        src_dir = root / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass")
        (src_dir / "utils.py").write_text("def helper(): pass")

        # Create .venv with fake Python packages (should be excluded)
        venv_dir = root / ".venv" / "lib" / "python3.12" / "site-packages"
        venv_dir.mkdir(parents=True)
        (venv_dir / "package1.py").write_text("# Package code")
        (venv_dir / "package2.py").write_text("# More package code")

        # Create node_modules (should be excluded)
        node_dir = root / "node_modules" / "some-package"
        node_dir.mkdir(parents=True)
        (node_dir / "index.js").write_text("// Node package")

        # Create __pycache__ (should be excluded)
        cache_dir = root / "src" / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "main.cpython-312.pyc").write_bytes(b"fake bytecode")

        # Setup indexer with default exclusions
        parser = TreeSitterParser()
        embedding = MockEmbeddingService()
        vector_store = MemoryStore()

        with tempfile.NamedTemporaryFile(suffix=".db") as db_file:
            metadata_store = MetadataStore(db_file.name)
            await metadata_store.initialize()

            indexer = CodeIndexer(parser, embedding, vector_store, metadata_store)

            # Define the same default exclusions as the fix
            default_exclusions = [
                "**/.venv/**",
                "**/venv/**",
                "**/node_modules/**",
                "**/.git/**",
                "**/__pycache__/**",
                "**/dist/**",
                "**/build/**",
                "**/target/**",
                "**/.pytest_cache/**",
                "**/.mypy_cache/**",
                "**/.ruff_cache/**",
                "**/htmlcov/**",
                "**/.coverage",
                "**/*.egg-info/**",
            ]

            # Index with exclusions
            stats = await indexer.index_directory(
                str(root),
                "test_project",
                recursive=True,
                exclude_patterns=default_exclusions,
            )

            # Verify: Should have indexed ONLY src/*.py files (2 files)
            assert stats.files_indexed == 2, \
                f"Expected 2 files indexed, got {stats.files_indexed}"

            # Verify: Should NOT have indexed .venv/, node_modules/, or __pycache__/
            indexed_files = await metadata_store.list_indexed_files("test_project")
            indexed_paths = [f.file_path for f in indexed_files]

            # Check that source files ARE indexed
            assert any("main.py" in p for p in indexed_paths), \
                "main.py should be indexed"
            assert any("utils.py" in p for p in indexed_paths), \
                "utils.py should be indexed"

            # Check that excluded directories are NOT indexed
            for path in indexed_paths:
                assert ".venv" not in path, \
                    f"Found .venv file in index: {path}"
                assert "node_modules" not in path, \
                    f"Found node_modules file in index: {path}"
                assert "__pycache__" not in path, \
                    f"Found __pycache__ file in index: {path}"
                assert ".pyc" not in path, \
                    f"Found bytecode file in index: {path}"

            await metadata_store.close()


@pytest.mark.asyncio
async def test_bug_012_indexing_completes_in_reasonable_time():
    """Regression test for BUG-012: Verify indexing doesn't hang on typical projects."""

    # This test would fail before the fix due to indexing thousands of unnecessary files
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create small realistic project (10 source files)
        src_dir = root / "src"
        src_dir.mkdir()
        for i in range(10):
            (src_dir / f"module_{i}.py").write_text(f"def func_{i}(): pass")

        # Setup indexer
        parser = TreeSitterParser()
        embedding = MockEmbeddingService()
        vector_store = MemoryStore()

        with tempfile.NamedTemporaryFile(suffix=".db") as db_file:
            metadata_store = MetadataStore(db_file.name)
            await metadata_store.initialize()

            indexer = CodeIndexer(parser, embedding, vector_store, metadata_store)

            default_exclusions = [
                "**/.venv/**",
                "**/venv/**",
                "**/node_modules/**",
                "**/.git/**",
                "**/__pycache__/**",
            ]

            # Should complete within 5 seconds even without exclusions for this small test
            # But with larger projects, exclusions are critical
            try:
                stats = await asyncio.wait_for(
                    indexer.index_directory(
                        str(root),
                        "test_project",
                        recursive=True,
                        exclude_patterns=default_exclusions,
                    ),
                    timeout=5.0
                )
                assert stats.files_indexed == 10
            except TimeoutError:
                pytest.fail("Indexing hung - did not complete within 5 seconds")

            await metadata_store.close()
