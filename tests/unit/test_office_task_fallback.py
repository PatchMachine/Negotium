"""Office tasks must degrade to the offline scaffold when the LLM is unreachable."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException, status

from negotium.app.api import _shared
from negotium.app.container import Container
from negotium.app.settings import Settings


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )


async def test_provider_failure_returns_offline_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh installs (no API key, no GPU) must not 500 out of setup/analyze."""
    container = _container(tmp_path)

    async def failing(*args: Any, **kwargs: Any) -> Any:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No module named 'x'")

    monkeypatch.setattr(_shared, "_complete_with_provider", failing)

    text = await _shared._complete_office_task(container, "회의 내용 요약", task="memory_summary")
    assert text.strip(), "fallback markdown must be returned instead of raising"


async def test_firewall_block_still_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)

    async def blocked(*args: Any, **kwargs: Any) -> Any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="firewall blocked")

    monkeypatch.setattr(_shared, "_complete_with_provider", blocked)

    with pytest.raises(HTTPException) as excinfo:
        await _shared._complete_office_task(container, "요약", task="memory_summary")
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
