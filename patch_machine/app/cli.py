"""Typer-based CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from patch_machine.app.container import Container
from patch_machine.observability import configure_logging, get_logger

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Patch Machine CLI")


@app.command()
def serve(
    host: str | None = typer.Option(None, help="HTTP bind host (overrides settings)."),
    port: int | None = typer.Option(None, help="HTTP bind port (overrides settings)."),
) -> None:
    """Run the FastAPI server + background orchestrator + Discord bot."""
    container = Container.build()
    settings = container.settings
    configure_logging(settings.log_level)
    uvicorn.run(
        "patch_machine.app.main:create_app",
        host=host or settings.http_host,
        port=port or settings.http_port,
        factory=True,
        log_level=settings.log_level.lower(),
    )


@app.command()
def reindex(archive_dir: Path = typer.Option(Path("./archive"))) -> None:
    """Rebuild index MD files from existing archive logs.

    Useful when the archive is imported from another machine or after a manual
    edit.  The logic lives in ``ArchiveWriter`` so it mirrors the production
    write path exactly.
    """
    from patch_machine.archive.schema import parse_front_matter
    from patch_machine.archive.writer import ArchiveWriter

    writer = ArchiveWriter(archive_dir)
    count = 0
    for log_path in archive_dir.rglob("*.md"):
        try:
            rel_parts = log_path.relative_to(archive_dir).parts
        except ValueError:
            continue
        if len(rel_parts) < 3 or rel_parts[0] in {"index", "knowledge_base"}:
            continue
        if not rel_parts[0].isdigit():
            continue
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        fm = parse_front_matter(text)
        if not fm:
            continue
        keywords = fm.get("keywords") or []
        modules = fm.get("modules") or []
        author = fm.get("author", "")
        writer.index.update(
            log_path=log_path,
            keywords=keywords,
            modules=modules,
            author=author,
        )
        count += 1
    writer.refresh_status()
    typer.echo(f"reindexed {count} log(s)")


@app.command()
def replay(jsonl_path: Path) -> None:
    """Replay past events recorded as JSONL (one IssueEvent per line)."""
    import asyncio

    from patch_machine.domain.entities import IssueEvent

    container = Container.build()
    log = get_logger(component="cli.replay")

    async def _run() -> None:
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            event = IssueEvent.model_validate(payload)
            log.info("replay.event", event_id=str(event.event_id), source=event.source)
            await container.orchestrator.handle(event)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
