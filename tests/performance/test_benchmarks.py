"""Performance benchmarks for CLAMS.

Benchmarks measure critical operations against HARD performance targets:
- Code search: p95 < 200ms
- Memory retrieval: p95 < 200ms
- Context assembly: p95 < 500ms
- Clustering: < 5s for 100 entries (4 axes)

Tests FAIL (not warn) if targets are missed.
Results logged to: tests/performance/benchmark_results.json
"""

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest

from clams.clustering import ExperienceClusterer
from clams.clustering.clusterer import Clusterer
from clams.embedding import MockEmbedding
from clams.storage import QdrantVectorStore

pytest_plugins = ("pytest_asyncio",)

# Mark as integration tests (require external Qdrant server)
pytestmark = pytest.mark.integration

# Performance targets (HARD requirements)
TARGETS = {
    "code_search_p95_ms": 200.0,
    "memory_retrieval_p95_ms": 200.0,
    "context_assembly_p95_ms": 500.0,
    "clustering_max_s": 5.0,
}

# Test collection names (isolated from production)
BENCHMARK_COLLECTIONS = {
    "memories": "bench_memories",
    "code_units": "bench_code_units",
    "full": "bench_ghap_full",
    "strategy": "bench_ghap_strategy",
    "surprise": "bench_ghap_surprise",
    "root_cause": "bench_ghap_root_cause",
}

# Results file path
RESULTS_FILE = Path(__file__).parent / "benchmark_results.json"


def calculate_p95(measurements: list[float]) -> float:
    """Calculate 95th percentile from measurements.

    Args:
        measurements: List of time measurements in seconds

    Returns:
        p95 value in seconds
    """
    return float(np.percentile(measurements, 95))


