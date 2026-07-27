"""Path-traversal guard shared by every archive reader.

Anything that turns caller-supplied (or index-stored) text into a filesystem
path must go through :func:`resolve_within`. Keeping one implementation means a
hardening fix lands everywhere at once, and makes the guard greppable.
"""

from __future__ import annotations

from pathlib import Path


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root``, refusing to escape it.

    ``..`` segments, absolute paths and symlinks pointing outside ``root`` are
    all rejected, because ``resolve()`` runs before the containment check.
    """

    if not relative or not relative.strip():
        raise ValueError("path 는 필수입니다.")
    cleaned = relative.strip().lstrip("/")
    if "\x00" in cleaned:
        raise ValueError("path 에 잘못된 문자가 포함되어 있습니다.")
    resolved_root = root.resolve()
    candidate = (resolved_root / cleaned).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("archive 외부 경로는 접근할 수 없습니다.") from exc
    return candidate
