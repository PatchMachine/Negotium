"""Turn-based conversations: per-thread replay, listing, and the context meter."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from negotium.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test",
            archive_dir=tmp_path / "archive",
            workspace_dir=tmp_path / "workspaces",
        )
    )


def _auth_headers(container: Container, user_id: str = "owner") -> dict[str, str]:
    container.auth_store.create_user(
        user_id=user_id, display_name="Local Owner", password="password-1234"
    )
    container.access_control.upsert_user(
        UserRecord(id=user_id, display_name="Local Owner", title="대표", role_id="owner")
    )
    token = container.auth_store.authenticate(user_id, "password-1234")
    assert token is not None
    return {"X-NG-User": f"Bearer {token}"}


def _chat(client: TestClient, headers: dict[str, str], message: str, **extra: object) -> dict:
    response = client.post(
        "/api/llm/chat",
        headers=headers,
        json={"message": message, "route": "api", "provider": "fake", **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_separate_conversations_do_not_bleed_into_each_other(tmp_path: Path) -> None:
    """Replay is scoped to one conversation.

    The old behaviour replayed "the user's last N records" regardless of which
    chat they came from, so an unrelated thread was spliced into every prompt.
    """

    container = _container(tmp_path)
    headers = _auth_headers(container)
    fake = FakeLlmProvider(
        responses=[ScriptedResponse(text=f"응답 {index}") for index in range(1, 6)]
    )
    container.llm = fake
    app = create_app(container)

    with TestClient(app) as client:
        first = _chat(client, headers, "내 이름은 지호야", conversation_id="chat-a")
        _chat(client, headers, "취미는 등산이야", conversation_id="chat-a")
        # A different conversation must start clean.
        _chat(client, headers, "완전히 다른 주제", conversation_id="chat-b")

    assert first["conversation_id"] == "chat-a"
    chat_b_prompt = "\n".join(
        message.content for message in fake.calls[-1] if isinstance(message.content, str)
    )
    assert "지호" not in chat_b_prompt
    assert "등산" not in chat_b_prompt


def test_a_conversation_replays_its_own_turns(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    fake = FakeLlmProvider(
        responses=[ScriptedResponse(text="반가워요 지호님"), ScriptedResponse(text="등산 좋죠")]
    )
    container.llm = fake
    app = create_app(container)

    with TestClient(app) as client:
        _chat(client, headers, "내 이름은 지호야", conversation_id="chat-a")
        second = _chat(client, headers, "내 이름 뭐랬지?", conversation_id="chat-a")

    replayed = "\n".join(
        message.content for message in fake.calls[-1] if isinstance(message.content, str)
    )
    assert "내 이름은 지호야" in replayed
    assert "반가워요 지호님" in replayed
    assert second["used_history"] >= 2


def test_conversation_list_groups_by_id_not_by_time_gap(tmp_path: Path) -> None:
    """Two chats started seconds apart must stay separate."""

    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        responses=[ScriptedResponse(text=f"응답 {index}") for index in range(1, 5)]
    )
    app = create_app(container)

    with TestClient(app) as client:
        _chat(client, headers, "회의록 정리 부탁해", conversation_id="chat-a")
        _chat(client, headers, "추가로 하나 더", conversation_id="chat-a")
        _chat(client, headers, "채용 공고 써줘", conversation_id="chat-b")
        listing = client.get("/api/llm/conversations", headers=headers)

    assert listing.status_code == 200
    conversations = {item["conversation_id"]: item for item in listing.json()["conversations"]}
    assert set(conversations) == {"chat-a", "chat-b"}
    assert conversations["chat-a"]["message_count"] == 4  # 2 user + 2 assistant
    assert conversations["chat-a"]["title"] == "회의록 정리 부탁해"
    assert conversations["chat-b"]["title"] == "채용 공고 써줘"


def test_reading_one_conversation_returns_its_turns_in_order(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        responses=[ScriptedResponse(text="첫 답변"), ScriptedResponse(text="둘째 답변")]
    )
    app = create_app(container)

    with TestClient(app) as client:
        _chat(client, headers, "첫 질문", conversation_id="chat-a")
        _chat(client, headers, "둘째 질문", conversation_id="chat-a")
        detail = client.get("/api/llm/conversations/chat-a", headers=headers)

    assert detail.status_code == 200
    turns = detail.json()["turns"]
    assert [turn["role"] for turn in turns] == ["user", "assistant", "user", "assistant"]
    assert [turn["content"] for turn in turns] == ["첫 질문", "첫 답변", "둘째 질문", "둘째 답변"]


def test_omitting_the_id_continues_the_latest_conversation(tmp_path: Path) -> None:
    """Plain API clients should not have to track ids to hold a conversation."""

    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        responses=[ScriptedResponse(text="응답 1"), ScriptedResponse(text="응답 2")]
    )
    app = create_app(container)

    with TestClient(app) as client:
        first = _chat(client, headers, "첫 질문")
        second = _chat(client, headers, "둘째 질문")

    assert first["conversation_id"]
    assert second["conversation_id"] == first["conversation_id"]
    assert second["used_history"] >= 2


def test_context_meter_reports_window_usage(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        responses=[ScriptedResponse(text="네", prompt_tokens=1200, completion_tokens=40)]
    )
    app = create_app(container)

    with TestClient(app) as client:
        payload = _chat(client, headers, "안녕", conversation_id="chat-a")

    context = payload["context"]
    assert context["prompt_tokens"] == 1200
    assert context["completion_tokens"] == 40
    assert context["context_window"] > 0
    assert 0 < context["used_ratio"] < 1
    assert context["estimated"] is False


def test_context_meter_estimates_when_the_provider_reports_nothing(tmp_path: Path) -> None:
    """Most local/stub providers return no usage; the meter must still work."""

    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(responses=[ScriptedResponse(text="네")])
    app = create_app(container)

    with TestClient(app) as client:
        payload = _chat(client, headers, "회사 상황 요약해줘", conversation_id="chat-a")

    context = payload["context"]
    assert context["estimated"] is True
    assert context["prompt_tokens"] > 0


def test_legacy_transcripts_without_an_id_stay_browsable(tmp_path: Path) -> None:
    """Existing installs have transcripts predating conversation tracking."""

    container = _container(tmp_path)
    root = tmp_path / "archive" / "conversations"
    root.mkdir(parents=True, exist_ok=True)
    (root / "2026-07-20_owner.jsonl").write_text(
        '{"id":"1","user_id":"owner","role":"user","content":"예전 질문",'
        '"provider":"solar","model":"solar-pro2","route":"api",'
        '"created_at":"2026-07-20T01:00:00+00:00","derived_from":[],"metadata":{}}\n',
        encoding="utf-8",
    )

    conversations = container.conversations.list_conversations(user_id="owner")

    assert len(conversations) == 1
    assert conversations[0]["legacy"] is True
    assert conversations[0]["title"] == "예전 질문"