def log_benchmark_result(
    name: str,
    value: float,
    target: float,
    passed: bool,
    iterations: int,
    unit: str = "ms",
) -> None:
    """Log benchmark result to JSON file.

    Args:
        name: Benchmark name
        value: Measured value (p95 or total time)
        target: Target value
        passed: Whether benchmark passed
        iterations: Number of iterations run
        unit: Unit of measurement (ms or s)
    """
    # Load existing results
    results: list[dict[str, Any]] = []
    if RESULTS_FILE.exists():
        try:
            results = json.loads(RESULTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            results = []

    # Append new result
    results.append(
        {
            "name": name,
            f"value_{unit}": value,
            f"target_{unit}": target,
            "passed": passed,
            "iterations": iterations,
            "timestamp": time.time(),
            "percentage_of_target": (value / target) * 100 if target > 0 else 0,
        }
    )

    # Keep last 100 results
    results = results[-100:]

    # Write back
    RESULTS_FILE.write_text(json.dumps(results, indent=2))


@pytest.fixture(scope="session", autouse=True)
def verify_qdrant() -> None:
    """Verify Qdrant is available before running benchmarks.

    Tests FAIL if Qdrant unavailable - no skips per spec.
    """
    try:
        response = httpx.get("http://localhost:6333/healthz", timeout=5)
        response.raise_for_status()
    except Exception as e:
        pytest.fail(f"Qdrant not available at localhost:6333: {e}")


@pytest.fixture(scope="module")
async def vector_store() -> AsyncIterator[QdrantVectorStore]:
    """Create a Qdrant vector store for benchmarks."""
    store = QdrantVectorStore(url="http://localhost:6333")
    yield store


@pytest.fixture(scope="module")
async def embedding_service() -> MockEmbedding:
    """Create a mock embedding service for deterministic benchmarks."""
    return MockEmbedding()


@pytest.fixture(scope="module")
async def benchmark_collections(
    vector_store: QdrantVectorStore,
) -> AsyncIterator[dict[str, str]]:
    """Create benchmark collections and populate with test data."""
    # Cleanup any existing collections
    for collection in BENCHMARK_COLLECTIONS.values():
        try:
            await vector_store.delete_collection(collection)
        except Exception:
            pass

    # Create fresh collections
    for collection in BENCHMARK_COLLECTIONS.values():
        await vector_store.create_collection(
            name=collection,
            dimension=768,
            distance="cosine",
        )

    yield BENCHMARK_COLLECTIONS

    # Cleanup after all benchmarks
    for collection in BENCHMARK_COLLECTIONS.values():
        try:
            await vector_store.delete_collection(collection)
        except Exception:
            pass


@pytest.fixture(scope="module")
async def populated_data(
    vector_store: QdrantVectorStore,
    embedding_service: MockEmbedding,
    benchmark_collections: dict[str, str],
) -> dict[str, str]:
    """Populate collections with benchmark data (runs once per module)."""
    # Populate memories (500 entries for realistic benchmark)
    for i in range(500):
        content = f"Memory {i} about topic {i % 20} with details and context"
        embedding = await embedding_service.embed(content)
        await vector_store.upsert(
            collection=benchmark_collections["memories"],
            id=f"mem_{i}",
            vector=embedding,
            payload={
                "id": f"mem_{i}",
                "content": content,
                "category": ["fact", "context", "workflow"][i % 3],
                "importance": (i % 10) / 10.0,
            },
        )

    # Populate code units (500 entries)
    for i in range(500):
        content = f"def function_{i}(arg): return process(arg, {i})"
        embedding = await embedding_service.embed(content)
        await vector_store.upsert(
            collection=benchmark_collections["code_units"],
            id=f"code_{i}",
            vector=embedding,
            payload={
                "id": f"code_{i}",
                "content": content,
                "name": f"function_{i}",
                "type": "function",
                "language": "python",
                "project": f"project_{i % 5}",
            },
        )

    # Populate GHAP entries for clustering benchmark (100 entries in each axis)
    for i in range(100):
        narrative = (
            f"Goal: Complete task {i}. "
            f"Hypothesis: The approach using method {i % 10} will work. "
            f"Action: Implemented the solution step by step. "
            f"Prediction: The test will pass. "
            f"Result: Completed successfully."
        )
        embedding = await embedding_service.embed(narrative)
        payload = {
            "id": f"ghap_{i}",
            "domain": ["debugging", "feature", "refactoring"][i % 3],
            "strategy": ["systematic-elimination", "trial-and-error", "research-first"][
                i % 3
            ],
            "outcome_status": "confirmed" if i % 4 != 0 else "falsified",
            "confidence_tier": ["gold", "silver", "bronze"][i % 3],
            "confidence_weight": [1.0, 0.7, 0.4][i % 3],
        }

        # Store in all axis collections
        for axis in ["full", "strategy", "surprise", "root_cause"]:
            axis_embedding = await embedding_service.embed(
                f"{axis}: {narrative[:100]}"
            )
            await vector_store.upsert(
                collection=benchmark_collections[axis],
                id=f"{axis}_ghap_{i}",
                vector=axis_embedding,
                payload=payload,
            )

    return benchmark_collections


class TestCodeSearchPerformance:
    """Benchmark code search performance."""

    async def test_code_search_p95_under_200ms(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        populated_data: dict[str, str],
    ) -> None:
        """Code search must have p95 < 200ms (100 iterations)."""
        collection = populated_data["code_units"]
        measurements: list[float] = []

        # Warm up (3 iterations)
        for i in range(3):
            query_embedding = await embedding_service.embed(f"warmup query {i}")
            await vector_store.search(
                collection=collection,
                query=query_embedding,
                limit=10,
            )

        # Benchmark (100 iterations)
        for i in range(100):
            query_embedding = await embedding_service.embed(f"function test {i % 20}")

            start = time.perf_counter()
            await vector_store.search(
                collection=collection,
                query=query_embedding,
                limit=10,
            )
            elapsed = time.perf_counter() - start
            measurements.append(elapsed)

        p95 = calculate_p95(measurements)
        p95_ms = p95 * 1000
        target_ms = TARGETS["code_search_p95_ms"]
        passed = p95_ms < target_ms

        log_benchmark_result(
            name="code_search",
            value=p95_ms,
            target=target_ms,
            passed=passed,
            iterations=100,
            unit="ms",
        )

        assert passed, (
            f"Code search p95 ({p95_ms:.1f}ms) exceeds target ({target_ms}ms). "
            f"Over by {((p95_ms / target_ms - 1) * 100):.1f}%"
        )


class TestMemoryRetrievalPerformance:
    """Benchmark memory retrieval performance."""

    async def test_memory_retrieval_p95_under_200ms(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        populated_data: dict[str, str],
    ) -> None:
        """Memory retrieval must have p95 < 200ms (100 iterations)."""
        collection = populated_data["memories"]
        measurements: list[float] = []

        # Warm up (3 iterations)
        for i in range(3):
            query_embedding = await embedding_service.embed(f"warmup memory {i}")
            await vector_store.search(
                collection=collection,
                query=query_embedding,
                limit=10,
            )

        # Benchmark (100 iterations)
        for i in range(100):
            query_embedding = await embedding_service.embed(f"topic {i % 20}")

            start = time.perf_counter()
            await vector_store.search(
                collection=collection,
                query=query_embedding,
                limit=10,
            )
            elapsed = time.perf_counter() - start
            measurements.append(elapsed)

        p95 = calculate_p95(measurements)
        p95_ms = p95 * 1000
        target_ms = TARGETS["memory_retrieval_p95_ms"]
        passed = p95_ms < target_ms

        log_benchmark_result(
            name="memory_retrieval",
            value=p95_ms,
            target=target_ms,
            passed=passed,
            iterations=100,
            unit="ms",
        )

        assert passed, (
            f"Memory retrieval p95 ({p95_ms:.1f}ms) exceeds target ({target_ms}ms). "
            f"Over by {((p95_ms / target_ms - 1) * 100):.1f}%"
        )


class TestContextAssemblyPerformance:
    """Benchmark context assembly performance."""

    async def test_context_assembly_p95_under_500ms(
        self,
        vector_store: QdrantVectorStore,
        embedding_service: MockEmbedding,
        populated_data: dict[str, str],
    ) -> None:
        """Context assembly must have p95 < 500ms (10 iterations).

        Context assembly involves:
        1. Embedding the query
        2. Searching multiple collections
        3. Deduplicating results
        4. Applying token budgets
        5. Formatting output
        """
        memories_collection = populated_data["memories"]
        code_collection = populated_data["code_units"]
        measurements: list[float] = []

        # Simulate context assembly workflow
        async def assemble_context(query: str) -> dict[str, Any]:
            """Simulate context assembly with multiple searches."""
            query_embedding = await embedding_service.embed(query)

            # Search memories
            memory_results = await vector_store.search(
                collection=memories_collection,
                query=query_embedding,
                limit=10,
            )

            # Search code
            code_results = await vector_store.search(
                collection=code_collection,
                query=query_embedding,
                limit=10,
            )

            # Simulate deduplication and formatting (minimal overhead)
            combined = []
            seen_ids = set()
            for r in memory_results:
                if r.id not in seen_ids:
                    combined.append({"type": "memory", "id": r.id, "score": r.score})
                    seen_ids.add(r.id)
            for r in code_results:
                if r.id not in seen_ids:
                    combined.append({"type": "code", "id": r.id, "score": r.score})
                    seen_ids.add(r.id)

            # Sort by score
            combined.sort(key=lambda x: x["score"], reverse=True)

            return {
                "items": combined[:20],
                "count": len(combined),
            }

        # Warm up (2 iterations)
        for i in range(2):
            await assemble_context(f"warmup context {i}")

        # Benchmark (10 iterations)
        for i in range(10):
            query = f"context about task {i} and debugging"

            start = time.perf_counter()
            result = await assemble_context(query)
            elapsed = time.perf_counter() - start
            measurements.append(elapsed)

            # Verify we got results
            assert result["count"] > 0

        p95 = calculate_p95(measurements)
        p95_ms = p95 * 1000
        target_ms = TARGETS["context_assembly_p95_ms"]
        passed = p95_ms < target_ms

        log_benchmark_result(
            name="context_assembly",
            value=p95_ms,
            target=target_ms,
            passed=passed,
            iterations=10,
            unit="ms",
        )

        assert passed, (
            f"Context assembly p95 ({p95_ms:.1f}ms) exceeds target ({target_ms}ms). "
            f"Over by {((p95_ms / target_ms - 1) * 100):.1f}%"
        )


class TestClusteringPerformance:
    """Benchmark clustering performance."""

    async def test_clustering_under_5s_for_100_entries(
        self,
        vector_store: QdrantVectorStore,
        populated_data: dict[str, str],
    ) -> None:
        """Clustering must complete in < 5s for 100 entries (4 axes)."""
        from unittest.mock import patch

        test_axis_collections = {
            "full": populated_data["full"],
            "strategy": populated_data["strategy"],
            "surprise": populated_data["surprise"],
            "root_cause": populated_data["root_cause"],
        }

        # Use patch.dict for proper cleanup even on test failure
        with patch.dict(
            "clams.clustering.experience.AXIS_COLLECTIONS",
            test_axis_collections,
            clear=True,
        ):
            clusterer = Clusterer(min_cluster_size=5, min_samples=3)
            experience_clusterer = ExperienceClusterer(
                vector_store=vector_store,
                clusterer=clusterer,
            )

            start = time.perf_counter()

            # Cluster all 4 axes
            results = await experience_clusterer.cluster_all_axes()

            elapsed = time.perf_counter() - start

            target_s = TARGETS["clustering_max_s"]
            passed = elapsed < target_s

            log_benchmark_result(
                name="clustering_4_axes",
                value=elapsed,
                target=target_s,
                passed=passed,
                iterations=1,
                unit="s",
            )

            # Verify we got results for all 4 axes
            assert len(results) == 4

            assert passed, (
                f"Clustering ({elapsed:.2f}s) exceeds target ({target_s}s). "
                f"Over by {((elapsed / target_s - 1) * 100):.1f}%"
            )
