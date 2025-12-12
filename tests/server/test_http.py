"""Tests for HTTP transport."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestHttpServerCreation:
    """Test HTTP server initialization."""

    def test_http_server_init(self) -> None:
        """HttpServer should initialize with correct parameters."""
        from clams.server.http import HttpServer

        mock_server = MagicMock()
        mock_services = MagicMock()

        http_server = HttpServer(
            server=mock_server,
            services=mock_services,
            host="127.0.0.1",
            port=6334,
        )

        assert http_server.server == mock_server
        assert http_server.services == mock_services
        assert http_server.host == "127.0.0.1"
        assert http_server.port == 6334

    def test_http_server_creates_sse_transport(self) -> None:
        """HttpServer should create SSE transport with /mcp endpoint."""
        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
        )

        # SSE transport should be configured for /mcp endpoint
        assert http_server.sse_transport._endpoint == "/mcp"


class TestHttpServerApp:
    """Test Starlette app creation."""

    def test_create_app_has_routes(self) -> None:
        """Created app should have health, sse, and mcp routes."""
        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
        )
        app = http_server.create_app()

        # Get route paths
        route_paths = [route.path for route in app.routes]

        assert "/health" in route_paths
        assert "/sse" in route_paths
        assert "/mcp" in route_paths


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy(self) -> None:
        """Health endpoint should return healthy status."""
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server"] == "clams"
        assert "version" in data


class TestDaemonManagement:
    """Test daemon lifecycle functions."""

    def test_get_pid_file_default(self) -> None:
        """get_pid_file should return default path."""
        from pathlib import Path

        from clams.server.http import get_pid_file

        pid_file = get_pid_file()
        assert pid_file == Path.home() / ".clams" / "server.pid"

    def test_get_pid_file_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_pid_file should use CLAMS_PID_FILE env var."""
        from pathlib import Path

        monkeypatch.setenv("CLAMS_PID_FILE", "/tmp/test.pid")

        # Reload to pick up env var
        import importlib

        import clams.server.http
        from clams.server.http import get_pid_file
        importlib.reload(clams.server.http)

        pid_file = get_pid_file()
        assert pid_file == Path("/tmp/test.pid")

    def test_is_server_running_no_pid_file(self, tmp_path: Path) -> None:
        """is_server_running should return False if no PID file."""

        with patch("clams.server.http.get_pid_file", return_value=tmp_path / "nonexistent.pid"):
            from clams.server.http import is_server_running

            assert is_server_running() is False

    def test_is_server_running_stale_pid(self, tmp_path: Path) -> None:
        """is_server_running should return False for stale PID."""

        pid_file = tmp_path / "server.pid"
        pid_file.write_text("99999999")  # Non-existent PID

        with patch("clams.server.http.get_pid_file", return_value=pid_file):
            from clams.server.http import is_server_running

            assert is_server_running() is False
