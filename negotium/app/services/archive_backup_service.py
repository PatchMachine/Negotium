"""Automatic git versioning of the runtime archive.

The archive gets its own nested git repository (the outer repo ignores
``/archive/`` entirely, so nesting is safe). The automation scheduler commits
dirty state periodically — audit trail and rollback for the MD-GitOps store —
and optionally pushes to an admin-configured remote.

Never committed (managed ``.gitignore``): ``secrets/`` (plaintext master
key), credential/session state (``auth.json``), the automation config
(``automation.json`` may carry a tokenized remote URL), and high-churn
derived caches. A commit racing an in-place store write may capture a
partially-written file; the next interval commit corrects it.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from negotium.app.container import Container

_log = structlog.get_logger(component="archive_backup")

_GIT_TIMEOUT_SECONDS = 60.0
_GIT_IDENTITY = [
    "-c",
    "user.name=Negotium Archive",
    "-c",
    "user.email=archive@negotium.local",
]

MANAGED_GITIGNORE = """\
# Managed by Negotium archive backup — do not edit; rewritten on every run.
# Secrets: the plaintext master key must never enter history.
secrets/
# Credential/session state and configs that may carry tokens.
auth.json
automation.json
# High-churn derived caches (rebuildable).
search_index/
volatile_memory/
token_usage/
context_firewall/
mcp_hub/
ai_jobs/
agent_execution/
notifications.json
"""


def _git(archive_dir: Path, *args: str) -> tuple[bool, str]:
    """Run one git command inside the archive; never raises."""
    argv = ["git", *_GIT_IDENTITY, *args]
    try:
        completed = subprocess.run(
            argv,
            cwd=str(archive_dir),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, output.strip()


def ensure_repo(archive_dir: Path) -> bool:
    """Initialize the nested repo if missing and (re)write the managed .gitignore."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    if not (archive_dir / ".git").exists():
        ok, output = _git(archive_dir, "init", "-q")
        if not ok:
            _log.warning("archive_backup.init_failed", error=output)
            return False
    gitignore = archive_dir / ".gitignore"
    if not gitignore.exists() or gitignore.read_text(encoding="utf-8") != MANAGED_GITIGNORE:
        gitignore.write_text(MANAGED_GITIGNORE, encoding="utf-8")
    return True


def is_dirty(archive_dir: Path) -> bool:
    ok, output = _git(archive_dir, "status", "--porcelain")
    return ok and bool(output.strip())


def commit_archive(archive_dir: Path, *, message: str) -> tuple[bool, bool]:
    """Returns ``(ok, committed)`` — clean tree is a successful no-op."""
    if not is_dirty(archive_dir):
        return True, False
    ok, output = _git(archive_dir, "add", "-A")
    if not ok:
        _log.warning("archive_backup.add_failed", error=output)
        return False, False
    ok, output = _git(archive_dir, "commit", "-q", "-m", message)
    if not ok:
        _log.warning("archive_backup.commit_failed", error=output)
        return False, False
    return True, True


def push_archive(archive_dir: Path, remote_url: str) -> tuple[bool, str]:
    """Push HEAD to the configured remote. The URL may embed a token — it is
    passed to git only and never logged or returned in failure reasons."""
    if not remote_url.strip():
        return True, ""
    ok, _output = _git(archive_dir, "remote", "get-url", "origin")
    if ok:
        set_ok, _ = _git(archive_dir, "remote", "set-url", "origin", remote_url)
    else:
        set_ok, _ = _git(archive_dir, "remote", "add", "origin", remote_url)
    if not set_ok:
        return False, "remote 설정 실패"
    ok, output = _git(archive_dir, "push", "-q", "origin", "HEAD:refs/heads/main")
    if not ok:
        _log.warning("archive_backup.push_failed")
        return False, f"push 실패 (exit output {len(output)} chars)"
    return True, ""


def backup_stats(archive_dir: Path) -> dict[str, object]:
    initialized = (archive_dir / ".git").exists()
    commits = 0
    last_commit_at = ""
    dirty = False
    if initialized:
        ok, output = _git(archive_dir, "rev-list", "--count", "HEAD")
        if ok:
            try:
                commits = int(output.strip())
            except ValueError:
                commits = 0
        ok, output = _git(archive_dir, "log", "-1", "--format=%cI")
        if ok:
            last_commit_at = output.strip()
        dirty = is_dirty(archive_dir)
    return {
        "initialized": initialized,
        "commits": commits,
        "last_commit_at": last_commit_at,
        "dirty": dirty,
    }


async def run_backup(container: Container) -> dict[str, Any]:
    """Commit dirty archive state; push when a remote is configured."""
    archive_dir = container.settings.archive_dir.resolve()
    remote_url = container.automation.read_config().backup.remote_url

    def _run() -> dict[str, Any]:
        if not ensure_repo(archive_dir):
            return {"committed": False, "pushed": None, "reason": "git init 실패"}
        message = f"archive backup {datetime.now(UTC).isoformat(timespec='seconds')}"
        ok, committed = commit_archive(archive_dir, message=message)
        if not ok:
            return {"committed": False, "pushed": None, "reason": "commit 실패"}
        pushed: bool | None = None
        reason = ""
        if remote_url.strip():
            push_ok, push_reason = push_archive(archive_dir, remote_url)
            pushed = push_ok
            reason = push_reason
        result: dict[str, Any] = {"committed": committed, "pushed": pushed}
        if reason:
            result["reason"] = reason
        return result

    return await asyncio.to_thread(_run)


__all__ = [
    "MANAGED_GITIGNORE",
    "backup_stats",
    "commit_archive",
    "ensure_repo",
    "is_dirty",
    "push_archive",
    "run_backup",
]
