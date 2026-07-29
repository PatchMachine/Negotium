from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

from negotium.app.initial_setup import parse_setup_file


def test_parse_setup_csv_extracts_rows_and_sensitive_hint(tmp_path: Path) -> None:
    path = tmp_path / "인사_명단.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["이름", "직함", "부서"])
        writer.writeheader()
        writer.writerow({"이름": "김대표", "직함": "대표", "부서": "경영"})

    parsed = parse_setup_file(path, archive_root=tmp_path)
    assert parsed.kind == "csv"
    assert parsed.rows[0]["이름"] == "김대표"
    assert parsed.sensitive_hint is True


def test_parse_setup_xlsx_extracts_rows(tmp_path: Path) -> None:
    path = tmp_path / "employees.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["name", "title", "department"])
    ws.append(["Alice", "Manager", "Ops"])
    wb.save(path)

    parsed = parse_setup_file(path, archive_root=tmp_path)
    assert parsed.kind == "xlsx"
    assert parsed.rows[0]["name"] == "Alice"
    assert "Alice" in parsed.text


def test_parse_setup_docx_extracts_real_text(tmp_path: Path) -> None:
    import zipfile

    path = tmp_path / "조직도.docx"
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>영업팀과 개발팀 조직 구성</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    parsed = parse_setup_file(path, archive_root=tmp_path)
    assert parsed.kind == "docx"
    assert "영업팀과 개발팀" in parsed.text, "must be real text, not mojibake"


def test_parse_setup_broken_hwp_reports_failure_text(tmp_path: Path) -> None:
    path = tmp_path / "old.hwp"
    path.write_bytes(b"not ole")
    parsed = parse_setup_file(path, archive_root=tmp_path)
    assert parsed.kind == "hwp"
    assert "문서 파싱 실패" in parsed.text


def test_parse_setup_text_reads_content(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# 보안 정책\n고객 정보는 로컬에서만 처리", encoding="utf-8")
    parsed = parse_setup_file(path, archive_root=tmp_path)
    assert parsed.kind == "md"
    assert "보안 정책" in parsed.text
    assert parsed.sensitive_hint is True
