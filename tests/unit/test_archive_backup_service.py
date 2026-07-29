"""Archive git backup: init, exclusions, idempotent commits, push, stats."""

from __future__ import annotations

import subprocess
from pathlib import Path

from negotium.app.container import Container
from negotium.app.services.archive_backup_service import (
    MANAGED_GITIGNORE,
    backup_stats,
    commit_archive,
    ensure_repo,
    push_archive,
    run_backup,
)
from negotium.app.settings import Settings
from negotium.archive.automation import AutomationConfig, BackupConfig


def _git_out(archive: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(archive), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _container(tmp_path: Path, *, remote_url: str = "") -> Container:
    container = Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )
    container.automation.write_config(
        AutomationConfig(backup=BackupConfig(enabled=True, remote_url=remote_url))
    )
    return container


def _seed_archive(archive: Path) -> None:
    (archive / "documents").mkdir(parents=True, exist_ok=True)
    (archive / "documents" / "minutes.md").write_text("# 회의록\n내용", encoding="utf-8")
    secrets = archive / "secrets"
    secrets.mkdir(parents=True, exist_ok=True)
    (secrets / "local_master.key").write_text("SUPER-SECRET", encoding="utf-8")
    (archive / "auth.json").write_text("{}", encoding="utf-8")
    index = archive / "search_index"
    index.mkdir(parents=True, exist_ok=True)
    (index / "manifest.json").write_text("{}", encoding="utf-8")


def test_ensure_repo_initializes_and_writes_managed_gitignore(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    assert ensure_repo(archive) is True
    assert (archive / ".git").exists()
    assert (archive / ".gitignore").read_text(encoding="utf-8") == MANAGED_GITIGNORE

    # Idempotent, and a tampered .gitignore is restored.
    (archive / ".gitignore").write_text("secrets 커밋해도 됨", encoding="utf-8")
    assert ensure_repo(archive) is True
    assert (archive / ".gitignore").read_text(encoding="utf-8") == MANAGED_GITIGNORE


async def test_backup_commits_documents_but_never_secrets(tmp_path: Path) -> None:
    container = _container(tmp_path)
    archive = container.settings.archive_dir
    _seed_archive(archive)

    result = await run_backup(container)

    assert result["committed"] is True
    tracked = _git_out(archive, "ls-files")
    assert "documents/minutes.md" in tracked
    assert "secrets/local_master.key" not in tracked, "master key must never enter history"
    assert "auth.json" not in tracked
    assert "automation.json" not in tracked, "config may carry a tokenized remote URL"
    assert "search_index/manifest.json" not in tracked


async def test_clean_tree_backup_is_a_noop(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _seed_archive(container.settings.archive_dir)

    first = await run_backup(container)
    second = await run_backup(container)

    assert first["committed"] is True
    assert second["committed"] is False, "clean tree must not create empty commits"
    stats = backup_stats(container.settings.archive_dir)
    assert stats["commits"] == 1


async def test_push_to_local_bare_remote(tmp_path: Path) -> None:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    container = _container(tmp_path, remote_url=str(bare))
    _seed_archive(container.settings.archive_dir)

    result = await run_backup(container)

    assert result["committed"] is True
    assert result["pushed"] is True
    remote_count = subprocess.run(
        ["git", "rev-list", "--count", "main"],
        cwd=str(bare),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert int(remote_count) >= 1


def test_push_failure_returns_reason_without_url(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    ensure_repo(archive)
    (archive / "note.md").write_text("x", encoding="utf-8")
    commit_archive(archive, message="seed")

    secret_url = "https://user:token123@example.invalid/repo.git"
    ok, reason = push_archive(archive, secret_url)

    assert ok is False
    assert "token123" not in reason, "the tokenized URL must not leak into the reason"


def test_backup_stats_shape(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    assert backup_stats(archive)["initialized"] is False

    ensure_repo(archive)
    (archive / "note.md").write_text("x", encoding="utf-8")
    commit_archive(archive, message="seed")
    (archive / "note.md").write_text("y", encoding="utf-8")

    stats = backup_stats(archive)
    assert stats["initialized"] is True
    assert stats["commits"] == 1
    assert stats["last_commit_at"]
    assert stats["dirty"] is True
