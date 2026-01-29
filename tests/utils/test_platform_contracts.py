"""Tests for PlatformInfo hash/eq contract.

PlatformInfo uses @dataclass(frozen=True), which auto-generates
__hash__ and __eq__ based on all fields. This is safe but should
be tested to catch regressions if fields are added or the decorator
is changed.

Reference: SPEC-048 - Hash/Eq Contract Tests for Other Hashable Classes
"""

from typing import Any

from clams.utils.platform import PlatformInfo


class TestPlatformInfoContract:
    """Verify PlatformInfo maintains hash/eq contract.

    Since PlatformInfo is a frozen dataclass, its hash/eq is
    auto-generated based on all fields. This should always satisfy
    the contract, but we test to catch regressions.
    """

    def test_equal_instances_have_equal_hashes(self) -> None:
        """INVARIANT: if a == b then hash(a) == hash(b)."""
        info1 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )
        info2 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )

        assert info1 == info2, "Identical instances must be equal"
        assert hash(info1) == hash(info2), (
            "Contract violation: equal instances must have equal hashes"
        )

    def test_different_instances_are_not_equal(self) -> None:
        """Instances with different fields must not be equal."""
        base = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )
        different = PlatformInfo(
            os_name="linux",  # Different OS
            os_version="Linux-6.0",
            machine="x86_64",
            is_macos=False,
            is_linux=True,
            is_apple_silicon=False,
            has_nvidia_gpu=True,
            mps_available=False,
            cuda_available=True,
            has_ripgrep=True,
            ripgrep_path="/usr/bin/rg",
            has_docker=True,
            docker_path="/usr/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )

        assert base != different, "Different instances must not be equal"

    def test_single_field_difference(self) -> None:
        """Changing any single field should make instances unequal."""
        base_kwargs: dict[str, Any] = {
            "os_name": "darwin",
            "os_version": "macOS-14.0",
            "machine": "arm64",
            "is_macos": True,
            "is_linux": False,
            "is_apple_silicon": True,
            "has_nvidia_gpu": False,
            "mps_available": True,
            "cuda_available": False,
            "has_ripgrep": True,
            "ripgrep_path": "/usr/local/bin/rg",
            "has_docker": True,
            "docker_path": "/usr/local/bin/docker",
            "docker_running": True,
            "qdrant_available": True,
            "qdrant_url": "http://localhost:6333",
        }

        base = PlatformInfo(**base_kwargs)

        # Test each boolean field flip
        for field in [
            "is_macos", "is_linux", "is_apple_silicon",
            "has_nvidia_gpu", "mps_available", "cuda_available",
            "has_ripgrep", "has_docker", "docker_running",
            "qdrant_available",
        ]:
            modified = dict(base_kwargs)
            modified[field] = not modified[field]
            different = PlatformInfo(**modified)
            assert base != different, f"Changing {field} should make unequal"


class TestPlatformInfoSetBehavior:
    """Test set operations with PlatformInfo."""

    def test_set_membership_consistent(self) -> None:
        """Equal instances have consistent set membership."""
        info1 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )
        info2 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )

        s: set[PlatformInfo] = {info1}
        assert info2 in s, "Equal instance not found in set (contract violation)"

    def test_set_deduplication(self) -> None:
        """Adding equal instances should result in one item."""
        kwargs: dict[str, Any] = {
            "os_name": "darwin",
            "os_version": "macOS-14.0",
            "machine": "arm64",
            "is_macos": True,
            "is_linux": False,
            "is_apple_silicon": True,
            "has_nvidia_gpu": False,
            "mps_available": True,
            "cuda_available": False,
            "has_ripgrep": True,
            "ripgrep_path": "/usr/local/bin/rg",
            "has_docker": True,
            "docker_path": "/usr/local/bin/docker",
            "docker_running": True,
            "qdrant_available": True,
            "qdrant_url": "http://localhost:6333",
        }

        s: set[PlatformInfo] = set()
        for _ in range(3):
            s.add(PlatformInfo(**kwargs))

        assert len(s) == 1, f"Expected 1 item after deduplication, got {len(s)}"


class TestPlatformInfoDictBehavior:
    """Test dict operations with PlatformInfo as key."""

    def test_dict_key_lookup(self) -> None:
        """Equal instances can find dict entries."""
        info1 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )
        info2 = PlatformInfo(
            os_name="darwin",
            os_version="macOS-14.0",
            machine="arm64",
            is_macos=True,
            is_linux=False,
            is_apple_silicon=True,
            has_nvidia_gpu=False,
            mps_available=True,
            cuda_available=False,
            has_ripgrep=True,
            ripgrep_path="/usr/local/bin/rg",
            has_docker=True,
            docker_path="/usr/local/bin/docker",
            docker_running=True,
            qdrant_available=True,
            qdrant_url="http://localhost:6333",
        )

        d: dict[PlatformInfo, str] = {info1: "cached_value"}
        assert d.get(info2) == "cached_value", (
            "Equal instance cannot find dict entry (contract violation)"
        )
