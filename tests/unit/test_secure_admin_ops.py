"""Secure admin storage tests."""

from __future__ import annotations

from pathlib import Path

from patch_machine.app.reset_state import reset_system_state
from patch_machine.archive.access_control import AccessControlStore, UserRecord
from patch_machine.archive.agent_execution import AgentExecutionStore, AgentPlan
from patch_machine.archive.audit_log import AuditLogStore
from patch_machine.archive.auth_store import AuthStore
from patch_machine.archive.context_compressor import CompressedContext, CompressedContextStore
from patch_machine.archive.conversation_store import ConversationRecord, ConversationStore
from patch_machine.archive.deletion_requests import DeletionRequest, DeletionRequestStore
from patch_machine.archive.memory_schema import MemorySchema, MemorySchemaStore
from patch_machine.archive.permanent_memory import PermanentMemoryStore
from patch_machine.archive.secret_store import ApiKeyRecord, SecretStore
from patch_machine.archive.uploads import UploadStore
from patch_machine.archive.volatile_memory import VolatileMemory, VolatileMemoryStore
from patch_machine.archive.work_memory import (
    WorkMemory,
    WorkMemoryStore,
    WorkScheduleItem,
    WorkScheduleStore,
)


def test_secret_store_masks_and_round_trips(archive_tmp: Path) -> None:
    store = SecretStore(archive_tmp, master_key="test-master-key")

    store.upsert(ApiKeyRecord(provider="openai", api_key="sk-test-1234567890", model="gpt-x"))

    listed = store.list_masked()
    openai = next(item for item in listed if item["provider"] == "openai")
    assert openai["configured"] is True
    assert openai["masked_value"] == "sk-t...7890"
    assert store.read("openai").api_key == "sk-test-1234567890"  # type: ignore[union-attr]


def test_access_control_blocks_viewer_from_admin_permissions(archive_tmp: Path) -> None:
    store = AccessControlStore(archive_tmp)
    store.upsert_user(
        UserRecord(id="viewer1", display_name="Viewer", title="사원", role_id="viewer")
    )

    assert store.has_permission(None, "admin:api_keys") is False
    assert store.has_permission("owner", "admin:api_keys") is True
    assert store.has_permission("viewer1", "admin:api_keys") is False
    assert store.has_permission("viewer1", "work:read") is True


def test_auth_store_setup_login_sessions_and_account_requests(archive_tmp: Path) -> None:
    store = AuthStore(archive_tmp)

    assert store.setup_required() is True
    store.create_user(user_id="admin", display_name="Admin", password="password-1234")
    token = store.authenticate("admin", "password-1234")
    request = store.request_account(
        user_id="staff1",
        display_name="Staff",
        title="사원",
        password="password-5678",
    )

    assert token is not None
    assert store.setup_required() is False
    assert store.resolve_token(token) == "admin"
    assert request.status == "pending"
    decided = store.decide_request(request.id, status="approved", decided_by="admin")
    assert decided.status == "approved"
    store.revoke_token(token)
    assert store.resolve_token(token) is None


def test_audit_log_store_appends_recent_records(archive_tmp: Path) -> None:
    store = AuditLogStore(archive_tmp)

    store.record(actor="admin", action="user.upsert", target="user", target_id="staff1")
    store.record(actor="admin", action="api_key.upsert", target="api_key", target_id="gemini")

    recent = store.list_recent(limit=2)
    assert recent[0]["action"] == "api_key.upsert"
    assert recent[1]["target_id"] == "staff1"


def test_reset_system_state_clears_local_state_and_writes_audit(archive_tmp: Path) -> None:
    workspace_dir = archive_tmp.parent / "workspaces"
    (archive_tmp / "auth.json").write_text("{}", encoding="utf-8")
    (archive_tmp / "documents").mkdir()
    (archive_tmp / "documents" / "draft.md").write_text("draft", encoding="utf-8")
    workspace_dir.mkdir()
    (workspace_dir / "repo.txt").write_text("checkout", encoding="utf-8")

    result = reset_system_state(
        archive_dir=archive_tmp,
        workspace_dir=workspace_dir,
        actor="test-admin",
    )

    assert not (archive_tmp / "auth.json").exists()
    assert not (archive_tmp / "documents").exists()
    assert not (workspace_dir / "repo.txt").exists()
    assert (archive_tmp / "audit_log.jsonl").exists()
    assert result["audit_log"] == str(archive_tmp / "audit_log.jsonl")
    assert AuditLogStore(archive_tmp).list_recent(limit=1)[0]["action"] == "system.reset"


