"""Regression test for BUG-057: Worker permission model documentation.

This bug is a design task - the deliverable is documentation, not code.
This test verifies the required documentation exists.
"""

from pathlib import Path


def test_worker_permission_model_doc_exists() -> None:
    """Verify the worker permission model documentation was created."""
    doc_path = Path(__file__).parent.parent / "docs" / "worker-permission-model.md"
    assert doc_path.exists(), f"Expected {doc_path} to exist"
    content = doc_path.read_text()
    assert len(content) > 1000, "Documentation should have substantial content"
    assert "permission" in content.lower(), "Documentation should discuss permissions"


def test_proposal_exists() -> None:
    """Verify the design proposal was created."""
    proposal_path = (
        Path(__file__).parent.parent / "planning_docs" / "BUG-057" / "proposal.md"
    )
    assert proposal_path.exists(), f"Expected {proposal_path} to exist"


def test_decisions_documented() -> None:
    """Verify architectural decisions were documented."""
    decisions_path = (
        Path(__file__).parent.parent / "planning_docs" / "BUG-057" / "decisions.md"
    )
    assert decisions_path.exists(), f"Expected {decisions_path} to exist"
