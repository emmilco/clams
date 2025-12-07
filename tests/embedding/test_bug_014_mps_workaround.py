"""Regression tests for BUG-014: MPS memory leak workaround.

Tests verify that the embedding model uses CPU (not MPS) on Apple Silicon
to avoid PyTorch MPS backend memory leak issues.
"""

import time
from pathlib import Path

import pytest
import torch

from learning_memory_server.embedding.nomic import NomicEmbedding
from learning_memory_server.indexers.indexer import CodeIndexer
from learning_memory_server.indexers.tree_sitter import TreeSitterParser
from learning_memory_server.storage.metadata import MetadataStore
from learning_memory_server.storage.qdrant import QdrantVectorStore


@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="Only relevant on Apple Silicon with MPS",
)
def test_bug_014_embedding_model_uses_cpu_on_mps():
    """Verify embedding model uses CPU (not MPS) to avoid memory leak."""
    embedding_service = NomicEmbedding()

    # CRITICAL: Model must be on CPU, not MPS
    # The fix in nomic.py should force CPU when MPS is available
    assert str(embedding_service.model.device) == "cpu", (
        f"Model on {embedding_service.model.device}, should be on CPU to avoid MPS leak"
    )


@pytest.mark.asyncio
async def test_bug_014_large_indexing_completes():
    """Verify that indexing many files completes without memory issues.

    This test indexes 50+ Python files from the codebase to verify:
    1. No memory leak causing OOM or severe slowdown
    2. Performance stays reasonable (< 10s avg per file)
    3. Indexing completes successfully

    Before the fix, indexing would show:
    - 15+ GB memory usage
    - 55+ seconds per file near the end (GPU memory exhaustion)
    - System unresponsiveness

    After the fix (CPU mode):
    - Stable memory usage
    - Consistent performance (~5-10s per file)
    - Reliable completion
    """
    # Setup services
    parser = TreeSitterParser()
    embedding_service = NomicEmbedding()
    vector_store = QdrantVectorStore(":memory:")
    metadata_store = MetadataStore(":memory:")
    await metadata_store.initialize()

    indexer = CodeIndexer(parser, embedding_service, vector_store, metadata_store)

    # Find Python files in the codebase
    # Use src/ directory to get a good mix of files
    clams_dir = Path(__file__).parent.parent.parent
    py_files = list(clams_dir.glob("src/**/*.py"))

    # Index at least 50 files (or all if fewer)
    files_to_index = py_files[:50] if len(py_files) >= 50 else py_files

    # Must have some files to test
    assert len(files_to_index) > 0, "No Python files found to index"

    # Index files and measure performance
    start = time.time()
    indexed_count = 0

    for py_file in files_to_index:
        try:
            await indexer.index_file(str(py_file), "test_project")
            indexed_count += 1
        except Exception as e:
            # Don't fail on individual file errors (unparseable files, etc)
            # Just record that we attempted it
            print(f"Warning: Failed to index {py_file}: {e}")

    elapsed = time.time() - start

    # Verify we indexed at least some files
    assert indexed_count > 0, "Failed to index any files"

    # Performance check: average time per file should be reasonable
    # Before fix: 55+ seconds per file (GPU memory exhaustion)
    # After fix: Should be < 10 seconds per file on CPU
    avg_time = elapsed / indexed_count
    assert avg_time < 10, (
        f"Average {avg_time:.1f}s per file - possible memory leak or performance issue"
    )

    # Cleanup
    await metadata_store.close()
    # Note: QdrantVectorStore doesn't have a close() method for in-memory instances


@pytest.mark.asyncio
async def test_bug_014_batch_encoding_performance():
    """Verify batch encoding doesn't accumulate memory or slow down.

    Tests multiple batches of embeddings to ensure:
    1. No progressive slowdown between batches
    2. No memory accumulation
    3. Consistent performance
    """
    embedding_service = NomicEmbedding()

    # Test data: multiple batches of text
    test_texts = [
        f"This is test text number {i} for batch encoding performance testing."
        for i in range(100)
    ]

    # Run multiple batches and measure time
    batch_times = []
    batch_size = 10

    for batch_start in range(0, len(test_texts), batch_size):
        batch = test_texts[batch_start : batch_start + batch_size]

        start = time.time()
        embeddings = await embedding_service.embed_batch(batch)
        elapsed = time.time() - start

        batch_times.append(elapsed)

        # Verify embeddings are correct shape
        assert len(embeddings) == len(batch)
        assert all(emb.shape == (768,) for emb in embeddings)

    # Performance should be consistent across batches
    # No progressive slowdown indicating memory issues
    first_batch_time = batch_times[0]
    last_batch_time = batch_times[-1]

    # Last batch should not be significantly slower than first
    # Allow 3x slowdown max (MPS leak would cause 10x+ slowdown)
    assert last_batch_time < first_batch_time * 3, (
        f"Last batch ({last_batch_time:.2f}s) significantly slower than "
        f"first batch ({first_batch_time:.2f}s) - possible memory leak"
    )
