"""Conversation transcripts: cross-day history and agent-trace metadata."""

from __future__ import annotations

from pathlib import Path

from negotium.archive.conversation_store import ConversationStore


def test_history_survives_the_utc_date_rollover(tmp_path: Path) -> None:
    """Transcripts are sharded per day; reading only today's shard loses history.

    Before the fix ``list_recent(user_id=...)`` looked at a single dated file,
    so every conversation silently disappeared at UTC midnight.
    """

    store = ConversationStore(tmp_path)
    root = tmp_path / "conversations"
    root.mkdir(parents=True, exist_ok=True)
    # Hand-write two earlier days plus a differently-named user, mirroring the
    # `YYYY-MM-DD_<user>.jsonl` layout the store writes.
    (root / "2026-07-25_owner.jsonl").write_text(
        '{"id":"1","user_id":"owner","role":"user","content":"이틀 전 질문",'
        '"provider":"solar","model":"solar-pro3","route":"api",'
        '"created_at":"2026-07-25T01:00:00+00:00","derived_from":[],"metadata":{}}\n',
        encoding="utf-8",
    )
    (root / "2026-07-26_owner.jsonl").write_text(
        '{"id":"2","user_id":"owner","role":"user","content":"어제 질문",'
        '"provider":"solar","model":"solar-pro3","route":"api",'
        '"created_at":"2026-07-26T01:00:00+00:00","derived_from":[],"metadata":{}}\n',
        encoding="utf-8",
    )
    (root / "2026-07-26_other.jsonl").write_text(
        '{"id":"3","user_id":"other","role":"user","content":"남의 대화",'
        '"provider":"solar","model":"solar-pro3","route":"api",'
        '"created_at":"2026-07-26T01:00:00+00:00","derived_from":[],"metadata":{}}\n',
        encoding="utf-8",
    )

    store.append_pair(
        user_id="owner",
        user_message="오늘 질문",
        assistant_message="오늘 답변",
        provider="solar",
        model="solar-pro3",
        route="api",
    )

    contents = [record["content"] for record in store.list_recent(user_id="owner", limit=50)]
    assert "이틀 전 질문" in contents
    assert "어제 질문" in contents
    assert "오늘 질문" in contents
    # Another user's shard must not leak in through the glob.
    assert "남의 대화" not in contents


def test_append_pair_persists_agent_trace_and_returns_ids(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path)
    trace = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "org.roster"}]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"users": []}'},
    ]
    user_id, assistant_id = store.append_pair(
        user_id="owner",
        user_message="조직 인원 알려줘",
        assistant_message="12명입니다.",
        provider="solar",
        model="solar-pro3",
        route="api",
        assistant_metadata={
            "conversation_id": "conv-1",
            "tier": "agent",
            "reasoning": "명부를 조회한다.",
            "agent_trace": trace,
        },
    )

    assert user_id and assistant_id and user_id != assistant_id
    records = store.list_recent(user_id="owner", limit=10)
    assistant = next(record for record in records if record["role"] == "assistant")
    metadata = assistant["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["conversation_id"] == "conv-1"
    # The Solar model card warns against stripping reasoning from earlier turns
    # when building follow-up requests, so it has to be persisted.
    assert metadata["reasoning"] == "명부를 조회한다."
    assert metadata["agent_trace"][1]["tool_call_id"] == "c1"


def test_append_pair_without_metadata_stays_backwards_compatible(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path)
    store.append_pair(
        user_id="owner",
        user_message="안녕",
        assistant_message="안녕하세요",
        provider="solar",
        model="solar-pro3",
        route="api",
    )
    records = store.list_recent(user_id="owner", limit=10)
    assert {record["role"] for record in records} == {"user", "assistant"}
    assert all(record["metadata"] == {} for record in records)


def test_a_user_id_prefix_does_not_leak_another_users_transcript(tmp_path: Path) -> None:
    """`*_user.jsonl` also matched `2026-07-27_admin_user.jsonl`."""

    store = ConversationStore(tmp_path)
    root = tmp_path / "conversations"
    root.mkdir(parents=True, exist_ok=True)
    (root / "2026-07-26_admin_user.jsonl").write_text(
        '{"id":"1","user_id":"admin_user","role":"user","content":"관리자 비밀 대화",'
        '"provider":"solar","model":"solar-pro3","route":"api",'
        '"created_at":"2026-07-26T01:00:00+00:00","derived_from":[],"metadata":{}}\n',
        encoding="utf-8",
    )
    store.append_pair(
        user_id="user",
        user_message="내 질문",
        assistant_message="내 답변",
        provider="solar",
        model="solar-pro3",
        route="api",
    )

    contents = [record["content"] for record in store.list_recent(user_id="user", limit=50)]
    assert "내 질문" in contents
    assert "관리자 비밀 대화" not in contents
