"""Archive writer: coordinates the rolling status document under archive/."""

from __future__ import annotations

from pathlib import Path

import portalocker

from negotium.archive.status import StatusManager
from negotium.observability import get_logger


class ArchiveWriter:
    """Owns the archive directory root and the rolling status document.

    The writer is the **single consumer** of the archive filesystem so we can
    rely on portalocker + serial writes rather than a full database.
    """

    def __init__(self, archive_dir: Path) -> None:
        self._dir = archive_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._status = StatusManager(self._dir)
        self._log = get_logger(component="archive.writer")

    @property
    def status(self) -> StatusManager:
        return self._status


def write_through_lock(path: Path, content: str) -> None:
    """Exposed helper in case other modules need a synchronized overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with portalocker.Lock(path, "w", encoding="utf-8", timeout=5) as fh:
        fh.write(content)
