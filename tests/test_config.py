"""配置解析测试。"""

import importlib

import src.config as config


def test_config_invalid_numbers_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "not-a-number")
    monkeypatch.setenv("MAX_IMAGES_PER_MESSAGE", "0")
    monkeypatch.setenv("GRADIO_SERVER_PORT", "-1")

    reloaded = importlib.reload(config)

    assert reloaded.REQUESTS_PER_MINUTE == 20
    assert reloaded.MAX_IMAGES_PER_MESSAGE == 4
    assert reloaded.GRADIO_SERVER_PORT == 7860


def test_config_invalid_default_provider_falls_back(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "missing-provider")

    reloaded = importlib.reload(config)

    assert reloaded.DEFAULT_PROVIDER == "dashscope"
