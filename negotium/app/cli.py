"""Typer-based CLI entry point."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import typer
import uvicorn

from negotium.app.container import Container
from negotium.observability import configure_logging

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Negotium CLI")


def _load_env_file() -> None:
    """Load ``.env`` into the process environment for server runtimes only.

    Nested settings models (e.g. ``LlmSettings``) are built via default_factory
    and read only ``os.environ``, so provider keys/models placed in ``.env`` are
    otherwise dropped in the backend. We do this at the CLI entry point rather
    than in the settings model itself so the test suite stays hermetic (it never
    invokes the CLI and must not pick up a developer's real ``.env`` keys).
    Existing environment variables win over ``.env`` (``override=False``).
    """

    from dotenv import load_dotenv

    load_dotenv(override=False)


def _build_frontend(served_dist: Path | None) -> None:
    """Run ``npm run build`` so the console can be served from this process."""
    from negotium.app.console_site import default_frontend_dist

    dist = default_frontend_dist()
    frontend = dist.parent
    npm = shutil.which("npm")
    if npm is None:
        raise typer.BadParameter("npm not found; install Node 20+ or drop --build-frontend")
    if not (frontend / "node_modules").is_dir():
        typer.echo("프론트엔드 의존성을 설치합니다 (npm ci)...")
        subprocess.run([npm, "ci", "--prefix", str(frontend)], check=True)
    typer.echo("콘솔을 빌드합니다 (npm run build)...")
    subprocess.run([npm, "run", "build", "--prefix", str(frontend)], check=True)
    if served_dist is not None and served_dist.resolve() != dist.resolve():
        typer.echo(
            f"경고: 빌드는 {dist} 에 생성됐지만 서버는 NG_FRONTEND_DIST={served_dist} 를 서빙합니다."
        )


@app.command()
def serve(
    host: str | None = typer.Option(None, help="HTTP bind host (overrides settings)."),
    port: int | None = typer.Option(None, help="HTTP bind port (overrides settings)."),
    build_frontend: bool = typer.Option(
        False, "--build-frontend", help="Build the React console before serving."
    ),
) -> None:
    """Run the Negotium office console — UI and API on a single port."""
    _load_env_file()
    container = Container.build()
    settings = container.settings
    if build_frontend:
        _build_frontend(settings.frontend_dist)
    configure_logging(settings.log_level)
    uvicorn.run(
        "negotium.app.main:create_app",
        host=host or settings.http_host,
        port=port or settings.http_port,
        factory=True,
        log_level=settings.log_level.lower(),
    )


@app.command("llm-gateway")
def llm_gateway(
    host: str | None = typer.Option(None, help="HTTP bind host (overrides settings)."),
    port: int | None = typer.Option(None, help="HTTP bind port (overrides settings)."),
) -> None:
    """Run the standalone external LLM gateway."""
    from negotium.app.settings import load_settings

    _load_env_file()
    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "negotium.llm_gateway.app:create_app",
        host=host or settings.llm_gateway_host,
        port=port or settings.llm_gateway_port,
        factory=True,
        log_level=settings.log_level.lower(),
    )


@app.command("reset-state")
def reset_state(
    yes: bool = typer.Option(False, "--yes", help="Confirm destructive local state reset."),
    actor: str = typer.Option("cli", help="Actor name written to the audit log."),
    include_workspaces: bool = typer.Option(
        True,
        help="Also clear the configured workspace directory.",
    ),
) -> None:
    """Reset local memory, auth, secrets, documents, uploads, and workspaces."""
    from negotium.app.reset_state import reset_system_state
    from negotium.app.settings import load_settings

    if not yes:
        raise typer.BadParameter("reset-state is destructive; re-run with --yes to confirm")
    settings = load_settings()
    result = reset_system_state(
        archive_dir=settings.archive_dir,
        workspace_dir=settings.workspace_dir,
        actor=actor,
        include_workspaces=include_workspaces,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


skill_app = typer.Typer(no_args_is_help=True, help="List and run registered skills.")
app.add_typer(skill_app, name="skill")


@skill_app.command("list")
def skill_list() -> None:
    """List all registered skills."""
    from negotium.app.services.skill_registry import get_skills

    skills = get_skills()
    if not skills:
        typer.echo("등록된 스킬이 없습니다.")
        return
    for skill in skills.values():
        typer.echo(f"{skill.id}\t[{skill.executor}]\t{skill.name} — {skill.description}")


@skill_app.command("run")
def skill_run(
    skill_id: str = typer.Argument(..., help="Skill id to run."),
    inputs: list[str] = typer.Option([], "--input", "-i", help="Input as key=value (repeatable)."),
    actor: str = typer.Option("cli", help="Actor name for the audit log."),
) -> None:
    """Run a skill with key=value inputs."""
    import asyncio

    from negotium.app.api import _complete_office_task
    from negotium.app.services.skill_registry import get_skill
    from negotium.app.services.skill_runtime import SkillError, run_skill

    parsed: dict[str, str] = {}
    for raw in inputs:
        if "=" not in raw:
            raise typer.BadParameter(f"input must be key=value: {raw}")
        key, value = raw.split("=", 1)
        parsed[key.strip()] = value
    container = Container.build()
    skill = get_skill(skill_id)
    if skill is None:
        raise typer.BadParameter(f"unknown skill: {skill_id}")

    async def _completion(prompt: str, image_parts: list[dict[str, object]] | None) -> str:
        return await _complete_office_task(container, prompt, task=skill.task)

    async def _run() -> None:
        try:
            result = await run_skill(
                container, skill_id, dict(parsed), actor=actor, completion=_completion
            )
        except SkillError as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    asyncio.run(_run())


if __name__ == "__main__":
    app()
