"""
配置文件
存储API密钥、模型名称和其他配置参数
"""
import os
from typing import Optional

# 尝试从.env文件加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()  # 加载.env文件中的环境变量
except ImportError:
    # 如果没有安装python-dotenv，继续使用系统环境变量
    pass

def _get_str(name: str, default: str) -> str:
    """读取字符串环境变量，空值回退默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_bool(name: str, default: bool = False) -> bool:
    """读取布尔环境变量，无法识别时回退默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _get_int(name: str, default: int, min_value: Optional[int] = None) -> int:
    """读取整数环境变量，非法或越界时回退默认值。"""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and parsed < min_value:
        return default
    return parsed


# API配置 - 从环境变量或.env文件获取
APP_ENV: str = _get_str('APP_ENV', 'development').lower()  # development / production
DASHSCOPE_API_KEY: str = os.getenv('DASHSCOPE_API_KEY', '')  # API密钥
BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # OpenAI兼容接口地址
MODEL_NAME: str = _get_str('MODEL_NAME', 'qwen-vl-plus')  # 模型名称（可配置）
DEFAULT_PROVIDER: str = _get_str("DEFAULT_PROVIDER", "dashscope").lower()  # 默认 Provider


def _provider_models(provider: str, defaults: list[str]) -> list[str]:
    """解析 Provider 模型列表，支持通过 .env 覆盖默认模型。"""
    models_env = os.getenv(f"{provider.upper()}_MODELS", "")
    if models_env:
        candidates = [item.strip() for item in models_env.split(",") if item.strip()]
    else:
        candidates = []
        model_name = os.getenv(f"{provider.upper()}_MODEL_NAME", "").strip()
        if model_name:
            candidates.append(model_name)
        if DEFAULT_PROVIDER == provider and MODEL_NAME:
            candidates.append(MODEL_NAME)
        candidates.extend(defaults)

    deduped: list[str] = []
    for model in candidates:
        if model and model not in deduped:
            deduped.append(model)
    return deduped or defaults

# ── 多 Provider 配置（P0-3）──────────────────────────────────────
# 每个 Provider 走 OpenAI 兼容协议，可通过 UI / 环境变量切换。
# api_key_env 指定从哪个环境变量读取密钥；models 列出可选视觉模型。
PROVIDERS: dict[str, dict] = {
    "dashscope": {
        "label": "通义千问 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "models": _provider_models("dashscope", ["qwen-vl-plus", "qwen-vl-max", "qwen-vl-max-latest"]),
    },
    "openai": {
        "label": "OpenAI",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "api_key_env": "OPENAI_API_KEY",
        "models": _provider_models("openai", ["gpt-4o", "gpt-4o-mini", "gpt-4.1"]),
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "models": _provider_models("openrouter", ["qwen/qwen2.5-vl-72b-instruct", "google/gemini-2.0-flash-001"]),
    },
    "ollama": {
        "label": "本地 Ollama",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "api_key_env": "OLLAMA_API_KEY",  # Ollama 通常无需密钥
        "models": _provider_models("ollama", ["llama3.2-vision", "qwen2.5vl"]),
    },
}

if DEFAULT_PROVIDER not in PROVIDERS:
    DEFAULT_PROVIDER = "dashscope"

# ── System Prompt（P0-4）─────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT: str = os.getenv(
    "SYSTEM_PROMPT",
    "你是一个有帮助的多模态智能助手，擅长理解图片并用简洁、准确的中文回答用户问题。",
)

# ── 工具调用 / 联网搜索（P0-4）──────────────────────────────────
ENABLE_TOOLS: bool = _get_bool("ENABLE_TOOLS", True)  # 是否启用工具调用
WEB_SEARCH_MAX_RESULTS: int = _get_int("WEB_SEARCH_MAX_RESULTS", 5, min_value=1)  # 联网搜索返回结果数
WEB_SEARCH_TIMEOUT: int = _get_int("WEB_SEARCH_TIMEOUT", 8, min_value=1)  # 联网搜索超时（秒）
WEB_SEARCH_MAX_QUERY_CHARS: int = _get_int("WEB_SEARCH_MAX_QUERY_CHARS", 200, min_value=1)  # 搜索词最大长度
WEB_SEARCH_MAX_RESULT_CHARS: int = _get_int("WEB_SEARCH_MAX_RESULT_CHARS", 2000, min_value=1)  # 搜索结果最大返回字符数

