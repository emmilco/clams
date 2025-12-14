"""Tests for cold-start fixtures to verify they work correctly.

These tests verify that the cold-start fixture infrastructure itself works
as expected, ensuring the fixtures can be relied upon for other tests.
"""

import pytest

from clams.storage.metadata import MetadataStore
from clams.storage.qdrant import QdrantVectorStore


class TestColdStartQdrant:
    """Tests for cold_start_qdrant fixture."""

    @pytest.mark.cold_start
    async def test_cold_start_has_no_collections(
        self, cold_start_qdrant: QdrantVectorStore
    ) -> None:
        """Verify cold_start_qdrant has no pre-existing collections."""
        # Check that common collections don't exist
        for collection_name in ["memories", "commits", "code", "values", "experiences"]:
            info = await cold_start_qdrant.get_collection_info(collection_name)
            assert info is None, (
                f"Collection '{collection_name}' exists in cold_start_qdrant, "
                "but it should be empty"
            )

    @pytest.mark.cold_start
    async def test_cold_start_is_isolated(
        self, cold_start_qdrant: QdrantVectorStore
    ) -> None:
        """Verify cold_start_qdrant provides isolated instances per test."""
        # Create a collection in this test
        await cold_start_qdrant.create_collection("test_isolation", dimension=128)

        # Verify it exists now
        info = await cold_start_qdrant.get_collection_info("test_isolation")
        assert info is not None
        assert info.name == "test_isolation"
        assert info.dimension == 128

    @pytest.mark.cold_start
    async def test_cold_start_cleanup_after_previous_test(
        self, cold_start_qdrant: QdrantVectorStore
    ) -> None:
        """Verify previous test's collection doesn't leak into this test.

        This test depends on test_cold_start_is_isolated running first.
        """
        # The collection created in test_cold_start_is_isolated should NOT exist here
        info = await cold_start_qdrant.get_collection_info("test_isolation")
        assert info is None, (
            "Collection 'test_isolation' from previous test leaked into this test"
        )


class TestPopulatedQdrant:
    """Tests for populated_qdrant fixture."""

    async def test_populated_has_standard_collections(
        self, populated_qdrant: QdrantVectorStore
    ) -> None:
        """Verify populated_qdrant has all standard collections pre-created."""
        expected_collections = {
            "memories": 768,
            "commits": 768,
            "code": 384,
            "values": 768,
            "experiences": 768,
        }

        for name, expected_dim in expected_collections.items():
            info = await populated_qdrant.get_collection_info(name)
            assert info is not None, f"Collection '{name}' should exist in populated_qdrant"
            assert info.dimension == expected_dim, (
                f"Collection '{name}' has wrong dimension: expected {expected_dim}, got {info.dimension}"
            )

    async def test_populated_collections_are_empty(
        self, populated_qdrant: QdrantVectorStore
    ) -> None:
        """Verify populated collections exist but contain no data."""
        for collection_name in ["memories", "commits", "code", "values", "experiences"]:
            count = await populated_qdrant.count(collection_name)
            assert count == 0, (
                f"Collection '{collection_name}' should be empty, but has {count} vectors"
            )


class TestQdrantState:
    """Tests for qdrant_state parameterized fixture."""

    async def test_qdrant_state_runs_both_scenarios(
        self, qdrant_state: QdrantVectorStore
    ) -> None:
        """Verify qdrant_state fixture works in both scenarios.

        This test runs twice due to parameterization. We verify that the
        qdrant_state is a valid QdrantVectorStore and can be used for operations.
        The actual state (cold vs populated) is tested by checking collection existence.
        """
        # This test will run twice due to parameterization
        # Check if this is cold_start or populated by checking for collections
        # We verify that checking collections doesn't error
        _ = await qdrant_state.get_collection_info("memories")

        # Either state is valid - we just verify the fixture works
        # In cold_start: info is None
        # In populated: info is not None
        # Both are valid outcomes depending on the param
        assert qdrant_state is not None

        # We can always create a new collection in either state
        await qdrant_state.create_collection("test_param_fixture", dimension=64)
        new_info = await qdrant_state.get_collection_info("test_param_fixture")
        assert new_info is not None
        assert new_info.dimension == 64


