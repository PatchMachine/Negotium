"""FastAPI entry point for the Negotium office console."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from negotium.app.api import create_operations_api_router
from negotium.app.console_site import install_console
from negotium.app.container import Container
from negotium.app.contributor_site import create_contributor_site_router
from negotium.app.services.archive_search_service import make_query_embedder
from negotium.app.services.automation_service import run_due_jobs
from negotium.observability import get_logger

_AUTOMATION_TICK_SECONDS = 60


async def _automation_loop(container: Container) -> None:
    """Minute tick for scheduled automation. Sleep-first: a short-lived app
    (e.g. TestClient lifespans) never executes a tick."""
    log = get_logger(component="automation")
    while True:
        await asyncio.sleep(_AUTOMATION_TICK_SECONDS)
        try:
            executed = await run_due_jobs(container)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("automation.tick_failed")
            continue
        if executed:
            log.info("automation.jobs_executed", jobs=executed)


def create_app(container: Container | None = None) -> FastAPI:
    container = container or Container.build()
    # Semantic search stays off until the admin enables it; the embedder
    # checks the toggle on every call, so wiring it unconditionally is safe.
    container.search_index.set_query_embedder(make_query_embedder(container))
    log = get_logger(component="app")
    llm_preload_task: asyncio.Task[None] | None = None
    automation_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal llm_preload_task, automation_task
        log.info("app.startup")
        if container.settings.env != "test" and container.settings.automation_enabled:
            automation_task = asyncio.create_task(
                _automation_loop(container), name="automation-scheduler"
            )
        runtime = container.llm_runtime.read()
        embedded_vllm = container.embedded_vllm()
        if (
            container.settings.env != "test"
            and container.settings.llm.vllm_preload_on_startup
            and runtime.local_enabled
            and (
                container.settings.llm.provider == "vllm"
                or container.settings.llm.default_route == "local"
            )
            and embedded_vllm is not None
        ):
            llm_preload_task = asyncio.create_task(embedded_vllm.preload(), name="vllm-preload")
        try:
            yield
        finally:
            log.info("app.shutdown")
            for task in (llm_preload_task, automation_task):
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    app = FastAPI(title="Negotium", version="0.1.0", lifespan=lifespan)
    app.include_router(create_operations_api_router(container))
    app.include_router(create_contributor_site_router(container.operations_memory))

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "metrics": container.metrics.snapshot(),
        }

    # Assets mount + SPA fallback on unmatched-GET 404s; routing semantics
    # (405s, slash redirects, endpoint-raised 404 bodies) stay untouched.
    install_console(app, container.settings.frontend_dist)

    return app


app = create_app
