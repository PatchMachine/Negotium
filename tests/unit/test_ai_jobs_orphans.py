"""Jobs stranded by a dead process get closed out, not left polling forever."""

from __future__ import annotations

from pathlib import Path

from negotium.archive.ai_jobs import AiJobStore


def test_fail_orphans_closes_running_and_queued_jobs(tmp_path: Path) -> None:
    store = AiJobStore(tmp_path)
    stranded = store.create(task="initial_office_setup.chat", actor="Upstage")
    store.update(stranded.with_status("running"))
    queued = store.create(task="documents.generate", actor="Upstage")
    done = store.create(task="reports.weekly", actor="Upstage")
    store.update(done.with_status("succeeded", result_path="reports/weekly.md"))

    closed = store.fail_orphans()

    assert {record.job_id for record in closed} == {stranded.job_id, queued.job_id}
    by_id = {record.job_id: record for record in store.recent(limit=100)}
    assert by_id[stranded.job_id].status == "failed"
    assert by_id[stranded.job_id].error
    assert by_id[queued.job_id].status == "failed"
    # A finished job is never rewritten.
    assert by_id[done.job_id].status == "succeeded"
    assert by_id[done.job_id].result_path == "reports/weekly.md"


def test_fail_orphans_is_idempotent(tmp_path: Path) -> None:
    store = AiJobStore(tmp_path)
    record = store.create(task="initial_office_setup.chat", actor="Upstage")
    store.update(record.with_status("running"))

    assert len(store.fail_orphans()) == 1
    assert store.fail_orphans() == []
