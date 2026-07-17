"""Pytest fixtures shared across test packages."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def archive_tmp(tmp_path: Path) -> Iterator[Path]:
    target = tmp_path / "archive"
    target.mkdir()
    yield target
