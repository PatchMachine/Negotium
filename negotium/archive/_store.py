"""Shared locked-file persistence helpers for archive stores."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, TypeVar

import portalocker

T = TypeVar("T")


def read_json_file(
    path: Path, *, default: Callable[[], T] | None = None
) -> Any | T | None:
    """Read JSON while coordinating with writers.

    Missing and empty files return a newly-created default value when supplied,
    otherwise ``None``.
    """
    if not path.exists():
        return default() if default is not None else None
    with portalocker.Lock(path, "r", encoding="utf-8", timeout=5) as handle:
        raw = handle.read()
    if not raw.strip():
        return default() if default is not None else None
    return json.loads(raw)


def write_json_file(path: Path, payload: Any) -> None:
    """Serialize JSON to a file protected by an exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with portalocker.Lock(path, "w", encoding="utf-8", timeout=5) as handle:
        handle.write(rendered)


def append_jsonl_line(
    path: Path, payload: Mapping[str, object], *, sort_keys: bool = False
) -> None:
    """Append one JSON object to a JSON Lines file under an exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=sort_keys)
    with portalocker.Lock(path, "a", encoding="utf-8", timeout=5) as handle:
        handle.write(rendered)
        handle.write("\n")


def iter_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
    """Yield valid JSON objects from a JSON Lines file."""
    if not path.exists():
        return
    with portalocker.Lock(path, "r", encoding="utf-8", timeout=5) as handle:
        lines = handle.readlines()
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload
