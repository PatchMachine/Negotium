"""Local office-document parsers: docx/hwpx zip+XML and binary HWP records."""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from negotium.app.services.office_doc_parser import (
    OfficeDocParseError,
    _decode_hwp_para_text,
    _extract_hwp_section_text,
    _iter_hwp_records,
    extract_docx_text,
    extract_hwpx_text,
    extract_office_doc_text,
)

_DOCX_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>회의록 첫 문단</w:t></w:r><w:r><w:tab/><w:t>탭 뒤 텍스트</w:t></w:r></w:p>
    <w:p><w:r><w:t>두 번째 문단</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

_HWPX_SECTION = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>{first}</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>{second}</hp:t></hp:run></hp:p>
</hs:sec>
"""


def _write_docx(path: Path, xml: str = _DOCX_XML) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return path


def _write_hwpx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Contents/section0.xml", _HWPX_SECTION.format(first="섹션0 문단", second="둘째 줄")
        )
        archive.writestr(
            "Contents/section1.xml", _HWPX_SECTION.format(first="섹션1 문단", second="마지막")
        )
    return path


def _hwp_record(tag: int, payload: bytes) -> bytes:
    return struct.pack("<I", (len(payload) << 20) | tag) + payload


def _para_text_payload(text: str) -> bytes:
    return text.encode("utf-16-le")


def test_docx_extracts_paragraphs_and_tabs(tmp_path: Path) -> None:
    path = _write_docx(tmp_path / "minutes.docx")
    text = extract_docx_text(path)
    assert "회의록 첫 문단\t탭 뒤 텍스트" in text
    assert text.index("첫 문단") < text.index("두 번째 문단")


def test_hwpx_extracts_sections_in_order(tmp_path: Path) -> None:
    path = _write_hwpx(tmp_path / "doc.hwpx")
    text = extract_hwpx_text(path)
    assert "섹션0 문단" in text
    assert text.index("섹션0 문단") < text.index("섹션1 문단")


def test_hwpx_without_sections_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.hwpx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
    with pytest.raises(OfficeDocParseError):
        extract_hwpx_text(path)


def test_docx_missing_body_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("other.xml", "<x/>")
    with pytest.raises(OfficeDocParseError):
        extract_docx_text(path)


def test_garbage_hwp_raises(tmp_path: Path) -> None:
    path = tmp_path / "garbage.hwp"
    path.write_bytes(b"this is not an ole file at all")
    with pytest.raises(OfficeDocParseError):
        extract_office_doc_text(path)


def test_iter_hwp_records_parses_standard_and_extended_headers() -> None:
    small = _hwp_record(67, _para_text_payload("가나다"))
    big_payload = _para_text_payload("라" * 10)
    # Extended-size header: size field 0xFFF, real size in the next DWORD.
    extended = (
        struct.pack("<I", (0xFFF << 20) | 67) + struct.pack("<I", len(big_payload)) + big_payload
    )
    records = list(_iter_hwp_records(small + extended))
    assert [tag for tag, _ in records] == [67, 67]
    assert records[1][1] == big_payload


def test_iter_hwp_records_tolerates_truncated_stream() -> None:
    record = _hwp_record(67, _para_text_payload("가"))
    truncated = record[:-1]
    assert list(_iter_hwp_records(truncated)) == []


def test_decode_hwp_para_text_handles_control_units() -> None:
    # "안녕" + newline(13) + tab control (unit 9 + 7 filler units) + "끝"
    units = [ord("안"), ord("녕"), 13, 9, 0, 0, 0, 0, 0, 0, 0, ord("끝")]
    payload = b"".join(struct.pack("<H", unit) for unit in units)
    assert _decode_hwp_para_text(payload) == "안녕\n\t끝"

    # Inline control (code 4) consumes 8 units total.
    units = [4, 1, 2, 3, 4, 5, 6, 7, ord("본"), ord("문")]
    payload = b"".join(struct.pack("<H", unit) for unit in units)
    assert _decode_hwp_para_text(payload) == "본문"


def test_extract_hwp_section_text_filters_non_text_records() -> None:
    section = (
        _hwp_record(66, b"\x00\x01")  # non-text record is ignored
        + _hwp_record(67, _para_text_payload("첫 문단"))
        + _hwp_record(67, _para_text_payload("둘째 문단"))
    )
    assert _extract_hwp_section_text(section) == "첫 문단\n둘째 문단"


def test_extract_hwp_section_text_survives_raw_deflate_roundtrip() -> None:
    """The zlib(-15) branch used for compressed BodyText sections."""
    section = _hwp_record(67, _para_text_payload("압축 본문"))
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(section) + compressor.flush()
    restored = zlib.decompress(compressed, -15)
    assert _extract_hwp_section_text(restored) == "압축 본문"


def test_unknown_suffix_raises(tmp_path: Path) -> None:
    path = tmp_path / "file.odt"
    path.write_bytes(b"")
    with pytest.raises(OfficeDocParseError):
        extract_office_doc_text(path)
