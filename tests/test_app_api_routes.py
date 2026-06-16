"""React API 路由边界测试。"""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import VLMChatAssistant
from src.chat_manager import ChatManager


@pytest.fixture
def assistant(tmp_path, monkeypatch):
    test_dir = str(tmp_path / "sessions")
    monkeypatch.setattr("src.chat_manager.HISTORY_STORAGE_DIR", test_dir)
    os.makedirs(test_dir, exist_ok=True)

    app = VLMChatAssistant.__new__(VLMChatAssistant)
    app.chat_manager = ChatManager()
    app.user_id = app.chat_manager.upsert_user("api-test-user", user_id="api-test-user")
    app._session_api_clients = {}
    app._rate_buckets = {}
    app.rag_manager = None
    return app


@pytest.fixture
def api_client(assistant):
    api_app = FastAPI()
    assistant.register_react_api_routes(api_app)
    return TestClient(api_app)


def test_api_get_messages_returns_404_for_unknown_session(api_client, assistant):
    existing = assistant.chat_manager.get_session_count()

    response = api_client.get("/api/sessions/missing-session/messages")

    assert response.status_code == 404
    assert assistant.chat_manager.get_session_count() == existing


def test_api_get_messages_returns_session_history(api_client, assistant):
    session_id = assistant.chat_manager.create_session(name="API 会话", user_id=assistant.user_id)
    assistant.chat_manager.add_message(session_id, "user", "你好")
    assistant.chat_manager.add_message(session_id, "assistant", "你好！")

    response = api_client.get(f"/api/sessions/{session_id}/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["id"] == session_id
    assert [item["role"] for item in payload["messages"]] == ["user", "assistant"]


def test_api_chat_returns_404_for_unknown_session(api_client, assistant):
    existing = assistant.chat_manager.get_session_count()

    response = api_client.post("/api/chat", data={"session_id": "missing-session", "message": "你好"})

    assert response.status_code == 404
    assert assistant.chat_manager.get_session_count() == existing


def test_apply_model_config_rejects_unknown_provider(assistant):
    ok, message, provider, _, client = assistant._apply_model_config(
        session_id="session-a",
        provider="missing-provider",
        model="",
        use_custom_api=False,
        custom_base_url="",
        custom_api_key="",
        custom_model="",
    )

    assert ok is False
    assert "不支持的模型提供方" in message
    assert provider == "missing-provider"
    assert client is None


def test_apply_model_config_reports_missing_builtin_api_key(assistant, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    ok, message, provider, _, client = assistant._apply_model_config(
        session_id="session-a",
        provider="openai",
        model="gpt-4o",
        use_custom_api=False,
        custom_base_url="",
        custom_api_key="",
        custom_model="",
    )

    assert ok is False
    assert "OPENAI_API_KEY" in message
    assert provider == "openai"
    assert client is None
