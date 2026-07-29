"""Embedding service: request shape, firewall gating, failure fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest

from negotium.app.container import Container
from negotium.app.services.archive_search_service import (
    EMBED_BATCH,
    embed_texts,
    embeddings_url,
    make_query_embedder,
    refresh_embeddings,
)
from negotium.app.settings import Settings
from negotium.archive.automation import AutomationConfig, SearchConfig

_BASE = "https://api.upstage.ai/v1"


class FakeAsyncClient:
    requests: ClassVar[list[dict[str, Any]]] = []
    fail: ClassVar[Exception | None] = None
    dim: ClassVar[int] = 8

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        if type(self).fail is not None:
            raise type(self).fail
        payload = kwargs["json"]
        type(self).requests.append({"url": url, "json": payload})
        inputs = payload["input"] if isinstance(payload["input"], list) else [payload["input"]]
        data = [
            {"index": i, "embedding": [0.1] * type(self).dim, "object": "embedding"}
            for i in range(len(inputs))
        ]
        return httpx.Response(
            200,
            json={"object": "list", "data": data, "model": payload["model"]},
            request=httpx.Request("POST", url),
        )


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch: pytest.MonkeyPatch) -> type[FakeAsyncClient]:
    FakeAsyncClient.requests = []
    FakeAsyncClient.fail = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


def _container(tmp_path: Path, *, embeddings_enabled: bool = True) -> Container:
    container = Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )
    container.settings.llm.solar_api_key = "up_test"
    container.automation.write_config(
        AutomationConfig(search=SearchConfig(embeddings_enabled=embeddings_enabled))
    )
    return container


def _write_doc(container: Container, rel: str, text: str) -> None:
    path = container.settings.archive_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_embeddings_url() -> None:
    assert embeddings_url(_BASE + "/") == "https://api.upstage.ai/v1/embeddings"


async def test_embed_texts_request_shape() -> None:
    vectors = await embed_texts(
        ["가", "나"], api_key="k", base_url=_BASE, model="embedding-passage"
    )
    assert len(vectors) == 2
    assert FakeAsyncClient.requests[0]["json"] == {
        "model": "embedding-passage",
        "input": ["가", "나"],
    }


async def test_embed_texts_rejects_oversized_batch() -> None:
    with pytest.raises(ValueError):
        await embed_texts(
            ["x"] * (EMBED_BATCH + 1), api_key="k", base_url=_BASE, model="embedding-passage"
        )


async def test_refresh_embeddings_sends_clean_chunks(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _write_doc(container, "documents/plan.md", "# 계획\n분기 목표와 일정 정리")

    result = await refresh_embeddings(container)

    assert result["embedded"] == 1
    assert result["skipped"] == 0
    stats = container.search_index.stats()
    assert stats["embedded"] == 1


async def test_sensitive_chunk_never_leaves_the_machine(tmp_path: Path) -> None:
    """A chunk with a resident registration number must not appear in any POST."""
    container = _container(tmp_path)
    _write_doc(
        container,
        "documents/hr_note.md",
        "# 인사 메모\n담당자 주민등록번호 900101-1234567 기록",
    )
    _write_doc(container, "documents/plan.md", "# 계획\n일반 업무 내용")

    result = await refresh_embeddings(container)

    sent = json.dumps([req["json"] for req in FakeAsyncClient.requests], ensure_ascii=False)
    assert "900101-1234567" not in sent, "RRN must never reach the embeddings API"
    assert result["skipped"] >= 1
    audit = container.context_firewall.list(limit=10)
    assert audit, "a firewall audit record must exist for the skipped file"


async def test_http_failure_persists_nothing_and_retries_later(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _write_doc(container, "documents/plan.md", "# 계획\n내용")
    FakeAsyncClient.fail = httpx.ConnectError("down")

    result = await refresh_embeddings(container)
    assert result["embedded"] == 0

    FakeAsyncClient.fail = None
    retried = await refresh_embeddings(container)
    assert retried["embedded"] == 1


def test_query_embedder_disabled_or_failing_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path, embeddings_enabled=False)
    embedder = make_query_embedder(container)
    assert embedder("검색어") is None, "disabled toggle short-circuits"

    container.automation.write_config(
        AutomationConfig(search=SearchConfig(embeddings_enabled=True))
    )

    class FailingClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> FailingClient:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", FailingClient)
    assert embedder("검색어") is None, "HTTP failure degrades to keyword-only"
