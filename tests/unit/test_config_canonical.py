"""Tests for the canonical configuration module (SPEC-029).

Tests the new top-level clams.config module that consolidates
scattered constants throughout the codebase.
"""

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDefaultSettings:
    """Test default configuration values match original constants."""

    def test_context_max_item_fraction(self) -> None:
        """Verify context max_item_fraction matches original constant."""
        from clams.config import settings

        assert settings.context.max_item_fraction == 0.25

    def test_context_source_weights(self) -> None:
        """Verify source weights match original dict."""
        from clams.config import settings

        expected = {
            "memories": 1,
            "code": 2,
            "experiences": 3,
            "values": 1,
            "commits": 2,
        }
        assert settings.context.source_weights == expected

    def test_context_similarity_threshold(self) -> None:
        """Verify deduplication threshold matches original constant."""
        from clams.config import settings

        assert settings.context.similarity_threshold == 0.90

    def test_context_max_fuzzy_content_length(self) -> None:
        """Verify max fuzzy content length matches original constant."""
        from clams.config import settings

        assert settings.context.max_fuzzy_content_length == 1000

    def test_indexer_embedding_batch_size(self) -> None:
        """Verify indexer batch size matches original class attribute."""
        from clams.config import settings

        assert settings.indexer.embedding_batch_size == 100

    def test_tools_project_id_max_length(self) -> None:
        """Verify project ID max length matches original constant."""
        from clams.config import settings

        assert settings.tools.project_id_max_length == 100

    def test_tools_snippet_max_length(self) -> None:
        """Verify snippet max length matches original inline constant."""
        from clams.config import settings

        assert settings.tools.snippet_max_length == 5_000

    def test_tools_memory_content_max_length(self) -> None:
        """Verify memory content max length matches original inline constant."""
        from clams.config import settings

        assert settings.tools.memory_content_max_length == 10_000

    def test_paths_clams_dir(self) -> None:
        """Verify CLAMS directory path."""
        from clams.config import settings

        assert settings.paths.clams_dir == Path.home() / ".clams"

    def test_paths_journal_dir(self) -> None:
        """Verify journal directory path."""
        from clams.config import settings

        assert settings.paths.journal_dir == Path.home() / ".clams" / "journal"


