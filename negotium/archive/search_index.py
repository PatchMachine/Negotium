"""Chunk-level keyword search over the archive corpus, with optional vectors.

Pure stdlib. The index lives under ``archive/search_index/`` as a derived,
rebuildable cache (manifest + per-source chunk files + optional embedding
files). Korean queries work without a morphological analyzer because CJK text
is tokenized into character bigrams, so "합의했지" shares terms with "합의".

The store never performs HTTP itself: the app layer supplies a query-embedder
callback and writes passage vectors through :meth:`SearchIndexStore.store_embeddings`.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from negotium.archive._corpus import (
    is_operational_internal_file,
    kind_for,
    read_full_text,
    title_for,
    tombstoned_source_ids,
)
from negotium.archive._store import read_json_file, write_json_file

INDEX_VERSION = 1
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
SNIPPET_WIDTH = 300
_BM25_K1 = 1.5
_BM25_B = 0.75
_RRF_K = 60

_WORD_RE = re.compile(r"[A-Za-z0-9_\-]+")


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0xAC00 <= code <= 0xD7A3  # Hangul syllables
        or 0x1100 <= code <= 0x11FF  # Hangul jamo
        or 0x3130 <= code <= 0x318F  # Hangul compatibility jamo
        or 0x4E00 <= code <= 0x9FFF  # CJK unified ideographs
        or 0x3040 <= code <= 0x30FF  # kana
    )


def tokenize(text: str) -> list[str]:
    """Lowercased terms: latin/digit words (+ separator-collapsed variant) and CJK bigrams."""
    tokens: list[str] = []
    for raw in text.lower().split():
        run = ""
        for char in raw:
            if _is_cjk(char):
                run += char
                continue
            if run:
                tokens.extend(_cjk_grams(run))
                run = ""
        if run:
            tokens.extend(_cjk_grams(run))
        for match in _WORD_RE.findall(raw):
            tokens.append(match)
            collapsed = match.replace("_", "").replace("-", "")
            if collapsed and collapsed != match:
                tokens.append(collapsed)
    return tokens


def _cjk_grams(run: str) -> list[str]:
    if len(run) == 1:
        return [run]
    return [run[index : index + 2] for index in range(len(run) - 1)]


def chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    step = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(cleaned), step):
        piece = cleaned[start : start + size]
        if piece:
            chunks.append(piece)
        if start + size >= len(cleaned):
            break
    return chunks


def make_snippet(chunk: str, query_tokens: list[str], *, width: int = SNIPPET_WIDTH) -> str:
    flattened = " ".join(chunk.split())
    lowered = flattened.lower()
    position = -1
    for token in sorted(set(query_tokens), key=len, reverse=True):
        position = lowered.find(token)
        if position >= 0:
            break
    if position < 0:
        return flattened[:width]
    start = max(0, position - width // 2)
    return flattened[start : start + width]


def rrf_merge(rankings: Sequence[Sequence[str]], *, k: int = _RRF_K) -> list[tuple[str, float]]:
    """Reciprocal-rank fusion of path rankings → (path, fused_score) best-first."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


@dataclass(frozen=True)
class SearchHit:
    path: str
    kind: str
    title: str
    updated_at: str
    score: float
    chunk_index: int
    snippet: str


def _file_key(rel: str) -> str:
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:24]


