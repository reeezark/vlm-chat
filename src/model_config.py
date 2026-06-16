"""模型配置解析、校验与安全摘要。"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from openai import OpenAI

from .config import DEFAULT_PROVIDER, MODEL_NAME, PROVIDERS


class ModelConfigError(ValueError):
    """模型配置校验错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RuntimeModelConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    is_custom: bool = False
    key_source: str = "env"
    label: str = ""

    @property
    def config_hash(self) -> str:
        source = f"{self.provider}|{self.model}|{self.base_url}|{self._key_fingerprint()}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]

    def _key_fingerprint(self) -> str:
        if not self.api_key:
            return ""
        return hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:10]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "label": self.label or self.provider,
            "model": self.model,
            "baseUrl": self.base_url,
            "isCustom": self.is_custom,
            "keySource": self.key_source,
            "hasApiKey": bool(self.api_key),
            "configHash": self.config_hash,
        }


def _validate_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise ModelConfigError("missing_base_url", "API 地址不能为空")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelConfigError("invalid_base_url", "API 地址格式不正确，请填写 http(s) URL")
    return normalized


def _normalize_provider(provider: Optional[str]) -> str:
    provider_id = (provider or DEFAULT_PROVIDER or "dashscope").strip().lower()
    if provider_id not in PROVIDERS:
        raise ModelConfigError("unsupported_provider", f"不支持的模型提供方: {provider_id}")
    return provider_id


def provider_models(provider: str) -> list[str]:
    provider_id = _normalize_provider(provider)
    return list(PROVIDERS[provider_id].get("models") or [])


def provider_requires_key(provider: str) -> bool:
    return _normalize_provider(provider) != "ollama"


def resolve_runtime_model_config(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    use_custom_api: bool = False,
    custom_base_url: str = "",
    custom_api_key: str = "",
    custom_model: str = "",
) -> RuntimeModelConfig:
    """将前端/环境变量配置解析为统一运行时模型配置。"""
    if use_custom_api:
        base_url = _validate_url(custom_base_url)
        api_key = (custom_api_key or "").strip()
        model_name = (custom_model or "").strip()
        if not api_key:
            raise ModelConfigError("missing_api_key", "自定义 API Key 不能为空")
        if not model_name:
            raise ModelConfigError("missing_model", "自定义模型名称不能为空")
        return RuntimeModelConfig(
            provider="custom",
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            is_custom=True,
            key_source="custom",
            label="自定义 OpenAI 兼容接口",
        )

    provider_id = _normalize_provider(provider)
    conf = PROVIDERS[provider_id]
    base_url = _validate_url(conf["base_url"])
    api_key = os.getenv(conf["api_key_env"], "").strip()
    provider_model = os.getenv(f"{provider_id.upper()}_MODEL_NAME", "").strip()
    if provider_model:
        model_name = provider_model
    elif provider_id == DEFAULT_PROVIDER and MODEL_NAME:
        model_name = MODEL_NAME
    else:
        models = conf.get("models") or []
        model_name = models[0] if models else ""
    model_name = (model or model_name or "").strip()
    if not model_name:
        raise ModelConfigError("missing_model", "模型名称不能为空")
    if provider_requires_key(provider_id) and not api_key:
        raise ModelConfigError(
            "missing_api_key",
            f"{conf['label']} 未配置 API Key，请设置 {conf['api_key_env']}，或启用自定义 OpenAI 兼容接口。",
        )
    return RuntimeModelConfig(
        provider=provider_id,
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        is_custom=False,
        key_source=conf["api_key_env"] if api_key else "none",
        label=conf["label"],
    )


def classify_model_error(error: Exception) -> tuple[str, str]:
    text = str(error)
    lowered = text.lower()
    if "401" in text or "invalid_api_key" in lowered or "unauthorized" in lowered:
        return "invalid_api_key", "API Key 无效或无权限"
    if "403" in text or "quota" in lowered or "free tier" in lowered:
        return "quota_or_permission", "模型服务额度不足或权限受限"
    if "404" in text or "model_not_found" in lowered:
        return "model_not_found", "模型不存在或当前账号无权访问该模型"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout", "模型服务连接超时"
    return "model_call_failed", text


def test_runtime_model_config(config: RuntimeModelConfig, timeout: float = 8.0) -> dict[str, Any]:
    """调用 OpenAI 兼容接口做一次轻量连接测试。"""
    started = time.time()
    try:
        client = OpenAI(
            api_key=config.api_key or "ollama",
            base_url=config.base_url,
            timeout=timeout,
        )
        client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            temperature=0,
        )
        return {
            "ok": True,
            "errorCode": "",
            "message": "连接测试成功",
            "latencyMs": round((time.time() - started) * 1000, 2),
            "summary": config.safe_summary(),
        }
    except Exception as error:
        code, message = classify_model_error(error)
        return {
            "ok": False,
            "errorCode": code,
            "message": message,
            "detail": str(error)[:500],
            "latencyMs": round((time.time() - started) * 1000, 2),
            "summary": config.safe_summary(),
        }