# ── 数据库存储（P0-2）───────────────────────────────────────────
SESSION_DB_DIR: str = os.getenv("SESSION_DB_DIR", "data/sessions")  # 会话数据库目录

# 图片配置
MAX_IMAGE_SIZE: int = 5 * 1024 * 1024  # 最大图片大小5MB
ALLOWED_FORMATS: list[str] = ['jpg', 'jpeg', 'png', 'webp']  # 支持的图片格式
TEMP_IMAGE_DIR: str = "data/temp_images"  # 临时图片存储目录
UPLOAD_IMAGE_DIR: str = "data/uploads"  # 持久化上传图片目录（跨会话/重启可用）

# ── 多图 / 文档输入（P1-5）──────────────────────────────────────
MAX_IMAGES_PER_MESSAGE: int = _get_int("MAX_IMAGES_PER_MESSAGE", 4, min_value=1)  # 单条消息最多图片数
ALLOWED_DOC_FORMATS: list[str] = ['pdf']  # 支持解析文本的文档格式
MAX_DOC_SIZE: int = _get_int("MAX_DOC_SIZE_MB", 10, min_value=1) * 1024 * 1024  # 最大文档大小
MAX_DOC_TEXT_CHARS: int = _get_int("MAX_DOC_TEXT_CHARS", 8000, min_value=1)  # 文档提取文本最大字符数
MAX_PDF_PAGES: int = _get_int("MAX_PDF_PAGES", 20, min_value=1)  # 单个 PDF 最大解析页数
UPLOAD_RETENTION_SECONDS: int = _get_int("UPLOAD_RETENTION_SECONDS", 7 * 24 * 3600, min_value=0)  # 上传文件保留时间
IMAGE_BASE64_CACHE_SIZE: int = _get_int("IMAGE_BASE64_CACHE_SIZE", 128, min_value=1)  # 图片 base64 编码缓存容量

# ── RAG MVP（知识库检索增强）────────────────────────────────────
ENABLE_RAG: bool = _get_bool("ENABLE_RAG", True)  # 是否启用轻量 RAG
RAG_DEFAULT_COLLECTION: str = os.getenv("RAG_DEFAULT_COLLECTION", "默认知识库")  # 默认知识库名称
RAG_CHUNK_SIZE: int = _get_int("RAG_CHUNK_SIZE", 800, min_value=1)  # 文档切片字符数
RAG_CHUNK_OVERLAP: int = _get_int("RAG_CHUNK_OVERLAP", 120, min_value=0)  # 文档切片重叠字符数
RAG_TOP_K: int = _get_int("RAG_TOP_K", 3, min_value=1)  # 每次检索返回片段数
RAG_EMBEDDING_DIM: int = _get_int("RAG_EMBEDDING_DIM", 128, min_value=16)  # 本地哈希向量维度

# 会话配置
MAX_HISTORY_LENGTH: int = 10  # 最大对话轮数
SESSION_TIMEOUT: int = 3600  # 会话超时时间（秒）

# 生成参数
TEMPERATURE: float = 0.7  # 温度参数
MAX_TOKENS: int = 512  # 最大生成token数
TOP_P: float = 0.9  # Top-p采样参数

# 界面配置
GRADIO_SERVER_NAME: str = _get_str('GRADIO_SERVER_NAME', '127.0.0.1')  # Gradio服务器地址（默认仅本机，对外暴露需显式设置）
GRADIO_SERVER_PORT: int = _get_int('GRADIO_SERVER_PORT', 7860, min_value=1)  # Gradio服务器端口
GRADIO_SHARE: bool = _get_bool('GRADIO_SHARE', False)  # 是否创建公开分享链接
REQUESTS_PER_MINUTE: int = _get_int('REQUESTS_PER_MINUTE', 20, min_value=0)  # 每个浏览器会话每分钟请求上限

# 基础用户上下文（为后续登录态 / RBAC / 多租户做资源归属铺垫）
DEFAULT_USERNAME: str = os.getenv('DEFAULT_USERNAME', 'local-user')
DEFAULT_USER_ID: str = os.getenv('DEFAULT_USER_ID', 'local-user')

# 鉴权配置（设置 GRADIO_AUTH_USER 与 GRADIO_AUTH_PASSWORD 后启用登录）
GRADIO_AUTH_USER: str = os.getenv('GRADIO_AUTH_USER', '')
GRADIO_AUTH_PASSWORD: str = os.getenv('GRADIO_AUTH_PASSWORD', '')
