"""Shared test fixtures for speclord."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_repo(fixtures_dir: Path) -> Path:
    """Path to the valid-repo test fixture."""
    return fixtures_dir / "valid-repo"
