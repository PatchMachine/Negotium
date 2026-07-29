"""Local text extraction for office documents.

* ``.docx`` and ``.hwpx`` are zip+XML containers and are parsed with the
  standard library only.
* Binary ``.hwp`` (HWP v5) is an OLE compound file; ``olefile`` reads the
  streams and the record/text decoding is implemented here.

The module is deliberately free of imports from other app modules so both
``attachment_service`` and ``initial_setup`` can use it without cycles.
Failures raise :class:`OfficeDocParseError` with a user-facing Korean message;
callers convert that into an attachment ``note``.
"""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

OFFICE_DOC_SUFFIXES = {".docx", ".hwp", ".hwpx"}

_DOC_CHAR_CAP = 20000
# Zip-bomb guard: refuse to inflate any single XML member beyond this.
_MAX_XML_MEMBER_BYTES = 20 * 1024 * 1024

_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HWPX_NS = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

_HWP_SIGNATURE = b"HWP Document File"
_HWPTAG_PARA_TEXT = 67


class OfficeDocParseError(Exception):
    """A local office-document parse failed; the message is user-facing."""


def extract_office_doc_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".hwpx":
        return extract_hwpx_text(path)
    if suffix == ".hwp":
        return extract_hwp_text(path)
    raise OfficeDocParseError(f"지원하지 않는 문서 형식입니다: {suffix or 'unknown'}")


def extract_docx_text(path: Path) -> str:
    root = _parse_zip_xml_member(path, "word/document.xml")
    paragraphs: list[str] = []
    total = 0
    for paragraph in root.iter(f"{_DOCX_NS}p"):
        pieces: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_DOCX_NS}t":
                pieces.append(node.text or "")
            elif node.tag == f"{_DOCX_NS}tab":
                pieces.append("\t")
            elif node.tag == f"{_DOCX_NS}br":
                pieces.append("\n")
        text = "".join(pieces)
        paragraphs.append(text)
        total += len(text) + 1
        if total >= _DOC_CHAR_CAP:
            break
    return "\n".join(paragraphs).strip()[:_DOC_CHAR_CAP]


def extract_hwpx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            members = sorted(
                (name for name in archive.namelist() if _is_hwpx_section(name)),
                key=_section_sort_key,
            )
            if not members:
                raise OfficeDocParseError("HWPX 본문(Contents/section*.xml)을 찾지 못했습니다.")
            paragraphs: list[str] = []
            total = 0
            for member in members:
                root = _parse_member(archive, member)
                for paragraph in root.iter(f"{_HWPX_NS}p"):
                    pieces = ["".join(node.itertext()) for node in paragraph.iter(f"{_HWPX_NS}t")]
                    text = "".join(pieces)
                    paragraphs.append(text)
                    total += len(text) + 1
                    if total >= _DOC_CHAR_CAP:
                        return "\n".join(paragraphs).strip()[:_DOC_CHAR_CAP]
            return "\n".join(paragraphs).strip()[:_DOC_CHAR_CAP]
    except zipfile.BadZipFile as exc:
        raise OfficeDocParseError(f"HWPX 파일을 열지 못했습니다: {exc}") from exc


