"""Utility functions and constants for code indexing."""

import hashlib

# Extension to language mapping (shared between parser and indexer)
# Note: Lua is not included as tree-sitter-lua is not available on PyPI
EXTENSION_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".swift": "swift",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".sql": "sql",
}


def generate_unit_id(project: str, file_path: str, qualified_name: str) -> str:
    """Generate unique ID for a semantic unit.

    Uses SHA-256 hash of project:file_path:qualified_name.
    Truncated to 32 chars (128 bits) for readability.
    """
    content = f"{project}:{file_path}:{qualified_name}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def compute_file_hash(path: str) -> str:
    """Compute SHA-256 hash of file contents."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
