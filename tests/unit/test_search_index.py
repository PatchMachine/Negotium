"""Search index: Korean bigrams, chunking, BM25 relevance, incremental refresh."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from negotium.archive import search_index as search_index_module
from negotium.archive.search_index import (
    SearchIndexStore,
    chunk_text,
    make_snippet,
    rrf_merge,
    tokenize,
)


def _write_doc(archive: Path, rel: str, text: str, *, mtime: float | None = None) -> Path:
    path = archive / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_korean_bigrams_bridge_postpositions() -> None:
    query = set(tokenize("합의했지"))
    doc = set(tokenize("A업체와 합의 내용 정리"))
    assert query & doc, "bigram overlap must connect 합의했지 ↔ 합의"


def test_collapsed_variant_matches_separators() -> None:
    assert "patchops" in tokenize("patch_ops/2026/07")
    assert "patchops" in tokenize("patchops")


def test_chunking_sizes_and_overlap() -> None:
    text = "가" * 2500
    chunks = chunk_text(text, size=900, overlap=150)
    assert all(len(chunk) <= 900 for chunk in chunks)
    assert chunks[0][-150:] == chunks[1][:150], "consecutive chunks share the overlap"
    assert chunk_text("짧은 글") == ["짧은 글"]
    assert chunk_text("   ") == []


def test_snippet_centers_on_hit() -> None:
    chunk = ("앞부분 " * 100) + "핵심합의내용" + (" 뒷부분" * 100)
    snippet = make_snippet(chunk, tokenize("합의"), width=100)
    assert "합의" in snippet
    assert len(snippet) <= 100


def test_rrf_merge_rewards_agreement() -> None:
    fused = rrf_merge([["a", "b", "c"], ["b", "a"]])
    order = [key for key, _ in fused]
    assert set(order[:2]) == {"a", "b"}
    assert order[2] == "c"


def test_relevance_beats_recency_and_deep_keywords_are_found(tmp_path: Path) -> None:
    """A keyword at char ~5000 in an old file must outrank a fresh unrelated file."""
    archive = tmp_path / "archive"
    filler = "일반적인 회의 내용입니다. " * 400  # ~5200 chars
    old_time = time.time() - 86400
    _write_doc(
        archive,
        "documents/old_minutes.md",
        "# 4월 회의록\n" + filler + "\n청우식품과 단가 인하 합의 완료",
        mtime=old_time,
    )
    _write_doc(archive, "documents/new_unrelated.md", "# 신규 문서\n다른 주제의 메모입니다.")

    store = SearchIndexStore(archive)
    hits = store.search("청우식품 합의")

    assert hits, "keyword buried past 600 chars must be found"
    assert hits[0].path == "documents/old_minutes.md"
    assert "합의" in hits[0].snippet


def test_incremental_refresh_reindexes_only_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "archive"
    _write_doc(archive, "documents/a.md", "# A\n프로젝트 알파 내용")
    b_path = _write_doc(archive, "documents/b.md", "# B\n프로젝트 베타 내용")

    store = SearchIndexStore(archive)
    first = store.refresh()
    assert first["indexed"] == 2

    reads: list[str] = []
    original = search_index_module.read_full_text

    def counting_read(path: Path, **kwargs: object) -> str:
        reads.append(path.name)
        return original(path)  # type: ignore[arg-type]

    monkeypatch.setattr(search_index_module, "read_full_text", counting_read)

    second = store.refresh()
    assert second == {"indexed": 0, "removed": 0, "unchanged": 2}
    assert reads == [], "unchanged files must not be re-read"

    b_path.write_text("# B\n프로젝트 감마로 변경", encoding="utf-8")
    os.utime(b_path, (time.time() + 5, time.time() + 5))
    third = store.refresh()
    assert third["indexed"] == 1
    assert reads == ["b.md"]
    assert store.search("감마")[0].path == "documents/b.md"
    assert not store.search("베타"), "old content must leave the index"


def test_deleted_and_tombstoned_files_leave_the_index(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    a_path = _write_doc(archive, "documents/a.md", "# A\n삭제될 문서")
    _write_doc(archive, "documents/b.md", "# B\n툼스톤 문서")

    store = SearchIndexStore(archive)
    assert store.search("문서")

    a_path.unlink()
    tombstones = archive / "memory" / "tombstones.jsonl"
    tombstones.parent.mkdir(parents=True, exist_ok=True)
    tombstones.write_text(json.dumps({"target_id": "documents/b.md"}) + "\n", encoding="utf-8")

    assert store.search("문서") == []
    assert store.stats()["files"] == 0


def test_vector_ranking_fuses_with_keywords(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    _write_doc(archive, "documents/a.md", "# A\n계약 조건 문서")
    _write_doc(archive, "documents/b.md", "# B\n합의 내용 문서")

    store = SearchIndexStore(archive)
    store.refresh()
    # Fake normalized vectors: b's chunk aligns with the fake query vector.
    store.store_embeddings("documents/a.md", {0: [1.0, 0.0]})
    store.store_embeddings("documents/b.md", {0: [0.0, 1.0]})
    store.set_query_embedder(lambda query: [0.0, 1.0])

    hits = store.search("문서")
    assert hits[0].path == "documents/b.md", "vector agreement must lift b via RRF"

    store.set_query_embedder(lambda query: None)
    assert store.search("계약"), "embedder returning None must fall back to keywords"


def test_stats_reports_embedding_progress(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    _write_doc(archive, "documents/a.md", "# A\n본문")
    store = SearchIndexStore(archive)
    store.refresh()
    store.store_embeddings("documents/a.md", {0: None})
    store.mark_embed_run("2026-07-29T00:00:00+00:00")

    stats = store.stats()
    assert stats["files"] == 1
    assert stats["embed_skipped"] == 1
    assert stats["last_embed_run"] == "2026-07-29T00:00:00+00:00"
