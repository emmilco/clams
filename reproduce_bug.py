#!/usr/bin/env python3
"""Reproduce BUG-020: store_value internal server error."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from unittest.mock import MagicMock, AsyncMock
import numpy as np

from clams.clustering import Clusterer, ExperienceClusterer
from clams.values import ValueStore
from clams.server.tools.learning import get_learning_tools


async def main() -> None:
    """Reproduce the bug by calling store_value."""
    print("Setting up mocks...")

    # Create mock vector store
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])
    vector_store.upsert = AsyncMock()
    vector_store.get = AsyncMock(return_value=None)

    # Create mock embedding service
    embedding_service = MagicMock()
    embedding_service.embed = AsyncMock(return_value=np.array([1.0, 2.0, 3.0], dtype=np.float32))

    # Create clusterer
    clusterer_impl = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )
    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer_impl,
    )

    # Mock cluster_axis to return some clusters
    from clams.clustering.types import ClusterInfo
    experience_clusterer.cluster_axis = AsyncMock(
        return_value=[
            ClusterInfo(
                label=0,
                centroid=np.array([1.0, 2.0, 3.0], dtype=np.float32),
                member_ids=["id1", "id2"],
                size=10,
                avg_weight=0.8,
            ),
        ]
    )
    experience_clusterer.count_experiences = AsyncMock(return_value=25)

    # Create value store
    value_store = ValueStore(
        embedding_service=embedding_service,
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    # Get tools
    print("Getting learning tools...")
    tools = get_learning_tools(experience_clusterer, value_store)

    # Call store_value
    print("\nCalling store_value with parameters:")
    params = {
        "text": "Test value",
        "cluster_id": "full_0",
        "axis": "full"
    }
    print(f"  {params}")

    try:
        result = await tools["store_value"](**params)
        print(f"\nResult: {result}")
    except Exception as e:
        print(f"\nException raised: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
