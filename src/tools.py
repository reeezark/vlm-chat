"""
工具调用模块（P0-4）
提供可被模型通过 Function Calling 调用的工具，目前实现联网搜索。
工具以 OpenAI tools 规范暴露，并提供统一的本地执行入口。
"""
import json
from typing import Callable, Optional

from .config import (
    WEB_SEARCH_MAX_RESULTS, WEB_SEARCH_TIMEOUT,
    WEB_SEARCH_MAX_QUERY_CHARS, WEB_SEARCH_MAX_RESULT_CHARS,
)
from .logger import get_api_logger

logger = get_api_logger()

_AUDIT_HOOK: Optional[Callable[[str, bool, str], None]] = None


def set_tool_audit_hook(hook: Optional[Callable[[str, bool, str], None]]) -> None:
    """注册工具调用审计回调。回调参数为 (tool_name, success, detail)。"""
    global _AUDIT_HOOK
    _AUDIT_HOOK = hook


def _emit_tool_audit(name: str, success: bool, detail: str) -> None:
    if _AUDIT_HOOK is None:
        return
    try:
        _AUDIT_HOOK(name, success, detail)
    except Exception as e:
        logger.warning(f"工具审计回调失败: {e}")


# ── 工具的 OpenAI 规范定义 ──────────────────────────────────────
TOOLS_SPEC: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "当需要获取实时信息、最新事件、或模型不确定的事实时，使用此工具联网搜索。返回若干条标题与摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def web_search(query: str, max_results: Optional[int] = None) -> str:
    """
    使用 duckduckgo-search 库进行联网搜索（无需密钥，返回真实搜索结果）。

    参数:
        query: 搜索关键词
        max_results: 返回结果数上限

    返回:
        搜索结果的文本摘要；失败时返回错误说明
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return "联网搜索失败: 请先安装 ddgs 包（pip install ddgs）"

    max_results = max_results or WEB_SEARCH_MAX_RESULTS
    query = (query or "").strip()
    if not query:
        return "联网搜索失败: 搜索关键词不能为空"
    if len(query) > WEB_SEARCH_MAX_QUERY_CHARS:
        query = query[:WEB_SEARCH_MAX_QUERY_CHARS]

    try:
        results: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body  = r.get("body", "")
                if title or body:
                    results.append(f"【{title}】{body}")
    except Exception as e:
        logger.warning(f"联网搜索失败: {e}")
        return f"联网搜索失败: {e}"

    if not results:
        return f"未找到关于\"{query}\"的搜索结果。"
    text = "\n".join(f"- {r}" for r in results)
    if len(text) > WEB_SEARCH_MAX_RESULT_CHARS:
        text = text[:WEB_SEARCH_MAX_RESULT_CHARS] + "\n…（搜索结果过长，已截断）"
    return text


# 工具名 -> 可调用对象
TOOL_REGISTRY = {
    "web_search": web_search,
}


def execute_tool_call(name: str, arguments: str) -> str:
    """
    执行模型请求的工具调用。

    参数:
        name: 工具名称
        arguments: JSON 字符串形式的参数

    返回:
        工具执行结果文本
    """
    func = TOOL_REGISTRY.get(name)
    if func is None:
        result = f"未知工具: {name}"
        _emit_tool_audit(name, False, result)
        return result
    try:
        kwargs = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        kwargs = {}
    try:
        result = func(**kwargs)
        success = not result.startswith("联网搜索失败") and not result.startswith("工具")
        _emit_tool_audit(name, success, result[:300])
        return result
    except Exception as e:
        logger.error(f"工具 {name} 执行失败: {e}")
        result = f"工具 {name} 执行失败: {e}"
        _emit_tool_audit(name, False, result)
        return result
