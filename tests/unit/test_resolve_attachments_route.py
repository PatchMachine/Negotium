"""Route gating for office-document attachments: cloud parses, local never calls out."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from negotium.app.api import _shared
from negotium.app.container import Container
from negotium.app.settings import Settings

_DOCX_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>로컬 추출 본문</w:t></w:r></w:p></w:body></w:document>"
)


def _container(tmp_path: Path) -> Container:
    container = Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )
    container.settings.llm.solar_api_key = "up_test_key"
    return container


def _upload_docx(container: Container) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", _DOCX_XML)
    buffer.seek(0)
    record = container.uploads.save(filename="minutes.docx", source=buffer)
    return str(record.id)


async def test_local_route_never_calls_document_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)
    upload_id = _upload_docx(container)

    async def spy(*args: Any, **kwargs: Any) -> tuple[str | None, str]:
        raise AssertionError("Document Parse must not be called on the local route")

    monkeypatch.setattr(_shared, "parse_office_document", spy)

    for route in ("local", ""):
        context, _parts, _notes = await _shared._resolve_document_attachments(
            container, [upload_id], vision_enabled=False, route=route
        )
        assert "로컬 추출 본문" in context


async def test_cloud_route_uses_document_parse_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)
    upload_id = _upload_docx(container)
    calls: list[Path] = []

    async def fake_parse(path: Path, **kwargs: Any) -> tuple[str | None, str]:
        calls.append(path)
        return "# 클라우드 변환 마크다운", ""

    monkeypatch.setattr(_shared, "parse_office_document", fake_parse)

    context, _parts, notes = await _shared._resolve_document_attachments(
        container, [upload_id], vision_enabled=False, route="cloud"
    )

    assert len(calls) == 1
    assert "클라우드 변환 마크다운" in context
    assert any("Document Parse" in note for note in notes)


async def test_cloud_parse_failure_falls_back_to_local_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)
    upload_id = _upload_docx(container)

    async def failing_parse(path: Path, **kwargs: Any) -> tuple[str | None, str]:
        return None, "boom"

    monkeypatch.setattr(_shared, "parse_office_document", failing_parse)

    context, _parts, notes = await _shared._resolve_document_attachments(
        container, [upload_id], vision_enabled=False, route="cloud"
    )

    assert "로컬 추출 본문" in context, "local parser must still supply text"
    assert any("클라우드 문서 파싱 실패" in note and "boom" in note for note in notes)


async def test_cloud_route_without_api_key_stays_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)
    container.settings.llm.solar_api_key = ""
    upload_id = _upload_docx(container)

    async def spy(*args: Any, **kwargs: Any) -> tuple[str | None, str]:
        raise AssertionError("no API key means no Document Parse call")

    monkeypatch.setattr(_shared, "parse_office_document", spy)

    context, _parts, _notes = await _shared._resolve_document_attachments(
        container, [upload_id], vision_enabled=False, route="cloud"
    )
    assert "로컬 추출 본문" in context