class SearchIndexStore:
    def __init__(self, archive_dir: Path) -> None:
        self._archive_dir = archive_dir.resolve()
        self._root = self._archive_dir / "search_index"
        self._manifest_path = self._root / "manifest.json"
        self._chunk_dir = self._root / "chunks"
        self._embedding_dir = self._root / "embeddings"
        self._query_embedder: Callable[[str], list[float] | None] | None = None
        # In-memory index, built lazily and patched incrementally on refresh.
        self._loaded = False
        self._postings: dict[str, dict[str, int]] = {}
        self._chunk_len: dict[str, int] = {}
        self._chunk_texts: dict[str, list[str]] = {}
        self._vectors: dict[str, list[float]] = {}
        self._vectors_loaded = False

    # -- configuration -------------------------------------------------

    def set_query_embedder(self, fn: Callable[[str], list[float] | None] | None) -> None:
        self._query_embedder = fn

    # -- public API ----------------------------------------------------

    def search(self, query: str, *, limit: int = 50) -> list[SearchHit]:
        self.refresh()
        self._ensure_loaded()
        manifest = self._read_manifest()
        files: dict[str, dict[str, Any]] = manifest.get("files", {})
        query_tokens = tokenize(query)
        keyword_best = self._keyword_best_chunks(query_tokens)
        keyword_rank = sorted(
            keyword_best, key=lambda rel: keyword_best[rel][1], reverse=True
        )

        vector_best: dict[str, tuple[int, float]] = {}
        rankings: list[list[str]] = [keyword_rank] if keyword_rank else []
        if self._query_embedder is not None:
            vector = self._query_embedder(query)
            if vector:
                vector_best = self._vector_best_chunks(vector)
                vector_rank = sorted(
                    vector_best, key=lambda rel: vector_best[rel][1], reverse=True
                )
                if vector_rank:
                    rankings.append(vector_rank)
        if not rankings:
            return []
        if len(rankings) > 1:
            fused = rrf_merge(rankings)
            # RRF ties (e.g. two mirrored rankings): semantic similarity, then
            # keyword score, decides.
            fused.sort(
                key=lambda item: (
                    item[1],
                    vector_best.get(item[0], (0, float("-inf")))[1],
                    keyword_best.get(item[0], (0, float("-inf")))[1],
                ),
                reverse=True,
            )
        else:
            fused = [(rel, keyword_best[rel][1]) for rel in rankings[0]]

        hits: list[SearchHit] = []
        for rel, fused_score in fused[: max(1, limit)]:
            meta = files.get(rel, {})
            if rel in keyword_best:
                chunk_index = keyword_best[rel][0]
            elif rel in vector_best:
                chunk_index = vector_best[rel][0]
            else:
                chunk_index = 0
            chunks = self._chunk_texts.get(rel, [])
            chunk = chunks[chunk_index] if 0 <= chunk_index < len(chunks) else ""
            hits.append(
                SearchHit(
                    path=rel,
                    kind=str(meta.get("kind") or "unknown"),
                    title=str(meta.get("title") or Path(rel).stem),
                    updated_at=str(meta.get("updated_at") or ""),
                    score=fused_score,
                    chunk_index=chunk_index,
                    snippet=make_snippet(chunk, query_tokens),
                )
            )
        return hits

    def refresh(self) -> dict[str, int]:
        """Reconcile the index with the archive; only changed files are re-read."""
        manifest = self._read_manifest()
        files: dict[str, dict[str, Any]] = manifest.get("files", {})
        tombstoned = tombstoned_source_ids(self._archive_dir)
        seen: set[str] = set()
        indexed = removed = unchanged = 0

        if self._archive_dir.exists():
            for path in self._archive_dir.rglob("*"):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if is_operational_internal_file(path, self._archive_dir):
                    continue
                if kind_for(path, self._archive_dir) == "unknown":
                    continue
                rel = path.relative_to(self._archive_dir).as_posix()
                if rel in tombstoned:
                    continue
                seen.add(rel)
                try:
                    stat = path.stat()
                except OSError:
                    continue
                entry = files.get(rel)
                if (
                    entry is not None
                    and entry.get("mtime") == stat.st_mtime
                    and entry.get("size") == stat.st_size
                ):
                    unchanged += 1
                    continue
                self._index_file(path, rel, stat.st_mtime, stat.st_size, files)
                indexed += 1

        for rel in list(files):
            if rel not in seen:
                self._drop_file(rel, files)
                removed += 1

        if indexed or removed:
            manifest["files"] = files
            manifest["version"] = INDEX_VERSION
            self._write_manifest(manifest)
        return {"indexed": indexed, "removed": removed, "unchanged": unchanged}

    def stats(self) -> dict[str, object]:
        manifest = self._read_manifest()
        files: dict[str, dict[str, Any]] = manifest.get("files", {})
        chunks = sum(int(entry.get("chunks") or 0) for entry in files.values())
        embedded = sum(int(entry.get("embedded") or 0) for entry in files.values())
        skipped = sum(int(entry.get("embed_skipped") or 0) for entry in files.values())
        embed = manifest.get("embed", {})
        return {
            "files": len(files),
            "chunks": chunks,
            "embedded": embedded,
            "embed_skipped": skipped,
            "last_embed_run": str(embed.get("last_run") or ""),
        }

    # -- embedding storage (no HTTP here) ------------------------------

    def chunks_needing_embedding(self, *, limit: int = 500) -> list[tuple[str, int, str]]:
        self.refresh()
        manifest = self._read_manifest()
        files: dict[str, dict[str, Any]] = manifest.get("files", {})
        pending: list[tuple[str, int, str]] = []
        for rel, entry in files.items():
            total = int(entry.get("chunks") or 0)
            if total <= 0:
                continue
            vectors = self._read_embedding_file(rel)
            missing = [index for index in range(total) if str(index) not in vectors]
            if not missing:
                continue
            chunks = self._load_chunks(rel)
            for index in missing:
                if index < len(chunks):
                    pending.append((rel, index, chunks[index]))
                if len(pending) >= limit:
                    return pending
        return pending

    def store_embeddings(self, path: str, vectors: dict[int, list[float] | None]) -> None:
        if not vectors:
            return
        stored = self._read_embedding_file(path)
        for index, vector in vectors.items():
            stored[str(index)] = vector
        self._embedding_dir.mkdir(parents=True, exist_ok=True)
        write_json_file(
            self._embedding_dir / f"{_file_key(path)}.json",
            {"path": path, "model": "embedding-passage", "vectors": stored},
        )
        manifest = self._read_manifest()
        entry = manifest.get("files", {}).get(path)
        if entry is not None:
            entry["embedded"] = sum(1 for value in stored.values() if value is not None)
            entry["embed_skipped"] = sum(1 for value in stored.values() if value is None)
            self._write_manifest(manifest)
        self._vectors_loaded = False  # reload lazily with the new vectors

    def mark_embed_run(self, at: str) -> None:
        manifest = self._read_manifest()
        manifest.setdefault("embed", {})["last_run"] = at
        self._write_manifest(manifest)

    # -- internals -----------------------------------------------------

    def _keyword_best_chunks(self, query_tokens: list[str]) -> dict[str, tuple[int, float]]:
        """Best (chunk_index, bm25_score) per source for the query terms."""
        terms = set(query_tokens)
        if not terms or not self._chunk_len:
            return {}
        total_chunks = len(self._chunk_len)
        avg_len = sum(self._chunk_len.values()) / total_chunks
        scores: dict[str, float] = {}
        for term in terms:
            postings = self._postings.get(term)
            if not postings:
                continue
            df = len(postings)
            idf = math.log(1.0 + (total_chunks - df + 0.5) / (df + 0.5))
            for chunk_id, tf in postings.items():
                length = self._chunk_len.get(chunk_id, 1)
                denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * length / avg_len)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + idf * (tf * (_BM25_K1 + 1)) / denom
        best: dict[str, tuple[int, float]] = {}
        for chunk_id, score in scores.items():
            rel, _, index_text = chunk_id.rpartition("#")
            index = int(index_text)
            current = best.get(rel)
            if current is None or score > current[1]:
                best[rel] = (index, score)
        return best

    def _vector_best_chunks(self, query_vector: list[float]) -> dict[str, tuple[int, float]]:
        self._ensure_vectors_loaded()
        best: dict[str, tuple[int, float]] = {}
        for chunk_id, vector in self._vectors.items():
            if len(vector) != len(query_vector):
                continue
            score = sum(a * b for a, b in zip(query_vector, vector, strict=False))
            rel, _, index_text = chunk_id.rpartition("#")
            current = best.get(rel)
            if current is None or score > current[1]:
                best[rel] = (int(index_text), score)
        return best

    def _index_file(
        self,
        path: Path,
        rel: str,
        mtime: float,
        size: int,
        files: dict[str, dict[str, Any]],
    ) -> None:
        text = read_full_text(path)
        chunks = chunk_text(text)
        self._chunk_dir.mkdir(parents=True, exist_ok=True)
        write_json_file(self._chunk_dir / f"{_file_key(rel)}.json", {"path": rel, "chunks": chunks})
        # Vectors are stale the moment the text changes.
        embedding_file = self._embedding_dir / f"{_file_key(rel)}.json"
        if embedding_file.exists():
            embedding_file.unlink()
        files[rel] = {
            "mtime": mtime,
            "size": size,
            "kind": kind_for(path, self._archive_dir),
            "title": title_for(path, text),
            "updated_at": datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
            "chunks": len(chunks),
            "embedded": 0,
            "embed_skipped": 0,
        }
        if self._loaded:
            self._unload_from_memory(rel)
            self._load_into_memory(rel, chunks)
        self._vectors_loaded = False

    def _drop_file(self, rel: str, files: dict[str, dict[str, Any]]) -> None:
        files.pop(rel, None)
        for directory in (self._chunk_dir, self._embedding_dir):
            target = directory / f"{_file_key(rel)}.json"
            if target.exists():
                target.unlink()
        if self._loaded:
            self._unload_from_memory(rel)
        self._vectors_loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        manifest = self._read_manifest()
        for rel in manifest.get("files", {}):
            self._load_into_memory(rel, self._load_chunks(rel))
        self._loaded = True

    def _load_into_memory(self, rel: str, chunks: list[str]) -> None:
        self._chunk_texts[rel] = chunks
        for index, chunk in enumerate(chunks):
            chunk_id = f"{rel}#{index}"
            terms = tokenize(chunk)
            self._chunk_len[chunk_id] = max(1, len(terms))
            for term in terms:
                self._postings.setdefault(term, {})
                self._postings[term][chunk_id] = self._postings[term].get(chunk_id, 0) + 1

    def _unload_from_memory(self, rel: str) -> None:
        chunks = self._chunk_texts.pop(rel, [])
        for index in range(len(chunks)):
            chunk_id = f"{rel}#{index}"
            self._chunk_len.pop(chunk_id, None)
        prefix = f"{rel}#"
        for term in list(self._postings):
            postings = self._postings[term]
            for chunk_id in [key for key in postings if key.startswith(prefix)]:
                del postings[chunk_id]
            if not postings:
                del self._postings[term]

    def _ensure_vectors_loaded(self) -> None:
        if self._vectors_loaded:
            return
        self._vectors = {}
        if self._embedding_dir.exists():
            for file in self._embedding_dir.glob("*.json"):
                payload = read_json_file(file)
                if not isinstance(payload, dict):
                    continue
                rel = str(payload.get("path") or "")
                vectors = payload.get("vectors")
                if not rel or not isinstance(vectors, dict):
                    continue
                for index_text, vector in vectors.items():
                    if isinstance(vector, list) and vector:
                        self._vectors[f"{rel}#{index_text}"] = [float(v) for v in vector]
        self._vectors_loaded = True

    def _load_chunks(self, rel: str) -> list[str]:
        payload = read_json_file(self._chunk_dir / f"{_file_key(rel)}.json")
        if not isinstance(payload, dict):
            return []
        chunks = payload.get("chunks")
        if not isinstance(chunks, list):
            return []
        return [str(chunk) for chunk in chunks]

    def _read_embedding_file(self, rel: str) -> dict[str, list[float] | None]:
        payload = read_json_file(self._embedding_dir / f"{_file_key(rel)}.json")
        if not isinstance(payload, dict):
            return {}
        vectors = payload.get("vectors")
        if not isinstance(vectors, dict):
            return {}
        result: dict[str, list[float] | None] = {}
        for key, value in vectors.items():
            result[str(key)] = [float(v) for v in value] if isinstance(value, list) else None
        return result

    def _read_manifest(self) -> dict[str, Any]:
        payload = read_json_file(self._manifest_path)
        if not isinstance(payload, dict):
            return {"version": INDEX_VERSION, "files": {}, "embed": {}}
        payload.setdefault("files", {})
        payload.setdefault("embed", {})
        return payload

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        write_json_file(self._manifest_path, manifest)


__all__ = [
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "SearchHit",
    "SearchIndexStore",
    "chunk_text",
    "make_snippet",
    "rrf_merge",
    "tokenize",
]
