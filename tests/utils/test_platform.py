"""Tests for platform detection module (SPEC-033)."""

import platform as stdlib_platform
import shutil
import sys

import pytest

from clams.utils.platform import (
    PlatformInfo,
    check_requirements,
    format_report,
    get_platform_info,
)


class TestGetPlatformInfo:
    """Tests for get_platform_info()."""

    def test_returns_platform_info(self) -> None:
        """get_platform_info returns PlatformInfo instance."""
        info = get_platform_info()
        assert isinstance(info, PlatformInfo)

    def test_detects_os(self) -> None:
        """Correctly detects current OS."""
        info = get_platform_info()
        expected_os = stdlib_platform.system().lower()
        assert info.os_name == expected_os

        if expected_os == "darwin":
            assert info.is_macos is True
            assert info.is_linux is False
        elif expected_os == "linux":
            assert info.is_macos is False
            assert info.is_linux is True

    def test_detects_machine_architecture(self) -> None:
        """Correctly detects machine architecture."""
        info = get_platform_info()
        expected_machine = stdlib_platform.machine()
        assert info.machine == expected_machine

    def test_apple_silicon_detection(self) -> None:
        """Apple Silicon detected correctly on macOS arm64."""
        info = get_platform_info()

        if info.is_macos and info.machine == "arm64":
            assert info.is_apple_silicon is True
        else:
            # Either not macOS or not arm64
            if not info.is_macos:
                assert info.is_apple_silicon is False

    def test_caches_result(self) -> None:
        """Result is cached (same object returned)."""
        info1 = get_platform_info()
        info2 = get_platform_info()
        assert info1 is info2

    def test_ripgrep_detection(self) -> None:
        """Ripgrep detection matches shutil.which result."""
        info = get_platform_info()
        expected = shutil.which("rg") is not None
        assert info.has_ripgrep == expected

        if info.has_ripgrep:
            assert info.ripgrep_path is not None
        else:
            assert info.ripgrep_path is None

    def test_docker_detection(self) -> None:
        """Docker detection matches shutil.which result."""
        info = get_platform_info()
        has_docker_binary = shutil.which("docker") is not None
        assert info.has_docker == has_docker_binary

        if info.has_docker:
            assert info.docker_path is not None
        else:
            assert info.docker_path is None
            # If no docker binary, daemon cannot be running
            assert info.docker_running is False

    def test_respects_qdrant_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLAMS_QDRANT_URL environment variable is respected."""
        # Clear cache to test with new env var
        get_platform_info.cache_clear()

        custom_url = "http://custom-qdrant:6333"
        monkeypatch.setenv("CLAMS_QDRANT_URL", custom_url)

        info = get_platform_info()
        assert info.qdrant_url == custom_url

        # Cleanup
        get_platform_info.cache_clear()

    def test_qdrant_url_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default Qdrant URL is localhost:6333."""
        get_platform_info.cache_clear()

        # Remove CLAMS_QDRANT_URL if set
        monkeypatch.delenv("CLAMS_QDRANT_URL", raising=False)

        info = get_platform_info()
        assert info.qdrant_url == "http://localhost:6333"

        # Cleanup
        get_platform_info.cache_clear()

    def test_platform_info_is_frozen(self) -> None:
        """PlatformInfo is immutable (frozen dataclass)."""
        info = get_platform_info()

        with pytest.raises(AttributeError):
            info.os_name = "modified"  # type: ignore[misc]


