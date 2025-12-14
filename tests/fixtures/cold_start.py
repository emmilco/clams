"""Cold-start fixtures for testing first-use scenarios.

These fixtures simulate the state of a fresh installation where no collections
or data exist. They are critical for catching bugs that only manifest on
first use, such as:
- BUG-043: Collections never created, 404 errors on first operations
- BUG-016: GHAP collections missing on first start

Cold-start fixtures should be used alongside populated fixtures to ensure
code handles both scenarios correctly.

Usage:
    @pytest.mark.cold_start
    async def test_first_memory_storage(cold_start_qdrant):
        store = MemoryStore(client=cold_start_qdrant)
        # This should NOT fail with 404 - collection should be auto-created
        result = await store.store(content="test", category="fact")
        assert result.success
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from clams.storage.metadata import MetadataStore
from clams.storage.qdrant import QdrantVectorStore

# -----------------------------------------------------------------------------
# Qdrant Cold-Start Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def cold_start_qdrant() -> AsyncIterator[QdrantVectorStore]:
    """Qdrant instance with no pre-existing collections - simulates first use.

    This fixture creates an in-memory Qdrant instance without any collections.
    Use this to test that your code properly handles the case where collections
    don't exist yet and need to be created on first use.

    The fixture automatically cleans up when the test completes (in-memory
    instances are discarded).

    Example:
        async def test_store_creates_collection(cold_start_qdrant):
            # Verify no collections exist
            info = await cold_start_qdrant.get_collection_info("memories")
            assert info is None

            # Your code should handle this gracefully
            store = MemoryStore(vector_store=cold_start_qdrant)
            await store.store(content="test", category="fact")

            # Collection should now exist
            info = await cold_start_qdrant.get_collection_info("memories")
            assert info is not None
    """
    store = QdrantVectorStore(url=":memory:")
    # Explicitly do NOT create any collections - that's the point of cold start
    yield store
    # Cleanup happens automatically with in-memory instance


@pytest.fixture
async def populated_qdrant() -> AsyncIterator[QdrantVectorStore]:
    """Qdrant instance with pre-created collections for normal operation testing.

    This fixture creates an in-memory Qdrant instance with the standard
    collections pre-created (memories, commits, code, values, experiences).
    Use this for tests that don't need to verify cold-start behavior.

    Collections created:
        - memories: 768-dimensional (semantic embeddings)
        - commits: 768-dimensional (semantic embeddings)
        - code: 384-dimensional (code embeddings)
        - values: 768-dimensional (value embeddings)
        - experiences: 768-dimensional (GHAP experience embeddings)
    """
    store = QdrantVectorStore(url=":memory:")

    # Create standard collections with appropriate dimensions
    collections_config: list[tuple[str, int]] = [
        ("memories", 768),
        ("commits", 768),
        ("code", 384),
        ("values", 768),
        ("experiences", 768),
    ]

    for name, dimension in collections_config:
        await store.create_collection(name=name, dimension=dimension)

    yield store
    # Cleanup happens automatically with in-memory instance


@pytest.fixture(params=["cold_start", "populated"])
async def qdrant_state(
    request: pytest.FixtureRequest,
    cold_start_qdrant: QdrantVectorStore,
    populated_qdrant: QdrantVectorStore,
) -> QdrantVectorStore:
    """Parameterized fixture to test both cold-start and populated scenarios.

    This fixture runs the test twice: once with an empty Qdrant instance
    (cold_start) and once with pre-populated collections (populated).

    Use this when you want to verify your code works correctly in both
    first-use and normal operation scenarios.

    Example:
        async def test_memory_operations(qdrant_state):
            store = MemoryStore(vector_store=qdrant_state)
            # This test runs twice - once cold, once populated
            result = await store.store(content="test", category="fact")
            assert result.success

    The current scenario can be accessed via request.param:
        async def test_with_scenario_info(qdrant_state, request):
            if request.param == "cold_start":
                # Verify collection creation happened
                ...
    """
    if request.param == "cold_start":
        return cold_start_qdrant
    return populated_qdrant


# -----------------------------------------------------------------------------
# SQLite Cold-Start Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def cold_start_db(tmp_path: Path) -> AsyncIterator[MetadataStore]:
    """SQLite metadata store with empty database - simulates first use.

    This fixture creates a fresh SQLite database with schema but no data.
    Use this to test that your code properly handles empty query results
    and doesn't assume data always exists.

    The database file is created in a temporary directory and automatically
    cleaned up after the test.

    Example:
        async def test_list_empty_projects(cold_start_db):
            projects = await cold_start_db.list_projects()
            assert projects == []  # Should return empty list, not error
    """
    db_path = tmp_path / "test_cold_start.db"
    store = MetadataStore(db_path)
    await store.initialize()  # Creates schema but no data

    yield store

    await store.close()


@pytest.fixture
async def populated_db(tmp_path: Path) -> AsyncIterator[MetadataStore]:
    """SQLite metadata store with sample data for normal operation testing.

    This fixture creates a SQLite database with pre-populated sample data
    including projects, indexed files, and call graph entries.

    Use this for tests that don't need to verify cold-start behavior.
    """
    from datetime import datetime

    db_path = tmp_path / "test_populated.db"
    store = MetadataStore(db_path)
    await store.initialize()

    # Add sample project
    await store.add_project(
        name="test_project",
        root_path="/test/project",
        settings={"language": "python"},
    )

    # Add sample indexed file
    await store.add_indexed_file(
        file_path="/test/project/main.py",
        project="test_project",
        language="python",
        file_hash="abc123",
        unit_count=5,
        last_modified=datetime.now(),
    )

    yield store

    await store.close()


@pytest.fixture(params=["cold_start", "populated"])
async def db_state(
    request: pytest.FixtureRequest,
    cold_start_db: MetadataStore,
    populated_db: MetadataStore,
) -> MetadataStore:
    """Parameterized fixture to test both cold-start and populated SQLite scenarios.

    Similar to qdrant_state, this runs tests twice: once with an empty database
    and once with pre-populated data.

    Example:
        async def test_project_operations(db_state):
            # This test runs twice - once cold, once populated
            projects = await db_state.list_projects()
            # Cold: expect []
            # Populated: expect at least one project
    """
    if request.param == "cold_start":
        return cold_start_db
    return populated_db


# -----------------------------------------------------------------------------
# Combined Cold-Start Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
async def cold_start_env(
    cold_start_qdrant: QdrantVectorStore,
    cold_start_db: MetadataStore,
) -> AsyncIterator[dict[str, Any]]:
    """Complete cold-start environment with both empty Qdrant and SQLite.

    Use this fixture when testing components that depend on both storage
    systems and need to verify first-use behavior for both.

    Returns:
        dict with keys:
            - 'qdrant': QdrantVectorStore (in-memory, no collections)
            - 'db': MetadataStore (empty schema)
    """
    yield {
        "qdrant": cold_start_qdrant,
        "db": cold_start_db,
    }


@pytest.fixture
async def populated_env(
    populated_qdrant: QdrantVectorStore,
    populated_db: MetadataStore,
) -> AsyncIterator[dict[str, Any]]:
    """Complete populated environment with both Qdrant and SQLite containing data.

    Returns:
        dict with keys:
            - 'qdrant': QdrantVectorStore (with standard collections)
            - 'db': MetadataStore (with sample data)
    """
    yield {
        "qdrant": populated_qdrant,
        "db": populated_db,
    }


@pytest.fixture(params=["cold_start", "populated"])
async def storage_env(
    request: pytest.FixtureRequest,
    cold_start_env: dict[str, Any],
    populated_env: dict[str, Any],
) -> dict[str, Any]:
    """Parameterized fixture for both cold-start and populated full environments.

    Runs tests twice: once with empty storage systems and once with data.
    """
    if request.param == "cold_start":
        return cold_start_env
    return populated_env