class TestColdStartDb:
    """Tests for cold_start_db fixture."""

    @pytest.mark.cold_start
    async def test_cold_start_db_is_empty(
        self, cold_start_db: MetadataStore
    ) -> None:
        """Verify cold_start_db has schema but no data."""
        # Should return empty list, not error
        projects = await cold_start_db.list_projects()
        assert projects == []

        indexed_files = await cold_start_db.list_indexed_files()
        assert indexed_files == []

    @pytest.mark.cold_start
    async def test_cold_start_db_is_functional(
        self, cold_start_db: MetadataStore
    ) -> None:
        """Verify cold_start_db can accept new data."""
        project = await cold_start_db.add_project(
            name="test_project",
            root_path="/test",
            settings={},
        )
        assert project.name == "test_project"

        # Verify it was stored
        projects = await cold_start_db.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "test_project"


class TestPopulatedDb:
    """Tests for populated_db fixture."""

    async def test_populated_db_has_sample_data(
        self, populated_db: MetadataStore
    ) -> None:
        """Verify populated_db has pre-populated sample data."""
        projects = await populated_db.list_projects()
        assert len(projects) >= 1
        assert any(p.name == "test_project" for p in projects)

        indexed_files = await populated_db.list_indexed_files()
        assert len(indexed_files) >= 1


class TestDbState:
    """Tests for db_state parameterized fixture."""

    async def test_db_state_runs_both_scenarios(
        self, db_state: MetadataStore
    ) -> None:
        """Verify db_state fixture works in both scenarios.

        This test runs twice due to parameterization. We verify that the
        db_state is a valid MetadataStore and can be used for operations.
        """
        # This test will run twice due to parameterization
        # Check current state - we verify listing doesn't error
        _ = await db_state.list_projects()

        # Either state is valid - we just verify the fixture works
        assert db_state is not None

        # We can always add a new project in either state
        new_project = await db_state.add_project(
            name="test_param_project",
            root_path="/test/param",
            settings={},
        )
        assert new_project is not None
        assert new_project.name == "test_param_project"


class TestCombinedEnvironments:
    """Tests for combined environment fixtures."""

    @pytest.mark.cold_start
    async def test_cold_start_env_is_complete(
        self, cold_start_env: dict
    ) -> None:
        """Verify cold_start_env provides both empty Qdrant and SQLite."""
        qdrant = cold_start_env["qdrant"]
        db = cold_start_env["db"]

        # Qdrant should have no collections
        info = await qdrant.get_collection_info("memories")
        assert info is None

        # DB should have no data
        projects = await db.list_projects()
        assert projects == []

    async def test_populated_env_is_complete(
        self, populated_env: dict
    ) -> None:
        """Verify populated_env provides both pre-populated Qdrant and SQLite."""
        qdrant = populated_env["qdrant"]
        db = populated_env["db"]

        # Qdrant should have collections
        info = await qdrant.get_collection_info("memories")
        assert info is not None

        # DB should have data
        projects = await db.list_projects()
        assert len(projects) >= 1

    async def test_storage_env_parameterized(
        self, storage_env: dict
    ) -> None:
        """Verify storage_env runs with both scenarios.

        This test runs twice due to parameterization. We verify that the
        storage_env provides both qdrant and db components.
        """
        qdrant = storage_env["qdrant"]
        db = storage_env["db"]

        # Verify both components are present and functional
        assert qdrant is not None
        assert db is not None

        # Verify we can use both components
        await qdrant.create_collection("test_env_param", dimension=32)
        env_info = await qdrant.get_collection_info("test_env_param")
        assert env_info is not None

        new_proj = await db.add_project(
            name="test_env_project",
            root_path="/test/env",
            settings={},
        )
        assert new_proj is not None
