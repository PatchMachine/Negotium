"""Work schedule store: updated_at must survive reads and only move on writes."""

from __future__ import annotations

from pathlib import Path

from negotium.archive.work_memory import WorkScheduleItem, WorkScheduleStore


def test_updated_at_is_stable_across_reads(archive_tmp: Path) -> None:
    store = WorkScheduleStore(archive_tmp)
    store.upsert(WorkScheduleItem.create(title="업무 A", owner_id="alice"))
    store.upsert(WorkScheduleItem.create(title="업무 B", owner_id="bob"))

    first = {row["id"]: row["updated_at"] for row in store.list()}
    second = {row["id"]: row["updated_at"] for row in store.list()}

    assert first == second, "list() must not rewrite updated_at"


def test_upsert_stamps_only_the_written_item(archive_tmp: Path) -> None:
    store = WorkScheduleStore(archive_tmp)
    saved_a = store.upsert(WorkScheduleItem.create(title="업무 A", owner_id="alice"))
    saved_b = store.upsert(WorkScheduleItem.create(title="업무 B", owner_id="bob"))
    before = {row["id"]: row["updated_at"] for row in store.list()}

    item_a = store.get(saved_a.id)
    assert item_a is not None
    store.upsert(WorkScheduleItem.create(**{**item_a.to_dict(), "status": "in_progress"}))

    after = {row["id"]: row["updated_at"] for row in store.list()}
    assert after[saved_a.id] > before[saved_a.id], "written item must get a fresh timestamp"
    assert after[saved_b.id] == before[saved_b.id], "untouched item must keep its timestamp"


def test_from_mapping_preserves_stored_timestamps(archive_tmp: Path) -> None:
    stamp = "2026-01-01T00:00:00+00:00"
    item = WorkScheduleItem.from_mapping(
        {"id": "x", "title": "t", "created_at": stamp, "updated_at": stamp}
    )
    assert item.created_at == stamp
    assert item.updated_at == stamp
