"""Notification store: visibility, ordering, read marking, cap, round-trips."""

from __future__ import annotations

from pathlib import Path

from negotium.archive.notifications import NotificationRecord, NotificationStore


def _record(**overrides: object) -> NotificationRecord:
    payload: dict[str, object] = {"title": "알림", "body": "본문", **overrides}
    return NotificationRecord.create(**payload)


def test_broadcast_and_own_visibility(archive_tmp: Path) -> None:
    store = NotificationStore(archive_tmp)
    store.add(_record(title="공지", user_id=""))
    store.add(_record(title="앨리스 전용", user_id="alice"))
    store.add(_record(title="밥 전용", user_id="bob"))

    titles = [item["title"] for item in store.list_for("alice")]
    assert "공지" in titles
    assert "앨리스 전용" in titles
    assert "밥 전용" not in titles


def test_listing_is_newest_first(archive_tmp: Path) -> None:
    store = NotificationStore(archive_tmp)
    store.add(_record(title="옛날", created_at="2026-01-01T00:00:00+00:00"))
    store.add(_record(title="최신", created_at="2026-07-01T00:00:00+00:00"))

    titles = [item["title"] for item in store.list_for("anyone")]
    assert titles[0] == "최신"


def test_mark_read_is_idempotent_and_per_user(archive_tmp: Path) -> None:
    store = NotificationStore(archive_tmp)
    saved = store.add(_record(title="공지"))

    assert store.mark_read([saved.id], "alice") == 1
    assert store.mark_read([saved.id], "alice") == 0, "second mark must be a no-op"
    assert store.mark_read([saved.id], "bob") == 1

    listed = store.list_for("alice")[0]
    assert sorted(listed["read_by"]) == ["alice", "bob"]  # type: ignore[arg-type]


def test_cap_drops_oldest_records(archive_tmp: Path) -> None:
    store = NotificationStore(archive_tmp)
    for index in range(NotificationStore.MAX_RECORDS + 5):
        store.add(_record(title=f"n{index}", created_at=f"2026-01-01T00:00:{index % 60:02d}+00:00"))

    listed = store.list_for("anyone", limit=NotificationStore.MAX_RECORDS + 10)
    assert len(listed) == NotificationStore.MAX_RECORDS


def test_round_trip_preserves_created_at_and_read_state(archive_tmp: Path) -> None:
    store = NotificationStore(archive_tmp)
    saved = store.add(_record(title="공지", created_at="2026-03-01T00:00:00+00:00"))
    store.mark_read([saved.id], "alice")

    first = store.list_for("alice")[0]
    second = store.list_for("alice")[0]
    assert first["created_at"] == "2026-03-01T00:00:00+00:00"
    assert first == second, "reads must not mutate records"