def extract_hwp_text(path: Path) -> str:
    import olefile

    try:
        ole = olefile.OleFileIO(str(path))
    except OSError as exc:
        raise OfficeDocParseError(f"HWP 파일을 열지 못했습니다: {exc}") from exc
    try:
        if not ole.exists("FileHeader"):
            raise OfficeDocParseError("HWP FileHeader가 없습니다. 올바른 HWP 파일이 아닙니다.")
        header = ole.openstream("FileHeader").read()
        if not header.startswith(_HWP_SIGNATURE):
            raise OfficeDocParseError("HWP 시그니처가 일치하지 않습니다.")
        if len(header) < 40:
            raise OfficeDocParseError("HWP FileHeader가 손상되었습니다.")
        attributes = struct.unpack_from("<I", header, 36)[0]
        compressed = bool(attributes & 0x1)
        if attributes & 0x2:
            raise OfficeDocParseError("암호화된 HWP는 지원하지 않습니다.")

        sections = sorted(
            (
                entry
                for entry in ole.listdir()
                if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section")
            ),
            key=lambda entry: _section_sort_key(entry[1]),
        )
        if not sections:
            # Distribution/preview documents keep the body in ViewText instead.
            raise OfficeDocParseError(
                "HWP 본문(BodyText)을 찾지 못했습니다. 배포용 문서는 지원하지 않습니다."
            )

        texts: list[str] = []
        total = 0
        for entry in sections:
            data = ole.openstream("/".join(entry)).read()
            if compressed:
                try:
                    data = zlib.decompress(data, -15)
                except zlib.error as exc:
                    raise OfficeDocParseError(f"HWP 본문 압축 해제 실패: {exc}") from exc
            text = _extract_hwp_section_text(data)
            texts.append(text)
            total += len(text) + 1
            if total >= _DOC_CHAR_CAP:
                break
        return "\n".join(texts).strip()[:_DOC_CHAR_CAP]
    finally:
        ole.close()


def _iter_hwp_records(stream: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield ``(tag_id, payload)`` records; a truncated stream ends quietly."""
    offset = 0
    length = len(stream)
    while offset + 4 <= length:
        header = struct.unpack_from("<I", stream, offset)[0]
        offset += 4
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > length:
                return
            size = struct.unpack_from("<I", stream, offset)[0]
            offset += 4
        if offset + size > length:
            return
        yield tag, stream[offset : offset + size]
        offset += size


def _decode_hwp_para_text(payload: bytes) -> str:
    """Decode a HWPTAG_PARA_TEXT payload (UTF-16LE with inline control codes)."""
    units = len(payload) // 2
    pieces: list[str] = []
    index = 0
    while index < units:
        code = struct.unpack_from("<H", payload, index * 2)[0]
        if code in (10, 13):
            pieces.append("\n")
            index += 1
        elif code in (30, 31):
            pieces.append(" ")
            index += 1
        elif code == 9:
            pieces.append("\t")
            index += 8  # tab is an 8-unit inline control
        elif code in (0, 24, 25, 26, 27, 28, 29):
            index += 1
        elif code < 32:
            index += 8  # other inline/extended controls occupy 8 units
        else:
            pieces.append(chr(code))
            index += 1
    return "".join(pieces)


def _extract_hwp_section_text(section: bytes) -> str:
    paragraphs = [
        _decode_hwp_para_text(payload)
        for tag, payload in _iter_hwp_records(section)
        if tag == _HWPTAG_PARA_TEXT
    ]
    return "\n".join(item for item in paragraphs if item.strip())


def _is_hwpx_section(name: str) -> bool:
    return bool(re.fullmatch(r"Contents/section\d+\.xml", name))


def _section_sort_key(name: str) -> int:
    match = re.search(r"(\d+)", name)
    return int(match.group(1)) if match else 0


def _parse_zip_xml_member(path: Path, member: str) -> ET.Element:
    try:
        with zipfile.ZipFile(path) as archive:
            return _parse_member(archive, member)
    except zipfile.BadZipFile as exc:
        raise OfficeDocParseError(f"문서 파일을 열지 못했습니다: {exc}") from exc


def _parse_member(archive: zipfile.ZipFile, member: str) -> ET.Element:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise OfficeDocParseError(f"문서 본문({member})을 찾지 못했습니다.") from exc
    if info.file_size > _MAX_XML_MEMBER_BYTES:
        raise OfficeDocParseError("문서 본문이 너무 큽니다.")
    try:
        return ET.fromstring(archive.read(member))
    except ET.ParseError as exc:
        raise OfficeDocParseError(f"문서 XML 파싱 실패: {exc}") from exc


__all__ = [
    "OFFICE_DOC_SUFFIXES",
    "OfficeDocParseError",
    "extract_docx_text",
    "extract_hwp_text",
    "extract_hwpx_text",
    "extract_office_doc_text",
]
