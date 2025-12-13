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
        mock_tool_registry: dict = {}

        http_server = HttpServer(
            server=mock_server,
            services=mock_services,
            tool_registry=mock_tool_registry,
            host="127.0.0.1",
            port=6335,
        )

        assert http_server.server == mock_server
        assert http_server.services == mock_services
        assert http_server.tool_registry == mock_tool_registry
        assert http_server.host == "127.0.0.1"
        assert http_server.port == 6335

    def test_http_server_creates_sse_transport(self) -> None:
        """HttpServer should create SSE transport with /sse endpoint."""
        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={},
        )

        # SSE transport should be configured for /sse endpoint
        assert http_server.sse_transport._endpoint == "/sse"


class TestHttpServerApp:
    """Test Starlette app creation."""

    def test_create_app_handles_routes(self) -> None:
        """Created app should handle health, sse, and api/call routes.

        Note: create_app() returns a wrapper ASGI function that intercepts /sse
        and delegates other routes to Starlette. We test via TestClient instead
        of inspecting routes directly.
        """
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={},
        )
        app = http_server.create_app()
        client = TestClient(app)

        # Health endpoint should be accessible
        response = client.get("/health")
        assert response.status_code == 200

        # API call endpoint should be accessible (will return 400 due to missing params)
        response = client.post("/api/call", json={})
        assert response.status_code == 400  # Missing tool name, but route exists


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
            tool_registry={},
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server"] == "clams"
        assert "version" in data


class TestApiCallEndpoint:
    """Test API call endpoint for hooks."""

    @pytest.mark.asyncio
    async def test_api_call_invokes_tool(self) -> None:
        """API call endpoint should invoke tool from registry."""
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        # Create a mock tool
        async def mock_ping() -> str:
            return "pong"

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={"ping": mock_ping},
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "ping", "arguments": {}}},
        )

        assert response.status_code == 200
        assert response.json()["result"] == "pong"

    @pytest.mark.asyncio
    async def test_api_call_unknown_tool(self) -> None:
        """API call endpoint should return 404 for unknown tool."""
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={},
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "unknown", "arguments": {}}},
        )

        assert response.status_code == 404
        assert "Unknown tool" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_api_call_missing_tool_name(self) -> None:
        """API call endpoint should return 400 if tool name missing."""
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={},
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.post(
            "/api/call",
            json={"method": "tools/call", "params": {}},
        )

        assert response.status_code == 400
        assert "Missing tool name" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_api_call_returns_dict(self) -> None:
        """API call endpoint should return dict results directly."""
        from starlette.testclient import TestClient

        from clams.server.http import HttpServer

        async def mock_tool() -> dict:
            return {"key": "value", "count": 42}

        http_server = HttpServer(
            server=MagicMock(),
            services=MagicMock(),
            tool_registry={"test_tool": mock_tool},
        )
        app = http_server.create_app()
        client = TestClient(app)

        response = client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "test_tool", "arguments": {}}},
        )

        assert response.status_code == 200
        assert response.json() == {"key": "value", "count": 42}


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