class TestEnvironmentOverrides:
    """Test environment variable overrides work correctly."""

    def test_context_max_item_fraction_override(self) -> None:
        """Verify environment override for max_item_fraction."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__MAX_ITEM_FRACTION": "0.5"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.context.max_item_fraction == 0.5

    def test_context_similarity_threshold_override(self) -> None:
        """Verify environment override for similarity_threshold."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__SIMILARITY_THRESHOLD": "0.85"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.context.similarity_threshold == 0.85

    def test_indexer_batch_size_override(self) -> None:
        """Verify environment override for embedding_batch_size."""
        with patch.dict(os.environ, {"CLAMS_INDEXER__EMBEDDING_BATCH_SIZE": "200"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.indexer.embedding_batch_size == 200

    def test_tools_snippet_max_length_override(self) -> None:
        """Verify environment override for snippet_max_length."""
        with patch.dict(os.environ, {"CLAMS_TOOLS__SNIPPET_MAX_LENGTH": "10000"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.tools.snippet_max_length == 10000

    def test_tools_memory_content_max_length_override(self) -> None:
        """Verify environment override for memory_content_max_length."""
        with patch.dict(os.environ, {"CLAMS_TOOLS__MEMORY_CONTENT_MAX_LENGTH": "20000"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.tools.memory_content_max_length == 20000

    def test_tools_project_id_max_length_override(self) -> None:
        """Verify environment override for project_id_max_length."""
        with patch.dict(os.environ, {"CLAMS_TOOLS__PROJECT_ID_MAX_LENGTH": "200"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.tools.project_id_max_length == 200

    def test_source_weight_override(self) -> None:
        """Verify environment override for individual source weights."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__SOURCE_WEIGHT_MEMORIES": "5"}):
            from clams.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.context.source_weight_memories == 5
            # source_weights dict should reflect the override
            assert fresh_settings.context.source_weights["memories"] == 5


class TestBackwardsCompatibility:
    """Test backwards compatibility with original module imports."""

    def test_server_settings_reexport(self) -> None:
        """Verify ServerSettings is re-exported from clams.config."""
        from clams.config import ServerSettings
        from clams.server.config import ServerSettings as OriginalServerSettings

        assert ServerSettings is OriginalServerSettings

    def test_module_level_singleton(self) -> None:
        """Verify settings singleton is accessible."""
        from clams.config import settings

        assert settings is not None
        assert hasattr(settings, "server")
        assert hasattr(settings, "context")
        assert hasattr(settings, "indexer")
        assert hasattr(settings, "tools")
        assert hasattr(settings, "paths")

    def test_tokens_module_aliases(self) -> None:
        """Verify original import locations still work (tokens.py)."""
        from clams.config import settings
        from clams.context.tokens import MAX_ITEM_FRACTION, SOURCE_WEIGHTS

        # Values should match settings
        assert MAX_ITEM_FRACTION == settings.context.max_item_fraction
        assert SOURCE_WEIGHTS == settings.context.source_weights

    def test_deduplication_module_aliases(self) -> None:
        """Verify original import locations still work (deduplication.py)."""
        from clams.config import settings
        from clams.context.deduplication import (
            MAX_FUZZY_CONTENT_LENGTH,
            SIMILARITY_THRESHOLD,
        )

        assert SIMILARITY_THRESHOLD == settings.context.similarity_threshold
        assert MAX_FUZZY_CONTENT_LENGTH == settings.context.max_fuzzy_content_length

    def test_validation_module_alias(self) -> None:
        """Verify original import location still works (validation.py)."""
        from clams.config import settings
        from clams.server.tools.validation import PROJECT_ID_MAX_LENGTH

        assert PROJECT_ID_MAX_LENGTH == settings.tools.project_id_max_length

    def test_session_module_aliases(self) -> None:
        """Verify original import locations still work (session.py)."""
        from clams.config import settings
        from clams.server.tools.session import CLAMS_DIR, JOURNAL_DIR

        assert CLAMS_DIR == settings.paths.clams_dir
        assert JOURNAL_DIR == settings.paths.journal_dir


class TestNoCircularImports:
    """Test that config module doesn't cause circular imports."""

    def test_config_import_clean(self) -> None:
        """Verify config module can be imported cleanly."""
        import clams.config

        importlib.reload(clams.config)  # Should not raise

    def test_settings_import_from_submodules(self) -> None:
        """Verify submodules can import settings without issues."""
        # These imports should not cause circular import errors
        from clams.context.deduplication import SIMILARITY_THRESHOLD  # noqa: F401
        from clams.context.tokens import SOURCE_WEIGHTS  # noqa: F401
        from clams.server.tools.validation import PROJECT_ID_MAX_LENGTH  # noqa: F401


class TestSettingsValidation:
    """Test settings validation."""

    def test_invalid_max_item_fraction_zero(self) -> None:
        """Verify validation rejects max_item_fraction of 0."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__MAX_ITEM_FRACTION": "0.0"}):
            from clams.config import Settings

            with pytest.raises(ValueError, match="max_item_fraction must be between"):
                Settings()

    def test_invalid_max_item_fraction_greater_than_one(self) -> None:
        """Verify validation rejects max_item_fraction > 1."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__MAX_ITEM_FRACTION": "1.5"}):
            from clams.config import Settings

            with pytest.raises(ValueError, match="max_item_fraction must be between"):
                Settings()

    def test_invalid_similarity_threshold_greater_than_one(self) -> None:
        """Verify validation rejects similarity_threshold > 1."""
        with patch.dict(os.environ, {"CLAMS_CONTEXT__SIMILARITY_THRESHOLD": "1.5"}):
            from clams.config import Settings

            with pytest.raises(ValueError, match="similarity_threshold must be between"):
                Settings()


class TestAllExports:
    """Test all expected exports are available."""

    def test_all_exports_defined(self) -> None:
        """Verify __all__ contains expected exports."""
        from clams import config

        expected = [
            "Settings",
            "ServerSettings",
            "ContextSettings",
            "IndexerSettings",
            "ToolSettings",
            "PathSettings",
            "settings",
        ]
        assert set(expected) == set(config.__all__)

    def test_all_exports_importable(self) -> None:
        """Verify all __all__ exports are importable."""
        from clams.config import (
            ContextSettings,
            IndexerSettings,
            PathSettings,
            ServerSettings,
            Settings,
            ToolSettings,
            settings,
        )

        # All should be non-None
        assert Settings is not None
        assert ServerSettings is not None
        assert ContextSettings is not None
        assert IndexerSettings is not None
        assert ToolSettings is not None
        assert PathSettings is not None
        assert settings is not None


class TestFieldDescriptions:
    """Test that all settings fields have descriptions."""

    def test_context_settings_have_descriptions(self) -> None:
        """Verify all ContextSettings fields have descriptions."""
        from clams.config import ContextSettings

        for field_name, field_info in ContextSettings.model_fields.items():
            assert field_info.description is not None, (
                f"ContextSettings.{field_name} is missing a description"
            )

    def test_indexer_settings_have_descriptions(self) -> None:
        """Verify all IndexerSettings fields have descriptions."""
        from clams.config import IndexerSettings

        for field_name, field_info in IndexerSettings.model_fields.items():
            assert field_info.description is not None, (
                f"IndexerSettings.{field_name} is missing a description"
            )

    def test_tool_settings_have_descriptions(self) -> None:
        """Verify all ToolSettings fields have descriptions."""
        from clams.config import ToolSettings

        for field_name, field_info in ToolSettings.model_fields.items():
            assert field_info.description is not None, (
                f"ToolSettings.{field_name} is missing a description"
            )

    def test_path_settings_have_descriptions(self) -> None:
        """Verify all PathSettings fields have descriptions."""
        from clams.config import PathSettings

        for field_name, field_info in PathSettings.model_fields.items():
            assert field_info.description is not None, (
                f"PathSettings.{field_name} is missing a description"
            )


class TestEnvPrefixes:
    """Test environment variable prefixes are correct."""

    def test_context_settings_env_prefix(self) -> None:
        """Verify ContextSettings uses correct env prefix."""
        from clams.config import ContextSettings

        assert ContextSettings.model_config.get("env_prefix") == "CLAMS_CONTEXT__"

    def test_indexer_settings_env_prefix(self) -> None:
        """Verify IndexerSettings uses correct env prefix."""
        from clams.config import IndexerSettings

        assert IndexerSettings.model_config.get("env_prefix") == "CLAMS_INDEXER__"

    def test_tool_settings_env_prefix(self) -> None:
        """Verify ToolSettings uses correct env prefix."""
        from clams.config import ToolSettings

        assert ToolSettings.model_config.get("env_prefix") == "CLAMS_TOOLS__"

    def test_path_settings_env_prefix(self) -> None:
        """Verify PathSettings uses correct env prefix."""
        from clams.config import PathSettings

        assert PathSettings.model_config.get("env_prefix") == "CLAMS_PATHS__"
