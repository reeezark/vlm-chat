import os
from unittest.mock import patch

import pytest

from src.model_config import (
    ModelConfigError,
    classify_model_error,
    resolve_runtime_model_config,
)


def test_resolve_builtin_openai_config_uses_env_key_and_model():
    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key", "OPENAI_MODEL_NAME": "custom-vlm"}, clear=False),
        patch("src.model_config.DEFAULT_PROVIDER", "openai"),
    ):
        config = resolve_runtime_model_config(provider="openai")

    assert config.provider == "openai"
    assert config.model == "custom-vlm"
    assert config.api_key == "openai-key"
    assert config.key_source == "OPENAI_API_KEY"
    assert not config.is_custom


def test_resolve_custom_config_validates_required_fields():
    with pytest.raises(ModelConfigError, match="API 地址不能为空") as exc:
        resolve_runtime_model_config(use_custom_api=True, custom_api_key="key", custom_model="model")

    assert exc.value.code == "missing_base_url"


def test_resolve_custom_config_rejects_invalid_url():
    with pytest.raises(ModelConfigError) as exc:
        resolve_runtime_model_config(
            use_custom_api=True,
            custom_base_url="not-a-url",
            custom_api_key="key",
            custom_model="model",
        )

    assert exc.value.code == "invalid_base_url"


def test_resolve_custom_config_safe_summary_masks_key():
    config = resolve_runtime_model_config(
        use_custom_api=True,
        custom_base_url="https://example.com/v1/",
        custom_api_key="secret-key",
        custom_model="custom-vlm",
    )
    summary = config.safe_summary()

    assert config.base_url == "https://example.com/v1"
    assert summary["provider"] == "custom"
    assert summary["hasApiKey"] is True
    assert "secret-key" not in str(summary)


def test_builtin_missing_api_key_does_not_fallback_to_other_provider():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "", "DASHSCOPE_API_KEY": "dash-key"}, clear=False):
        with pytest.raises(ModelConfigError) as exc:
            resolve_runtime_model_config(provider="openai")

    assert exc.value.code == "missing_api_key"


def test_classify_quota_error():
    code, message = classify_model_error(Exception("403 AllocationQuota.FreeTierOnly"))

    assert code == "quota_or_permission"
    assert "额度" in message
