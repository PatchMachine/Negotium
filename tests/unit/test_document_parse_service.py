"""Upstage Document Parse client: success, cache, and failure contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from negotium.app.services.document_parse_service import (
    DOCUMENT_PARSE_MAX_BYTES,
    cached_parse_path,
    digitization_url,
    parse_document_via_api,
    parse_office_document,
)

_BASE_URL = "https://api.upstage.ai/v1"


class FakeClient:
    """Stands in for httpx.AsyncClient; counts POSTs and returns a canned response."""

    post_calls = 0
    response_factory: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        type(self).post_calls += 1
        factory = type(self).response_factory
        assert factory is not None
        result = factory(url, kwargs)
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, httpx.Response)
        return result


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.post_calls = 0
    FakeClient.response_factory = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)


def _ok_response(markdown: str = "# 변환 결과") -> httpx.Response:
    return httpx.Response(
        200,
        json={"content": {"markdown": markdown}},
        request=httpx.Request("POST", digitization_url(_BASE_URL)),
    )


def test_digitization_url_strips_trailing_slash() -> None:
    assert digitization_url("https://api.upstage.ai/v1/") == (
        "https://api.upstage.ai/v1/document-digitization"
    )


async def test_parse_success_sends_expected_form(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def factory(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        seen["url"] = url
        seen["data"] = kwargs["data"]
        seen["headers"] = kwargs["headers"]
        return _ok_response()

    FakeClient.response_factory = staticmethod(factory)
    file = tmp_path / "doc.docx"
    file.write_bytes(b"fake docx bytes")

    markdown, reason = await parse_document_via_api(file, api_key="up_test", base_url=_BASE_URL)

    assert markdown == "# 변환 결과"
    assert reason == ""
    assert seen["url"] == "https://api.upstage.ai/v1/document-digitization"
    assert seen["data"]["model"] == "document-parse"
    assert seen["data"]["output_formats"] == '["markdown"]'
    assert seen["headers"]["Authorization"] == "Bearer up_test"


async def test_parse_office_document_caches_result(tmp_path: Path) -> None:
    FakeClient.response_factory = staticmethod(lambda url, kwargs: _ok_response("# 캐시 본문"))
    file = tmp_path / "doc.hwp"
    file.write_bytes(b"fake hwp bytes")

    first, _ = await parse_office_document(file, api_key="k", base_url=_BASE_URL)
    second, _ = await parse_office_document(file, api_key="k", base_url=_BASE_URL)

    assert first == "# 캐시 본문"
    assert second == "# 캐시 본문"
    assert FakeClient.post_calls == 1, "cache hit must not re-bill"
    assert cached_parse_path(file).read_text(encoding="utf-8") == "# 캐시 본문"


async def test_server_error_returns_reason(tmp_path: Path) -> None:
    FakeClient.response_factory = staticmethod(
        lambda url, kwargs: httpx.Response(
            500, request=httpx.Request("POST", digitization_url(_BASE_URL))
        )
    )
    file = tmp_path / "doc.docx"
    file.write_bytes(b"x")

    markdown, reason = await parse_document_via_api(file, api_key="k", base_url=_BASE_URL)
    assert markdown is None
    assert "500" in reason


async def test_connect_error_returns_reason(tmp_path: Path) -> None:
    FakeClient.response_factory = staticmethod(
        lambda url, kwargs: httpx.ConnectError("connection refused")
    )
    file = tmp_path / "doc.docx"
    file.write_bytes(b"x")

    markdown, reason = await parse_document_via_api(file, api_key="k", base_url=_BASE_URL)
    assert markdown is None
    assert "호출 실패" in reason


async def test_missing_markdown_in_response(tmp_path: Path) -> None:
    FakeClient.response_factory = staticmethod(
        lambda url, kwargs: httpx.Response(
            200, json={"content": {}}, request=httpx.Request("POST", digitization_url(_BASE_URL))
        )
    )
    file = tmp_path / "doc.docx"
    file.write_bytes(b"x")

    markdown, reason = await parse_document_via_api(file, api_key="k", base_url=_BASE_URL)
    assert markdown is None
    assert "markdown" in reason


async def test_oversized_file_is_rejected_before_any_post(tmp_path: Path) -> None:
    file = tmp_path / "big.docx"
    with file.open("wb") as handle:
        handle.seek(DOCUMENT_PARSE_MAX_BYTES)
        handle.write(b"\0")

    markdown, reason = await parse_document_via_api(file, api_key="k", base_url=_BASE_URL)
    assert markdown is None
    assert "50MB" in reason
    assert FakeClient.post_calls == 0
