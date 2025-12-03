"""Tests for SQLite metadata storage."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from learning_memory_server.storage import MetadataStore


@pytest.fixture
async def metadata_store() -> MetadataStore:
    """Create a temporary metadata store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metadata.db"
        store = MetadataStore(db_path)
        await store.initialize()
        yield store
        await store.close()


class TestIndexedFiles:
    """Tests for indexed file CRUD operations."""

    async def test_add_indexed_file(self, metadata_store: MetadataStore) -> None:
        """Test adding an indexed file."""
        now = datetime.now()
        indexed_file = await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        assert indexed_file.id is not None
        assert indexed_file.file_path == "/project/src/main.py"
        assert indexed_file.project == "test-project"
        assert indexed_file.language == "python"
        assert indexed_file.file_hash == "abc123"
        assert indexed_file.unit_count == 5
        assert indexed_file.indexed_at is not None
        assert indexed_file.last_modified == now

    async def test_add_indexed_file_upsert(self, metadata_store: MetadataStore) -> None:
        """Test that adding the same file twice updates it."""
        now = datetime.now()

        # Add first time
        file1 = await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        # Add again with different hash
        file2 = await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="def456",
            unit_count=7,
            last_modified=now,
        )

        # Should be same ID (update), different hash
        assert file2.id == file1.id
        assert file2.file_hash == "def456"
        assert file2.unit_count == 7

    async def test_get_indexed_file(self, metadata_store: MetadataStore) -> None:
        """Test retrieving an indexed file."""
        now = datetime.now()
        await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        retrieved = await metadata_store.get_indexed_file(
            "/project/src/main.py", "test-project"
        )
        assert retrieved is not None
        assert retrieved.file_path == "/project/src/main.py"
        assert retrieved.file_hash == "abc123"

    async def test_get_indexed_file_not_found(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test retrieving a nonexistent file."""
        result = await metadata_store.get_indexed_file(
            "/nonexistent.py", "test-project"
        )
        assert result is None

    async def test_list_indexed_files(self, metadata_store: MetadataStore) -> None:
        """Test listing indexed files."""
        now = datetime.now()

        await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        await metadata_store.add_indexed_file(
            file_path="/project/src/utils.py",
            project="test-project",
            language="python",
            file_hash="def456",
            unit_count=3,
            last_modified=now,
        )

        files = await metadata_store.list_indexed_files("test-project")
        assert len(files) == 2
        assert files[0].file_path == "/project/src/main.py"
        assert files[1].file_path == "/project/src/utils.py"

    async def test_list_indexed_files_all_projects(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test listing files across all projects."""
        now = datetime.now()

        await metadata_store.add_indexed_file(
            file_path="/project1/src/main.py",
            project="project1",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        await metadata_store.add_indexed_file(
            file_path="/project2/src/main.py",
            project="project2",
            language="python",
            file_hash="def456",
            unit_count=3,
            last_modified=now,
        )

        files = await metadata_store.list_indexed_files()
        assert len(files) == 2

    async def test_get_stale_files(self, metadata_store: MetadataStore) -> None:
        """Test detecting stale files."""
        now = datetime.now()

        await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        await metadata_store.add_indexed_file(
            file_path="/project/src/deleted.py",
            project="test-project",
            language="python",
            file_hash="def456",
            unit_count=3,
            last_modified=now,
        )

        # Only main.py still exists
        current_files = {"/project/src/main.py"}
        stale = await metadata_store.get_stale_files("test-project", current_files)

        assert len(stale) == 1
        assert stale[0].file_path == "/project/src/deleted.py"

    async def test_delete_indexed_file(self, metadata_store: MetadataStore) -> None:
        """Test deleting an indexed file."""
        now = datetime.now()
        await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        await metadata_store.delete_indexed_file("/project/src/main.py", "test-project")

        result = await metadata_store.get_indexed_file(
            "/project/src/main.py", "test-project"
        )
        assert result is None


class TestCallGraph:
    """Tests for call graph operations."""

    async def test_add_call(self, metadata_store: MetadataStore) -> None:
        """Test adding a call graph entry."""
        entry = await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        assert entry.id is not None
        assert entry.caller_qualified_name == "module.ClassA.method1"
        assert entry.callee_qualified_name == "module.ClassB.method2"
        assert entry.caller_file == "/project/src/class_a.py"
        assert entry.callee_file == "/project/src/class_b.py"
        assert entry.project == "test-project"
        assert entry.indexed_at is not None

    async def test_add_call_upsert(self, metadata_store: MetadataStore) -> None:
        """Test that adding the same call twice updates it."""
        # Add first time
        entry1 = await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        # Add again with different files
        entry2 = await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/new_class_a.py",
            callee_file="/project/src/new_class_b.py",
            project="test-project",
        )

        # Should be same ID (update), different files
        assert entry2.id == entry1.id
        assert entry2.caller_file == "/project/src/new_class_a.py"

    async def test_get_callers(self, metadata_store: MetadataStore) -> None:
        """Test finding callers of a function."""
        await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        await metadata_store.add_call(
            caller_qualified_name="module.ClassC.method3",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_c.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        callers = await metadata_store.get_callers(
            "module.ClassB.method2", "test-project"
        )

        assert len(callers) == 2
        caller_names = {c.caller_qualified_name for c in callers}
        assert caller_names == {
            "module.ClassA.method1",
            "module.ClassC.method3",
        }

    async def test_get_callees(self, metadata_store: MetadataStore) -> None:
        """Test finding functions called by a function."""
        await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassC.method3",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_c.py",
            project="test-project",
        )

        callees = await metadata_store.get_callees(
            "module.ClassA.method1", "test-project"
        )

        assert len(callees) == 2
        callee_names = {c.callee_qualified_name for c in callees}
        assert callee_names == {
            "module.ClassB.method2",
            "module.ClassC.method3",
        }

    async def test_delete_calls_for_file(self, metadata_store: MetadataStore) -> None:
        """Test deleting all calls for a file."""
        await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        await metadata_store.add_call(
            caller_qualified_name="module.ClassC.method3",
            callee_qualified_name="module.ClassA.method1",
            caller_file="/project/src/class_c.py",
            callee_file="/project/src/class_a.py",
            project="test-project",
        )

        # Delete calls for class_a.py (both as caller and callee)
        await metadata_store.delete_calls_for_file(
            "/project/src/class_a.py", "test-project"
        )

        # Should have no more calls involving class_a
        callers = await metadata_store.get_callers(
            "module.ClassA.method1", "test-project"
        )
        callees = await metadata_store.get_callees(
            "module.ClassA.method1", "test-project"
        )

        assert len(callers) == 0
        assert len(callees) == 0


class TestProjects:
    """Tests for project configuration operations."""

    async def test_add_project(self, metadata_store: MetadataStore) -> None:
        """Test adding a project."""
        project = await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
            settings={"language": "python", "exclude": ["*.pyc"]},
        )

        assert project.id is not None
        assert project.name == "test-project"
        assert project.root_path == "/path/to/project"
        assert project.settings == {"language": "python", "exclude": ["*.pyc"]}
        assert project.created_at is not None
        assert project.last_indexed is None

    async def test_add_project_default_settings(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test adding a project with default settings."""
        project = await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
        )

        assert project.settings == {}

    async def test_add_project_upsert(self, metadata_store: MetadataStore) -> None:
        """Test that adding the same project twice updates it."""
        # Add first time
        project1 = await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
            settings={"language": "python"},
        )

        # Add again with different settings
        project2 = await metadata_store.add_project(
            name="test-project",
            root_path="/new/path",
            settings={"language": "typescript"},
        )

        # Should be same ID (update), different settings
        assert project2.id == project1.id
        assert project2.root_path == "/new/path"
        assert project2.settings == {"language": "typescript"}

    async def test_get_project(self, metadata_store: MetadataStore) -> None:
        """Test retrieving a project."""
        await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
        )

        retrieved = await metadata_store.get_project("test-project")
        assert retrieved is not None
        assert retrieved.name == "test-project"

    async def test_get_project_not_found(self, metadata_store: MetadataStore) -> None:
        """Test retrieving a nonexistent project."""
        result = await metadata_store.get_project("nonexistent")
        assert result is None

    async def test_list_projects(self, metadata_store: MetadataStore) -> None:
        """Test listing all projects."""
        await metadata_store.add_project(
            name="project-a",
            root_path="/path/to/a",
        )

        await metadata_store.add_project(
            name="project-b",
            root_path="/path/to/b",
        )

        projects = await metadata_store.list_projects()
        assert len(projects) == 2
        assert projects[0].name == "project-a"
        assert projects[1].name == "project-b"

    async def test_update_project_last_indexed(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test updating the last indexed timestamp."""
        await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
        )

        # Initially None
        project = await metadata_store.get_project("test-project")
        assert project is not None
        assert project.last_indexed is None

        # Update timestamp
        await metadata_store.update_project_last_indexed("test-project")

        # Now should have timestamp
        project = await metadata_store.get_project("test-project")
        assert project is not None
        assert project.last_indexed is not None

    async def test_delete_project(self, metadata_store: MetadataStore) -> None:
        """Test deleting a project and all its data."""
        # Add project with files and calls
        await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
        )

        now = datetime.now()
        await metadata_store.add_indexed_file(
            file_path="/project/src/main.py",
            project="test-project",
            language="python",
            file_hash="abc123",
            unit_count=5,
            last_modified=now,
        )

        await metadata_store.add_call(
            caller_qualified_name="module.ClassA.method1",
            callee_qualified_name="module.ClassB.method2",
            caller_file="/project/src/class_a.py",
            callee_file="/project/src/class_b.py",
            project="test-project",
        )

        # Delete project
        await metadata_store.delete_project("test-project")

        # Verify everything is gone
        project = await metadata_store.get_project("test-project")
        assert project is None

        files = await metadata_store.list_indexed_files("test-project")
        assert len(files) == 0

        callers = await metadata_store.get_callers(
            "module.ClassB.method2", "test-project"
        )
        assert len(callers) == 0


class TestJSONSerialization:
    """Tests for JSON round-trip in project settings."""

    async def test_complex_settings_roundtrip(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test that complex settings survive JSON serialization."""
        complex_settings = {
            "exclude_patterns": ["*.pyc", "*.pyo", "__pycache__"],
            "include_languages": ["python", "typescript"],
            "indexing": {
                "max_file_size": 1048576,
                "follow_symlinks": False,
            },
            "features": {
                "call_graph": True,
                "git_integration": True,
            },
        }

        await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
            settings=complex_settings,
        )

        # Retrieve and verify
        retrieved = await metadata_store.get_project("test-project")
        assert retrieved is not None
        assert retrieved.settings == complex_settings

    async def test_empty_settings_roundtrip(
        self, metadata_store: MetadataStore
    ) -> None:
        """Test that empty settings work correctly."""
        await metadata_store.add_project(
            name="test-project",
            root_path="/path/to/project",
            settings={},
        )

        retrieved = await metadata_store.get_project("test-project")
        assert retrieved is not None
        assert retrieved.settings == {}
