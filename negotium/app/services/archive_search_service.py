"""Upstage embeddings for the archive search index, firewall-gated.

Every chunk passes the context firewall before leaving the machine; blocked or
local-only chunks are recorded as skipped and never sent (an improvement over
the Document Parse precedent, which posts raw bytes). Embedding is opt-in via
the automation config and runs on the automation scheduler.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx
import structlog

from negotium.app.services.context_firewall_service import (
    ContextFirewallResult,
    load_context_firewall_policy,
    record_firewall_audit,
    sanitize_context,
)

if TYPE_CHECKING:
    from negotium.app.container import Container

_log = structlog.get_logger(component="archive_search")

PASSAGE_MODEL = "embedding-passage"
QUERY_MODEL = "embedding-query"
EMBED_BATCH = 100
_EMBED_TIMEOUT_SECONDS = 30.0
_QUERY_TIMEOUT_SECONDS = 4.0
_QUERY_CACHE_SIZE = 32
_CIRCUIT_BREAK_SECONDS = 60.0

_ALLOWED_DECISIONS = {"allow", "allow_redacted"}


def embeddings_url(solar_base_url: str) -> str:
    """``https://api.upstage.ai/v1`` → ``https://api.upstage.ai/v1/embeddings``."""
    return solar_base_url.rstrip("/") + "/embeddings"


def _solar_key(container: Container) -> str:
    saved = container.secret_store.read("solar")
    return (saved.api_key if saved else "") or container.settings.llm.solar_api_key


async def embed_texts(
    texts: list[str],
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = _EMBED_TIMEOUT_SECONDS,
) -> list[list[float]]:
    """Order-preserving embeddings for up to ``EMBED_BATCH`` texts. Raises on failure."""
    if not texts:
        return []
    if len(texts) > EMBED_BATCH:
        raise ValueError(f"batch too large: {len(texts)} > {EMBED_BATCH}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            embeddings_url(base_url),
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": texts},
        )
    response.raise_for_status()
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or len(data) != len(texts):
        raise ValueError("unexpected embeddings response shape")
    ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
    return [[float(v) for v in item["embedding"]] for item in ordered]


async def refresh_embeddings(container: Container, *, max_chunks: int = 500) -> dict[str, object]:
    """Refresh the index and embed pending chunks that clear the firewall."""
    store = container.search_index
    refreshed = store.refresh()
    api_key = _solar_key(container)
    if not api_key:
        return {"refresh": refreshed, "embedded": 0, "skipped": 0, "reason": "no api key"}

    pending = store.chunks_needing_embedding(limit=max_chunks)
    if not pending:
        return {"refresh": refreshed, "embedded": 0, "skipped": 0}

    policy = load_context_firewall_policy(container.settings.workspace_dir)
    sendable: list[tuple[str, int, str]] = []
    skipped_by_file: dict[str, int] = {}
    blocked_results: dict[str, ContextFirewallResult] = {}
    per_file: dict[str, dict[int, list[float] | None]] = {}
    for path, index, text in pending:
        result = sanitize_context(
            text,
            destination="frontier_llm",
            task_type="embedding_index",
            source_uri=path,
            policy=policy,
        )
        if result.decision in _ALLOWED_DECISIONS:
            sanitized = result.sanitized if isinstance(result.sanitized, str) else text
            sendable.append((path, index, sanitized))
        else:
            per_file.setdefault(path, {})[index] = None
            skipped_by_file[path] = skipped_by_file.get(path, 0) + 1
            blocked_results[path] = result

    embedded = 0
    try:
        for start in range(0, len(sendable), EMBED_BATCH):
            batch = sendable[start : start + EMBED_BATCH]
            vectors = await embed_texts(
                [text for _, _, text in batch],
                api_key=api_key,
                base_url=container.settings.llm.solar_base_url,
                model=PASSAGE_MODEL,
            )
            for (path, index, _text), vector in zip(batch, vectors, strict=True):
                per_file.setdefault(path, {})[index] = [round(v, 6) for v in vector]
                embedded += 1
    except (httpx.HTTPError, ValueError) as exc:
        # Persist what we have; the rest is retried on the next slot.
        _log.warning("archive_search.embed_failed", error=str(exc))

    for path, vectors_by_index in per_file.items():
        store.store_embeddings(path, vectors_by_index)

    for path in skipped_by_file:
        # One audit record per file with skipped chunks — bounded log volume.
        blocked = blocked_results.get(path)
        if blocked is not None:
            record_firewall_audit(
                container,
                blocked,
                actor="automation",
                destination="frontier_llm",
                task_type="embedding_index",
            )

    return {
        "refresh": refreshed,
        "embedded": embedded,
        "skipped": sum(skipped_by_file.values()),
    }


def make_query_embedder(container: Container) -> Callable[[str], list[float] | None]:
    """Sync query embedder with a small cache and a failure circuit breaker."""
    cache: OrderedDict[str, list[float]] = OrderedDict()
    broken_until = 0.0

    def embed(query: str) -> list[float] | None:
        nonlocal broken_until
        if not container.automation.read_config().search.embeddings_enabled:
            return None
        api_key = _solar_key(container)
        if not api_key or time.monotonic() < broken_until:
            return None
        key = query.strip()
        if not key:
            return None
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        try:
            with httpx.Client(timeout=_QUERY_TIMEOUT_SECONDS) as client:
                response = client.post(
                    embeddings_url(container.settings.llm.solar_base_url),
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": QUERY_MODEL, "input": key},
                )
            response.raise_for_status()
            data = response.json()["data"][0]["embedding"]
            vector = [float(v) for v in data]
        except Exception:
            broken_until = time.monotonic() + _CIRCUIT_BREAK_SECONDS
            return None
        cache[key] = vector
        if len(cache) > _QUERY_CACHE_SIZE:
            cache.popitem(last=False)
        return vector

    return embed


__all__ = [
    "EMBED_BATCH",
    "PASSAGE_MODEL",
    "QUERY_MODEL",
    "embed_texts",
    "embeddings_url",
    "make_query_embedder",
    "refresh_embeddings",
]
