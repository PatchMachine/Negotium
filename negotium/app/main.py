"""FastAPI entry point for the Negotium office console."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from negotium.app.api import create_operations_api_router
from negotium.app.container import Container
from negotium.app.contributor_site import create_contributor_site_router
from negotium.observability import get_logger


def create_app(container: Container | None = None) -> FastAPI:
    container = container or Container.build()
    log = get_logger(component="app")
    llm_preload_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal llm_preload_task
        log.info("app.startup")
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
            if llm_preload_task is not None:
                llm_preload_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await llm_preload_task

    app = FastAPI(title="Negotium", version="0.1.0", lifespan=lifespan)
    app.include_router(create_operations_api_router(container))
    app.include_router(create_contributor_site_router(container.operations_memory))

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "metrics": container.metrics.snapshot(),
        }

    return app


app = create_app