def test_work_memory_and_schedule_round_trip(archive_tmp: Path) -> None:
    memory_store = WorkMemoryStore(archive_tmp)
    schedule_store = WorkScheduleStore(archive_tmp)

    saved_memory = memory_store.write(
        WorkMemory(
            goals="문서 자동화", current_focus="업무 스케줄 정리", next_actions="담당자 확정"
        )
    )
    saved_item = schedule_store.upsert(
        WorkScheduleItem.create(
            title="계약서 분류 자동화",
            owner_name="관리팀",
            status="in_progress",
            priority="high",
            due_date="2026-05-10",
        )
    )

    assert saved_memory.updated_at
    assert memory_store.read().current_focus == "업무 스케줄 정리"
    assert schedule_store.list()[0]["title"] == "계약서 분류 자동화"
    assert schedule_store.delete(saved_item.id) is True
    assert schedule_store.list() == []


def test_memory_redesign_stores_scan_and_round_trip(archive_tmp: Path) -> None:
    (archive_tmp / "2026" / "05").mkdir(parents=True)
    (archive_tmp / "2026" / "05" / "patch.md").write_text(
        "# Patch Log\n\nmemory source", encoding="utf-8"
    )
    AuditLogStore(archive_tmp).record(actor="admin", action="memory.test", target="memory")

    conversations = ConversationStore(archive_tmp)
    conversations.append(ConversationRecord.create(user_id="admin", role="user", content="hello"))

    permanent = PermanentMemoryStore(archive_tmp)
    assert any(source["kind"] == "patch_log" for source in permanent.recent())
    assert permanent.search("hello")

    volatile = VolatileMemoryStore(archive_tmp)
    saved_memory = volatile.write(VolatileMemory(scope="user", key="admin", summary="요약"))
    assert volatile.read(scope="user", key="admin").summary == saved_memory.summary

    compressed = CompressedContextStore(archive_tmp)
    compressed.write(
        CompressedContext(
            scope="user", key="admin", summary="압축", source_refs=["conversations/demo.jsonl"]
        )
    )
    assert compressed.read(scope="user", key="admin").source_refs == ["conversations/demo.jsonl"]

    schemas = MemorySchemaStore(archive_tmp)
    proposal = schemas.propose(
        actor="admin",
        mode="llm_propose_human_approve",
        proposal=MemorySchema(type_id="decision", display_name="결정 이력").to_dict(),
    )
    schemas.approve(str(proposal["id"]), actor="admin")
    assert schemas.list()[0]["type_id"] == "decision"

    deletions = DeletionRequestStore(archive_tmp)
    request = deletions.create(
        DeletionRequest.create(
            requester="admin",
            target_type="conversation",
            target_id="record-1",
            summary="demo",
            reason="test",
        )
    )
    assert deletions.decide(request.id, actor="admin", approved=True).status == "approved"
    assert (archive_tmp / "memory" / "tombstones.jsonl").exists()

    agents = AgentExecutionStore(archive_tmp)
    plan = agents.save_plan(
        AgentPlan.create(objective="테스트 실행", steps=[{"id": "step-1"}], created_by="admin")
    )
    assert agents.approve_plan(plan.id, actor="admin").status == "approved"
    assert (
        agents.append_run(plan.id, actor="admin", event="run_requested")["event"] == "run_requested"
    )


def test_upload_store_saves_and_deletes_file(archive_tmp: Path) -> None:
    store = UploadStore(archive_tmp)
    source = __import__("io").BytesIO(b"hello")

    record = store.save(filename="hello.txt", source=source, description="demo")

    assert (archive_tmp / record.path).exists()
    assert store.list()[0]["filename"] == "hello.txt"
    assert store.delete(record.id) is True
    assert not (archive_tmp / record.path).exists()
