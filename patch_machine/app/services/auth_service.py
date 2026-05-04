"""Authentication and access control service boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patch_machine.app.container import Container


def require_permission(container: Container, credential: str | None, permission: str) -> str:
    from patch_machine.app.api import _require

    return _require(container, credential, permission)
