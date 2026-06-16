"""
应用层模型配置测试
"""
from app import VLMChatAssistant


def test_custom_model_config_is_isolated_by_session():
    app = VLMChatAssistant.__new__(VLMChatAssistant)
    app._session_api_clients = {}

    ok_a, _, provider_a, model_a, client_a = app._apply_model_config(
        session_id="session-a",
        provider="dashscope",
        model="qwen-vl-plus",
        use_custom_api=True,
        custom_base_url="https://a.example.com/v1",
        custom_api_key="key-a",
        custom_model="model-a",
    )
    ok_b, _, provider_b, model_b, client_b = app._apply_model_config(
        session_id="session-b",
        provider="dashscope",
        model="qwen-vl-plus",
        use_custom_api=True,
        custom_base_url="https://b.example.com/v1",
        custom_api_key="key-b",
        custom_model="model-b",
    )

    assert ok_a is True
    assert ok_b is True
    assert provider_a == "custom"
    assert provider_b == "custom"
    assert model_a == "model-a"
    assert model_b == "model-b"
    assert client_a is not client_b
    assert app._session_api_clients["session-a"].base_url == "https://a.example.com/v1"
    assert app._session_api_clients["session-a"].api_key == "key-a"
    assert app._session_api_clients["session-b"].base_url == "https://b.example.com/v1"
    assert app._session_api_clients["session-b"].api_key == "key-b"
