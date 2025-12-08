"""Tests for embedding registry."""

import os
from unittest.mock import Mock, patch

import pytest

from learning_memory_server.embedding.base import EmbeddingSettings
from learning_memory_server.embedding.registry import (
    EmbeddingRegistry,
    get_code_embedder,
    get_semantic_embedder,
    initialize_registry,
)


def test_registry_not_initialized() -> None:
    """Test that accessing embedders before initialization raises error."""
    # Reset global registry
    import learning_memory_server.embedding.registry as registry_module

    registry_module._registry = None

    with pytest.raises(RuntimeError, match="Registry not initialized"):
        get_code_embedder()

    with pytest.raises(RuntimeError, match="Registry not initialized"):
        get_semantic_embedder()


def test_registry_initialization() -> None:
    """Test registry initialization with model names."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    # Verify registry is initialized (but models not loaded yet)
    import learning_memory_server.embedding.registry as registry_module

    assert registry_module._registry is not None
    assert registry_module._registry._code_model == code_model
    assert registry_module._registry._semantic_model == semantic_model
    # Models should still be None (lazy loading)
    assert registry_module._registry._code_embedder is None
    assert registry_module._registry._semantic_embedder is None


def test_lazy_loading_code_embedder() -> None:
    """Test that code embedder is loaded on first access."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    # First access should load the model
    embedder1 = get_code_embedder()
    assert embedder1 is not None
    assert embedder1.settings.model_name == code_model

    # Second access should return cached instance
    embedder2 = get_code_embedder()
    assert embedder2 is embedder1  # Same instance


def test_lazy_loading_semantic_embedder() -> None:
    """Test that semantic embedder is loaded on first access."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    # First access should load the model
    embedder1 = get_semantic_embedder()
    assert embedder1 is not None
    assert embedder1.settings.model_name == semantic_model

    # Second access should return cached instance
    embedder2 = get_semantic_embedder()
    assert embedder2 is embedder1  # Same instance


def test_instance_caching() -> None:
    """Test that embedders are cached and reused."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    # Get embedders multiple times
    code1 = get_code_embedder()
    code2 = get_code_embedder()
    code3 = get_code_embedder()

    semantic1 = get_semantic_embedder()
    semantic2 = get_semantic_embedder()
    semantic3 = get_semantic_embedder()

    # All should be the same instance
    assert code1 is code2 is code3
    assert semantic1 is semantic2 is semantic3

    # Code and semantic should be different instances
    assert code1 is not semantic1


def test_env_var_override_code_model() -> None:
    """Test that LMS_CODE_MODEL env var is read by ServerSettings."""
    custom_model = "custom/code/model"

    with patch.dict(os.environ, {"LMS_CODE_MODEL": custom_model}):
        # ServerSettings reads the env var with LMS_ prefix
        from learning_memory_server.server.config import ServerSettings

        settings = ServerSettings()
        assert settings.code_model == custom_model

        # The registry uses the model name passed from ServerSettings
        initialize_registry(settings.code_model, settings.semantic_model)

        # Verify registry was initialized with the env var value
        import learning_memory_server.embedding.registry as registry_module

        assert registry_module._registry is not None
        assert registry_module._registry._code_model == custom_model


def test_env_var_override_semantic_model() -> None:
    """Test that LMS_SEMANTIC_MODEL env var is read by ServerSettings."""
    custom_model = "custom/semantic/model"

    with patch.dict(os.environ, {"LMS_SEMANTIC_MODEL": custom_model}):
        # ServerSettings reads the env var with LMS_ prefix
        from learning_memory_server.server.config import ServerSettings

        settings = ServerSettings()
        assert settings.semantic_model == custom_model

        # The registry uses the model name passed from ServerSettings
        initialize_registry(settings.code_model, settings.semantic_model)

        # Verify registry was initialized with the env var value
        import learning_memory_server.embedding.registry as registry_module

        assert registry_module._registry is not None
        assert registry_module._registry._semantic_model == custom_model


def test_registry_separate_instances() -> None:
    """Test that code and semantic embedders are separate instances."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    code_embedder = get_code_embedder()
    semantic_embedder = get_semantic_embedder()

    # Should be different instances
    assert code_embedder is not semantic_embedder

    # Should have different model names
    assert code_embedder.settings.model_name == code_model
    assert semantic_embedder.settings.model_name == semantic_model


def test_registry_model_logging(caplog) -> None:
    """Test that registry logs when models are loaded."""
    import structlog

    # Configure structlog to capture logs
    structlog.configure(
        processors=[structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    initialize_registry(code_model, semantic_model)

    # First access should log
    get_code_embedder()
    # Check that dimension is logged (proves model was loaded)

    get_semantic_embedder()
    # Check that dimension is logged (proves model was loaded)


def test_direct_registry_usage() -> None:
    """Test using EmbeddingRegistry directly without global functions."""
    code_model = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model = "nomic-ai/nomic-embed-text-v1.5"

    registry = EmbeddingRegistry(code_model, semantic_model)

    # Models should not be loaded yet
    assert registry._code_embedder is None
    assert registry._semantic_embedder is None

    # First access loads models
    code = registry.get_code_embedder()
    assert code is not None
    assert registry._code_embedder is not None

    semantic = registry.get_semantic_embedder()
    assert semantic is not None
    assert registry._semantic_embedder is not None

    # Second access returns cached
    assert registry.get_code_embedder() is code
    assert registry.get_semantic_embedder() is semantic