class TestCheckRequirements:
    """Tests for check_requirements()."""

    def test_empty_requirements_pass(self) -> None:
        """Empty requirements list always passes."""
        ok, missing = check_requirements([])
        assert ok is True
        assert missing == []

    def test_invalid_requirement_raises(self) -> None:
        """Invalid requirement name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown requirement"):
            check_requirements(["invalid_requirement"])

    def test_invalid_requirement_shows_valid_names(self) -> None:
        """ValueError message includes list of valid requirement names."""
        with pytest.raises(ValueError) as exc_info:
            check_requirements(["bogus_req"])

        error_msg = str(exc_info.value)
        assert "mps" in error_msg
        assert "cuda" in error_msg
        assert "ripgrep" in error_msg
        assert "docker" in error_msg
        assert "qdrant" in error_msg

    def test_returns_missing_requirements(self) -> None:
        """Missing requirements are returned in second element."""
        # Test with a requirement we know might not be met
        info = get_platform_info()

        if not info.qdrant_available:
            ok, missing = check_requirements(["qdrant"])
            assert ok is False
            assert "qdrant" in missing

    def test_returns_all_missing(self) -> None:
        """All missing requirements are listed."""
        info = get_platform_info()

        # Build list of unavailable requirements
        unavailable = []
        if not info.qdrant_available:
            unavailable.append("qdrant")
        if not info.docker_running:
            unavailable.append("docker")
        if not info.cuda_available:
            unavailable.append("cuda")

        if len(unavailable) >= 2:
            ok, missing = check_requirements(unavailable)
            assert ok is False
            for req in unavailable:
                assert req in missing

    def test_all_valid_requirement_names(self) -> None:
        """All documented requirement names are valid."""
        valid_names = [
            "mps",
            "cuda",
            "ripgrep",
            "docker",
            "qdrant",
            "macos",
            "linux",
            "apple_silicon",
            "nvidia_gpu",
        ]

        # Should not raise
        for name in valid_names:
            check_requirements([name])

    def test_os_requirements(self) -> None:
        """OS requirements correctly reflect current platform."""
        ok_macos, missing_macos = check_requirements(["macos"])
        ok_linux, missing_linux = check_requirements(["linux"])

        if sys.platform == "darwin":
            assert ok_macos is True
            assert ok_linux is False
        elif sys.platform.startswith("linux"):
            assert ok_macos is False
            assert ok_linux is True


class TestFormatReport:
    """Tests for format_report()."""

    def test_produces_string(self) -> None:
        """format_report produces non-empty string."""
        info = get_platform_info()
        report = format_report(info)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_contains_platform_info(self) -> None:
        """Report contains platform information."""
        info = get_platform_info()
        report = format_report(info)

        assert "Platform:" in report
        assert "PyTorch Backends:" in report
        assert "External Tools:" in report
        assert "Services:" in report

    def test_contains_mps_status(self) -> None:
        """Report includes MPS availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "MPS:" in report

    def test_contains_cuda_status(self) -> None:
        """Report includes CUDA availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "CUDA:" in report

    def test_contains_ripgrep_status(self) -> None:
        """Report includes ripgrep availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "ripgrep:" in report

    def test_contains_docker_status(self) -> None:
        """Report includes docker availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "docker:" in report

    def test_contains_qdrant_status(self) -> None:
        """Report includes Qdrant availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "Qdrant:" in report
        # URL should be in the report
        assert info.qdrant_url in report

    def test_macos_format(self) -> None:
        """macOS report includes architecture info."""
        info = get_platform_info()
        report = format_report(info)

        if info.is_macos:
            assert "macOS" in report
            assert "Architecture:" in report
            if info.is_apple_silicon:
                assert "Apple Silicon" in report
            else:
                assert "Intel" in report

    def test_linux_format(self) -> None:
        """Linux report includes architecture info."""
        info = get_platform_info()
        report = format_report(info)

        if info.is_linux:
            assert "Linux" in report
            assert "Architecture:" in report


class TestPlatformMarkers:
    """Tests verifying platform markers work correctly."""

    @pytest.mark.requires_ripgrep
    def test_requires_ripgrep_runs_when_available(self) -> None:
        """Test with requires_ripgrep marker runs only when ripgrep available."""
        # If we get here, ripgrep must be available
        assert shutil.which("rg") is not None

    @pytest.mark.macos_only
    def test_macos_only_runs_on_macos(self) -> None:
        """Test with macos_only marker runs only on macOS."""
        # If we get here, must be macOS
        assert sys.platform == "darwin"

    @pytest.mark.linux_only
    def test_linux_only_runs_on_linux(self) -> None:
        """Test with linux_only marker runs only on Linux."""
        # If we get here, must be Linux
        assert sys.platform.startswith("linux")

    @pytest.mark.requires_mps
    def test_requires_mps_runs_when_available(self) -> None:
        """Test with requires_mps marker runs only when MPS available."""
        # If we get here, MPS must be available
        import torch

        assert torch.backends.mps.is_available()

    @pytest.mark.requires_cuda
    def test_requires_cuda_runs_when_available(self) -> None:
        """Test with requires_cuda marker runs only when CUDA available."""
        # If we get here, CUDA must be available
        import torch

        assert torch.cuda.is_available()

    @pytest.mark.requires_docker
    def test_requires_docker_runs_when_available(self) -> None:
        """Test with requires_docker marker runs only when Docker running."""
        info = get_platform_info()
        assert info.docker_running is True

    @pytest.mark.requires_qdrant
    def test_requires_qdrant_runs_when_available(self) -> None:
        """Test with requires_qdrant marker runs only when Qdrant available."""
        info = get_platform_info()
        assert info.qdrant_available is True


class TestPlatformInfoFixture:
    """Tests for the platform_info pytest fixture."""

    def test_fixture_available(self, platform_info: PlatformInfo) -> None:
        """platform_info fixture is available and returns correct type."""
        assert isinstance(platform_info, PlatformInfo)

    def test_fixture_matches_get_platform_info(
        self, platform_info: PlatformInfo
    ) -> None:
        """Fixture returns same instance as get_platform_info()."""
        direct_info = get_platform_info()
        assert platform_info is direct_info

    def test_fixture_has_all_attributes(self, platform_info: PlatformInfo) -> None:
        """Fixture has all expected attributes."""
        # Check all documented attributes exist
        assert hasattr(platform_info, "os_name")
        assert hasattr(platform_info, "os_version")
        assert hasattr(platform_info, "machine")
        assert hasattr(platform_info, "is_macos")
        assert hasattr(platform_info, "is_linux")
        assert hasattr(platform_info, "is_apple_silicon")
        assert hasattr(platform_info, "has_nvidia_gpu")
        assert hasattr(platform_info, "mps_available")
        assert hasattr(platform_info, "cuda_available")
        assert hasattr(platform_info, "has_ripgrep")
        assert hasattr(platform_info, "ripgrep_path")
        assert hasattr(platform_info, "has_docker")
        assert hasattr(platform_info, "docker_path")
        assert hasattr(platform_info, "docker_running")
        assert hasattr(platform_info, "qdrant_available")
        assert hasattr(platform_info, "qdrant_url")
