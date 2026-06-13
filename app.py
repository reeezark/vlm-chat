"""
主应用入口
基于Gradio构建的智能图文问答助手Web界面
ChatGPT风格：左侧会话列表 + 中间聊天区
"""
import os
import sys
import logging
import time

os.environ["OPENAI_LOG"] = "error"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
logging.disable(logging.DEBUG)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from src.api_client import VLMAPIClient
from src.chat_manager import ChatManager
from src.image_processor import ImageProcessor
from src.metrics import MetricsCollector
from src.rag import RagManager
from src.tools import set_tool_audit_hook
from src.config import (
    GRADIO_SERVER_NAME, GRADIO_SERVER_PORT, GRADIO_SHARE,
    GRADIO_AUTH_USER, GRADIO_AUTH_PASSWORD,
    PROVIDERS, DEFAULT_PROVIDER, DEFAULT_SYSTEM_PROMPT, ENABLE_TOOLS,
    MAX_IMAGES_PER_MESSAGE, APP_ENV, REQUESTS_PER_MINUTE,
    SESSION_DB_DIR, ENABLE_RAG, RAG_DEFAULT_COLLECTION, RAG_TOP_K,
    DEFAULT_USERNAME, DEFAULT_USER_ID,
)

# ── 主题（Claude 风格：温润米白 + 陶土橙强调色） ──────────────────
LIGHT_THEME = gr.themes.Base(
    neutral_hue=gr.themes.colors.Color(
        c50="#faf9f5", c100="#f3f1ea", c200="#e8e5dc", c300="#d8d4c8",
        c400="#b3ad9e", c500="#82817b", c600="#5c5b55", c700="#42413c",
        c800="#2b2a27", c900="#1f1e1d", c950="#141312",
    ),
    primary_hue=gr.themes.colors.orange,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
)

# ── JavaScript注入样式（最高优先级，Claude 风格 + 响应式） ─────────
INJECT_CSS_JS = """
() => {
    const css = `
    /* ── 设计变量 ──────────────────── */
    :root {
        --bg: #faf9f5;
        --bg-grad-1: #faf9f5;
        --bg-grad-2: #f4f1ea;
        --sidebar-bg: #f3f1ea;
        --surface: #ffffff;
        --border: #e8e5dc;
        --border-strong: #d8d4c8;
        --text: #2b2a27;
        --text-muted: #82817b;
        --accent: #cc785c;
        --accent-hover: #b8654b;
        --accent-soft: rgba(204,120,92,0.10);
        --shadow-sm: 0 1px 2px rgba(40,38,33,0.04), 0 1px 3px rgba(40,38,33,0.06);
        --shadow-md: 0 2px 8px rgba(40,38,33,0.06), 0 4px 16px rgba(40,38,33,0.05);
        --radius: 14px;
        --radius-lg: 18px;
        --ease: cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ── 全局 ──────────────────────── */
    html, body, .gradio-container {
        background: linear-gradient(160deg, var(--bg-grad-1) 0%, var(--bg-grad-2) 100%) !important;
        background-attachment: fixed !important;
        margin: 0 !important; padding: 0 !important;
        max-width: 100% !important;
        color: var(--text) !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    footer { display: none !important; }
    .gradio-container, .gradio-container * { color: var(--text); }
    *, *::before, *::after { -webkit-tap-highlight-color: transparent; }

    /* 进入动画 */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ── 侧边栏 ────────────────────── */
    #sidebar {
        background: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border) !important;
        padding: 28px 20px !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 18px !important;
        overflow-y: auto !important;
        height: 100vh !important;
    }
    #sidebar * { background: transparent; }
    #sidebar h3, #sidebar .sidebar-title {
        color: var(--text) !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        letter-spacing: -0.4px !important;
        margin: 0 0 4px !important;
    }
    #sidebar .new-chat-btn,
    #sidebar button.new-chat-btn {
        background: var(--accent) !important;
        color: #fff !important;
        border: 1px solid var(--accent) !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        box-shadow: var(--shadow-sm) !important;
        transition: transform 0.15s var(--ease), background 0.15s var(--ease), box-shadow 0.15s var(--ease) !important;
    }
    #sidebar .new-chat-btn:hover { background: var(--accent-hover) !important; border-color: var(--accent-hover) !important; transform: translateY(-1px) !important; box-shadow: var(--shadow-md) !important; }
    #sidebar .new-chat-btn:active { transform: translateY(0) !important; }

    /* 表单标签 */
    #sidebar label { color: var(--text-muted) !important; font-size: 11px !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.7px !important; }

    /* 下拉框 / 文本框 / 复选框 */
    #sidebar .session-dropdown input,
    #sidebar .session-dropdown textarea,
    #sidebar .session-dropdown .wrap {
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 12px !important;
        box-shadow: var(--shadow-sm) !important;
        transition: border-color 0.15s var(--ease), box-shadow 0.15s var(--ease) !important;
    }
    #sidebar .session-dropdown input:focus,
    #sidebar .session-dropdown textarea:focus,
    #sidebar .session-dropdown .wrap:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-soft) !important;
    }
    #sidebar input[type="checkbox"] { accent-color: var(--accent) !important; }

    /* 侧边栏底部 */
    .sidebar-footer {
        margin-top: auto !important;
        padding-top: 18px !important;
        border-top: 1px solid var(--border) !important;
    }
    .danger-btn, button.danger-btn {
        background: transparent !important;
        border: 1px solid #e6cfc6 !important;
        color: #b8654b !important;
        border-radius: 10px !important;
        font-size: 12px !important;
        padding: 9px 14px !important;
        transition: all 0.15s var(--ease) !important;
    }
    .danger-btn:hover { background: #f8eee9 !important; border-color: #d9b3a6 !important; }

    /* ── 主聊天区 ───────────────────── */
    #main-area {
        background: transparent !important;
        display: flex !important;
        flex-direction: column !important;
        height: 100vh !important;
        padding: 0 !important;
    }
    #top-bar {
        padding: 20px 36px !important;
        border-bottom: 1px solid var(--border) !important;
        flex-shrink: 0 !important;
        background: rgba(250,249,245,0.72) !important;
        backdrop-filter: saturate(180%) blur(12px) !important;
        -webkit-backdrop-filter: saturate(180%) blur(12px) !important;
    }
    #top-bar p { color: var(--text) !important; font-size: 15px !important; font-weight: 600 !important; letter-spacing: -0.2px !important; margin: 0 !important; }

    /* 聊天消息 */
    #chat-area {
        flex: 1 !important;
        min-height: 0 !important;
        overflow-y: auto !important;
        background: transparent !important;
        padding: 24px max(36px, calc((100% - 820px) / 2)) !important;
    }
    #chat-area * { background: transparent; }
    #chat-area .user .message-bubble-border,
    #chat-area .user > div > div {
        background: var(--surface) !important;
        border-radius: var(--radius-lg) !important;
        border: 1px solid var(--border) !important;
        padding: 14px 20px !important;
        box-shadow: var(--shadow-sm) !important;
        animation: fadeInUp 0.3s var(--ease) !important;
    }
    #chat-area .bot .message-bubble-border,
    #chat-area .bot > div > div {
        background: transparent !important;
        border: none !important;
        padding: 14px 20px !important;
        animation: fadeInUp 0.3s var(--ease) !important;
    }
    #chat-area .message, #chat-area p, #chat-area span, #chat-area div, #chat-area li {
        color: var(--text) !important;
    }
    #chat-area .message { font-size: 15px !important; line-height: 1.75 !important; letter-spacing: 0.1px !important; }
    #chat-area pre, #chat-area code {
        background: #f3f1ea !important;
        border-radius: 10px !important;
        font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace !important;
    }
    #chat-area pre { padding: 14px 16px !important; border: 1px solid var(--border) !important; overflow-x: auto !important; }
    #chat-area img { border-radius: 12px !important; max-width: 320px !important; max-height: 320px !important; box-shadow: var(--shadow-sm) !important; }
    #chat-area .avatar-container { display: none !important; }

    /* ── 输入区 ─────────────────────── */
    #input-box {
        padding: 16px max(36px, calc((100% - 820px) / 2)) 28px !important;
        border-top: 1px solid var(--border) !important;
        flex-shrink: 0 !important;
        background: transparent !important;
    }
    #input-box .container {
        background: var(--surface) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: var(--radius-lg) !important;
        padding: 8px 12px !important;
        box-shadow: var(--shadow-sm) !important;
        transition: border-color 0.2s var(--ease), box-shadow 0.2s var(--ease) !important;
    }
    #input-box .container:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow-md) !important;
    }
    #input-box textarea, #input-box input {
        background: transparent !important;
        color: var(--text) !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        border: none !important;
    }
    #input-box textarea::placeholder, #input-box input::placeholder { color: var(--text-muted) !important; }
    #input-box button { border-radius: 10px !important; }
    .input-actions { padding: 10px 0 0 !important; gap: 8px !important; }
    .clear-btn, button.clear-btn {
        background: var(--surface) !important;
        border: 1px solid var(--border-strong) !important;
        color: var(--text-muted) !important;
        border-radius: 10px !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        padding: 7px 16px !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.15s var(--ease) !important;
    }
    .clear-btn:hover { background: var(--accent-soft) !important; color: var(--accent-hover) !important; border-color: #e0c4b9 !important; transform: translateY(-1px) !important; }
    .clear-btn:active { transform: translateY(0) !important; }

    /* ── 链接 / 排版 ────────────────── */
    a { color: var(--accent) !important; text-decoration: none !important; }
    a:hover { text-decoration: underline !important; }
    .prose { color: var(--text) !important; }

    /* ── 滚动条 ────────────────────── */
    #chat-area::-webkit-scrollbar, #sidebar::-webkit-scrollbar { width: 8px; }
    #chat-area::-webkit-scrollbar-thumb, #sidebar::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }
    #chat-area::-webkit-scrollbar-thumb:hover, #sidebar::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    #chat-area, #sidebar { scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent; }

    /* ── 响应式：平板 ──────────────── */
    @media (max-width: 1024px) {
        #chat-area { padding: 20px 24px !important; }
        #input-box { padding: 14px 24px 24px !important; }
        #top-bar { padding: 18px 24px !important; }
    }

    /* ── 响应式：移动端 ────────────── */
    @media (max-width: 768px) {
        #app-row { flex-direction: column !important; flex-wrap: nowrap !important; }
        #sidebar {
            height: auto !important;
            max-height: 42vh !important;
            min-width: 100% !important;
            width: 100% !important;
            border-right: none !important;
            border-bottom: 1px solid var(--border) !important;
            padding: 18px 16px !important;
            gap: 12px !important;
        }
        #main-area { height: 58vh !important; }
        #chat-area { padding: 16px 16px !important; }
        #chat-area .message { font-size: 14px !important; }
        #chat-area img { max-width: 80vw !important; }
        #input-box { padding: 12px 16px 20px !important; }
        #top-bar { padding: 14px 16px !important; }
        .input-actions { flex-wrap: wrap !important; }
    }
    @media (max-width: 480px) {
        #sidebar { max-height: 46vh !important; }
        #main-area { height: 54vh !important; }
        .clear-btn { padding: 7px 12px !important; font-size: 11px !important; }
    }
    `;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
}
"""


class VLMChatAssistant:
    """VLM聊天助手应用"""

    def __init__(self):
        self.api_client = VLMAPIClient(allow_missing_key=True)
        self._session_api_clients: dict[str, VLMAPIClient] = {}
        self.chat_manager = ChatManager()
        self.image_processor = ImageProcessor()
        self.metrics = MetricsCollector()
        self.rag_manager = RagManager(os.path.join(SESSION_DB_DIR, "sessions.db")) if ENABLE_RAG else None
        self.user_id = self.chat_manager.upsert_user(DEFAULT_USERNAME, user_id=DEFAULT_USER_ID)
        self._rate_buckets: dict[str, list[float]] = {}
        set_tool_audit_hook(self._record_tool_audit)

        # 启动时清理过期会话；每个浏览器会话在 init_browser_session 中独立创建
        self.chat_manager.cleanup_expired_sessions()
        self.image_processor.cleanup_old_uploads()

    def _record_tool_audit(self, name: str, success: bool, detail: str) -> None:
        """记录工具调用指标和审计；工具层不持有会话上下文，因此 session_id 为空。"""
        self.metrics.inc("tool_calls_total")
        if not success:
            self.metrics.inc("tool_errors_total")
        self.chat_manager.add_audit_log(
            action="tool_call",
            resource_type="tool",
            resource_id=name,
            user_id=self.user_id,
            success=success,
            error_code=None if success else "tool_error",
            detail=detail[:300] if detail else None,
        )

    def _session_choices(self) -> list[str]:
        return [s["name"] for s in self.chat_manager.get_all_sessions(user_id=self.user_id)]

    def _name_of(self, session_id: str) -> str:
        s = self.chat_manager.get_session(session_id, user_id=self.user_id) if session_id else None
        return s["name"] if s else ""

    def _ensure_session(self, session_id):
        """确保 session_id 有效，否则回退到最新会话或新建一个"""
        if session_id and self.chat_manager.get_session(session_id, user_id=self.user_id):
            return session_id
        sessions = self.chat_manager.get_all_sessions(user_id=self.user_id)
        if sessions:
            return sessions[0]["session_id"]
        return self.chat_manager.create_session(user_id=self.user_id)

    def _check_rate_limit(self, session_id: str) -> tuple[bool, str]:
        """按浏览器会话做轻量限流，避免公开部署时被单会话刷爆模型接口"""
        if REQUESTS_PER_MINUTE <= 0:
            return True, ""
        now = time.time()
        window_start = now - 60
        bucket = [t for t in self._rate_buckets.get(session_id, []) if t >= window_start]
        if len(bucket) >= REQUESTS_PER_MINUTE:
            self._rate_buckets[session_id] = bucket
            self.metrics.inc("rate_limited_total")
            self.chat_manager.add_audit_log(
                action="rate_limited",
                session_id=session_id,
                resource_type="session",
                resource_id=session_id,
                user_id=self.user_id,
                success=False,
                error_code="rate_limited",
            )
            return False, f"请求过于频繁，请稍后再试（每分钟最多 {REQUESTS_PER_MINUTE} 次）。"
        bucket.append(now)
        self._rate_buckets[session_id] = bucket
        return True, ""

    def _api_client_for_session(self, session_id: str) -> VLMAPIClient:
        """为每个浏览器会话维护独立模型客户端，避免自定义 API 配置互相覆盖。"""
        client = self._session_api_clients.get(session_id)
        if client is None:
            client = VLMAPIClient(allow_missing_key=True)
            self._session_api_clients[session_id] = client
        return client

    def _ingest_rag_document(self, session_id: str, filename: str, text: str) -> None:
        """将解析后的文档文本写入轻量知识库。"""
        if not self.rag_manager or not text:
            return
        try:
            document_id, chunk_count = self.rag_manager.ingest_text(
                RAG_DEFAULT_COLLECTION,
                filename,
                text,
                content_type="application/pdf",
                owner_user_id=self.user_id,
            )
            if chunk_count:
                self.metrics.inc("rag_documents_total")
                self.metrics.inc("rag_chunks_total", chunk_count)
                self.chat_manager.add_audit_log(
                    action="rag_ingest_document",
                    session_id=session_id,
                    resource_type="rag_document",
                    resource_id=document_id,
                    user_id=self.user_id,
                    success=True,
                    detail=f"filename={filename};chunks={chunk_count}",
                )
        except Exception as e:
            self.metrics.inc("rag_ingest_errors_total")
            self.chat_manager.add_audit_log(
                action="rag_ingest_document",
                session_id=session_id,
                resource_type="rag_document",
                resource_id=filename,
                user_id=self.user_id,
                success=False,
                error_code="rag_ingest_failed",
                detail=str(e)[:300],
            )

    def _build_rag_context(self, question: str) -> tuple[str, str]:
        """基于问题检索知识库片段，生成模型上下文和用户可见引用。"""
        if not self.rag_manager or not question:
            return "", ""
        results = self.rag_manager.semantic_search(question, limit=RAG_TOP_K, owner_user_id=self.user_id)
        if not results:
            return "", ""
        self.metrics.inc("rag_retrievals_total")
        blocks = []
        for idx, item in enumerate(results, start=1):
            filename = item.get("filename") or "unknown"
            content = (item.get("content") or "").strip()
            blocks.append(f"[{idx}] 来源: {filename}\n{content}")
        context = "\n\n【知识库相关片段】\n" + "\n\n".join(blocks)
        references = self.rag_manager.format_references(results)
        return context, references

    def _rag_documents(self) -> list[dict]:
        if not self.rag_manager:
            return []
        return self.rag_manager.list_documents(RAG_DEFAULT_COLLECTION, owner_user_id=self.user_id)

    def _rag_document_choices(self) -> list[tuple[str, str]]:
        choices = []
        for doc in self._rag_documents():
            label = f"{doc['filename']} ({doc['chunk_count']} 段)"
            choices.append((label, doc["document_id"]))
        return choices

    def _rag_summary(self) -> str:
        docs = self._rag_documents()
        if not self.rag_manager:
            return "RAG 未启用。"
        if not docs:
            return "默认知识库暂无文档。上传 PDF 后会自动入库。"
        total_chunks = sum(int(d.get("chunk_count") or 0) for d in docs)
        return f"默认知识库：{len(docs)} 个文档，{total_chunks} 个切片。"

    def refresh_knowledge_base(self):
        """刷新知识库文档列表。"""
        choices = self._rag_document_choices()
        value = choices[0][1] if choices else None
        return gr.Dropdown(choices=choices, value=value), self._rag_summary(), ""

    def show_rag_chunks(self, document_id):
        """查看选中文档的切片摘要。"""
        if not self.rag_manager or not document_id:
            return "请选择一个已入库文档。"
        chunks = self.rag_manager.list_chunks(document_id, limit=8, owner_user_id=self.user_id)
        if not chunks:
            return "该文档暂无切片。"
        lines = ["**文档切片预览**"]
        for chunk in chunks:
            content = " ".join((chunk.get("content") or "").split())
            if len(content) > 160:
                content = content[:160].rstrip() + "..."
            lines.append(f"- 第 {chunk['chunk_index']} 段：{content}")
        return "\n".join(lines)

    def delete_rag_document(self, document_id):
        """删除选中的知识库文档。"""
        if not self.rag_manager or not document_id:
            return gr.Dropdown(choices=self._rag_document_choices(), value=None), self._rag_summary(), "请选择要删除的文档。"
        ok = self.rag_manager.delete_document(document_id, owner_user_id=self.user_id)
        self.chat_manager.add_audit_log(
            action="rag_delete_document",
            resource_type="rag_document",
            resource_id=document_id,
            user_id=self.user_id,
            success=ok,
        )
        choices = self._rag_document_choices()
        value = choices[0][1] if choices else None
        status = "已删除选中文档。" if ok else "未找到选中文档。"
        return gr.Dropdown(choices=choices, value=value), self._rag_summary(), status

    def clear_knowledge_base(self):
        """清空默认知识库。"""
        if not self.rag_manager:
            return gr.Dropdown(choices=[], value=None), "RAG 未启用。", "RAG 未启用。"
        count = self.rag_manager.clear_collection(RAG_DEFAULT_COLLECTION, owner_user_id=self.user_id)
        self.chat_manager.add_audit_log(
            action="rag_clear_collection",
            resource_type="rag_collection",
            resource_id=RAG_DEFAULT_COLLECTION,
            user_id=self.user_id,
            success=True,
            detail=f"documents={count}",
        )
        return gr.Dropdown(choices=[], value=None), self._rag_summary(), f"已清空默认知识库，删除 {count} 个文档。"

    def _apply_model_config(
        self,
        session_id: str,
        provider: str,
        model: str,
        use_custom_api: bool,
        custom_base_url: str,
        custom_api_key: str,
        custom_model: str,
    ) -> tuple[bool, str, str, str, VLMAPIClient | None]:
        """应用模型配置到当前会话客户端，返回 (成功, 错误消息, 实际 provider, 实际 model, client)。"""
        api_client = self._api_client_for_session(session_id)
        if use_custom_api:
            actual_provider = "custom"
            actual_model = (custom_model or "").strip()
            try:
                api_client.switch_model(
                    provider="custom",
                    model_name=actual_model,
                    base_url=(custom_base_url or "").strip(),
                    api_key=(custom_api_key or "").strip(),
                )
                return True, "", actual_provider, actual_model, api_client
            except Exception as e:
                return False, f"自定义模型配置失败: {str(e)}", actual_provider, actual_model, None

        try:
            api_client.switch_model(provider=provider, model_name=model)
            return True, "", provider, model, api_client
        except Exception as e:
            return False, f"模型切换失败: {str(e)}", provider, model, None

    def process_query(
        self,
        multimodal_input,
        chatbot_history,
        session_id,
        provider,
        model,
        system_prompt,
        use_tools,
        use_custom_api,
        custom_base_url,
        custom_api_key,
        custom_model,
    ):
        """流式处理用户输入（P0-1/P0-3/P0-4 + P1-5 多图/PDF）。作为生成器逐步产出聊天记录。"""
        session_id = self._ensure_session(session_id)
        request_started_at = time.time()
        self.metrics.inc("chat_requests_total")
        chatbot_history = chatbot_history or []
        allowed, limit_msg = self._check_rate_limit(session_id)
        if not allowed:
            chatbot_history.append({"role": "assistant", "content": limit_msg})
            yield chatbot_history, None, session_id
            return
        if multimodal_input is None:
            yield chatbot_history, None, session_id
            return

        question = (multimodal_input.get("text") or "").strip()
        files = multimodal_input.get("files") or []

        # 分离图片与文档（PDF）（P1-5）
        image_files: list[str] = []
        doc_files: list[str] = []
        for f in files:
            if self.image_processor.is_image(f):
                image_files.append(f)
            elif self.image_processor.is_document(f):
                doc_files.append(f)
            else:
                image_files.append(f)  # 默认按图片处理，交给校验拦截

        if not question and not image_files and not doc_files:
            yield chatbot_history, None, session_id
            return

        # 校验并持久化图片（最多 MAX_IMAGES_PER_MESSAGE 张）
        persisted_images: list[str] = []
        if image_files:
            if len(image_files) > MAX_IMAGES_PER_MESSAGE:
                image_files = image_files[:MAX_IMAGES_PER_MESSAGE]
            for img in image_files:
                is_valid, msgs = self.image_processor.validate_image(img)
                if not is_valid:
                    self.metrics.inc("image_validation_errors_total")
                    self.chat_manager.add_audit_log(
                        action="upload_image",
                        session_id=session_id,
                        resource_type="image",
                        resource_id=os.path.basename(img),
                        user_id=self.user_id,
                        success=False,
                        error_code="image_validation_failed",
                    )
                    chatbot_history.append({"role": "user", "content": question or "上传图片"})
                    chatbot_history.append({"role": "assistant", "content": "图片验证失败: " + "; ".join(msgs)})
                    yield chatbot_history, None, session_id
                    return
                persisted = self.image_processor.persist_upload(img)
                persisted_images.append(persisted)
                self.metrics.inc("uploaded_images_total")
                self.chat_manager.add_audit_log(
                    action="upload_image",
                    session_id=session_id,
                    resource_type="image",
                    resource_id=os.path.basename(persisted),
                    user_id=self.user_id,
                    success=True,
                )

        # 解析文档（PDF）文本并拼接到问题（P1-5）
        doc_text = ""
        for doc in doc_files:
            ok, dmsg = self.image_processor.validate_document(doc)
            if not ok:
                self.metrics.inc("document_validation_errors_total")
                self.chat_manager.add_audit_log(
                    action="parse_document",
                    session_id=session_id,
                    resource_type="document",
                    resource_id=os.path.basename(doc),
                    user_id=self.user_id,
                    success=False,
                    error_code="document_validation_failed",
                )
                chatbot_history.append({"role": "user", "content": question or "上传文档"})
                chatbot_history.append({"role": "assistant", "content": "文档验证失败: " + dmsg})
                yield chatbot_history, None, session_id
                return
            ok, extracted = self.image_processor.extract_pdf_text(doc)
            if not ok:
                self.metrics.inc("document_parse_errors_total")
                self.chat_manager.add_audit_log(
                    action="parse_document",
                    session_id=session_id,
                    resource_type="document",
                    resource_id=os.path.basename(doc),
                    user_id=self.user_id,
                    success=False,
                    error_code="document_parse_failed",
                )
                chatbot_history.append({"role": "user", "content": question or "上传文档"})
                chatbot_history.append({"role": "assistant", "content": extracted})
                yield chatbot_history, None, session_id
                return
            doc_name = os.path.basename(doc)
            doc_text += f"\n\n【文档 {doc_name} 内容】\n{extracted}"
            self._ingest_rag_document(session_id, doc_name, extracted)
            self.metrics.inc("parsed_documents_total")
            self.chat_manager.add_audit_log(
                action="parse_document",
                session_id=session_id,
                resource_type="document",
                resource_id=doc_name,
                user_id=self.user_id,
                success=True,
                detail=f"chars={len(extracted)}",
            )

        if not question and (persisted_images or doc_text):
            question = "请描述这张图片的内容" if persisted_images else "请总结这份文档的内容"

        # 送入模型的问题（含文档文本）；展示给用户的仍是原始问题
        rag_context, rag_references = self._build_rag_context(question)
        api_question = question + (("\n" + doc_text) if doc_text else "") + rag_context

        # 当前消息图片：单张退化为字符串，多张为列表
        current_image = None
        if persisted_images:
            current_image = persisted_images if len(persisted_images) > 1 else persisted_images[0]

        # 应用 Provider / 模型 / System Prompt 设置
        actual_provider = "custom" if use_custom_api else provider
        actual_model = (custom_model or "").strip() if use_custom_api else model
        self.chat_manager.set_model(session_id, actual_provider, actual_model)
        if system_prompt is not None:
            self.chat_manager.set_system_prompt(session_id, system_prompt)
        ok, err_msg, actual_provider, actual_model, api_client = self._apply_model_config(
            session_id,
            provider,
            model,
            use_custom_api,
            custom_base_url,
            custom_api_key,
            custom_model,
        )
        if not ok:
            chatbot_history.append({"role": "user", "content": question or "上传图片"})
            chatbot_history.append({"role": "assistant", "content": err_msg})
            yield chatbot_history, None, session_id
            return

        # 仅当本条没有图片时才复用会话历史图片（避免文档/纯文本提问误带旧图）
        use_image = current_image
        history = self.chat_manager.get_history(session_id, format_for_api=True)
        sys_prompt = system_prompt or self.chat_manager.get_system_prompt(session_id)

        # 先渲染用户消息（含多图）与占位的助手气泡
        if persisted_images:
            user_content = [{"path": p} for p in persisted_images]
            if question:
                user_content.append(question)
        else:
            user_content = question
        chatbot_history.append({"role": "user", "content": user_content})
        chatbot_history.append({"role": "assistant", "content": "▌"})
        yield chatbot_history, None, session_id

        # 流式产出回答
        final_answer = ""
        try:
            for partial in api_client.stream_api(
                image_path=use_image,
                question=api_question,
                history=history,
                system_prompt=sys_prompt,
                use_tools=use_tools,
            ):
                final_answer = partial
                chatbot_history[-1] = {"role": "assistant", "content": partial + " ▌"}
                yield chatbot_history, None, session_id
            if rag_references:
                final_answer = final_answer + rag_references
            chatbot_history[-1] = {"role": "assistant", "content": final_answer}
        except Exception as e:
            self.metrics.inc("chat_errors_total")
            self.chat_manager.add_audit_log(
                action="chat",
                session_id=session_id,
                resource_type="session",
                resource_id=session_id,
                user_id=self.user_id,
                provider=actual_provider,
                model=actual_model,
                success=False,
                error_code="api_error",
            )
            chatbot_history[-1] = {"role": "assistant", "content": f"API调用失败: {str(e)}"}
            yield chatbot_history, None, session_id
            return

        # 成功后统一落库，避免失败时状态不一致
        self.chat_manager.add_message(session_id, "user", question, image_path=current_image)
        self.chat_manager.add_message(session_id, "assistant", final_answer)
        self.metrics.inc("chat_success_total")
        self.metrics.observe("chat_request_duration", time.time() - request_started_at)
        self.chat_manager.add_audit_log(
            action="chat",
            session_id=session_id,
            resource_type="session",
            resource_id=session_id,
            user_id=self.user_id,
            provider=actual_provider,
            model=actual_model,
            success=True,
        )
        yield chatbot_history, None, session_id

    def regenerate(
        self,
        chatbot_history,
        session_id,
        provider,
        model,
        system_prompt,
        use_tools,
        use_custom_api,
        custom_base_url,
        custom_api_key,
        custom_model,
    ):
        """重新生成最近一轮回答（P1-7）。回退最近一轮后用相同的用户输入重新流式生成。"""
        session_id = self._ensure_session(session_id)
        chatbot_history = chatbot_history or []
        allowed, limit_msg = self._check_rate_limit(session_id)
        if not allowed:
            chatbot_history.append({"role": "assistant", "content": limit_msg})
            yield chatbot_history, session_id
            return

        last_user = self.chat_manager.pop_last_exchange(session_id)
        if not last_user:
            yield chatbot_history, session_id
            return

        question = last_user.get("text") or ""
        current_image = last_user.get("image")

        # 同步回退 UI 中的最近一轮（最后的 assistant + user 气泡）
        if chatbot_history and chatbot_history[-1]["role"] == "assistant":
            chatbot_history.pop()
        if chatbot_history and chatbot_history[-1]["role"] == "user":
            chatbot_history.pop()

        actual_provider = "custom" if use_custom_api else provider
        actual_model = (custom_model or "").strip() if use_custom_api else model
        self.chat_manager.set_model(session_id, actual_provider, actual_model)
        if system_prompt is not None:
            self.chat_manager.set_system_prompt(session_id, system_prompt)
        ok, err_msg, _, _, api_client = self._apply_model_config(
            session_id,
            provider,
            model,
            use_custom_api,
            custom_base_url,
            custom_api_key,
            custom_model,
        )
        if not ok:
            chatbot_history.append({"role": "assistant", "content": err_msg})
            yield chatbot_history, session_id
            return

        history = self.chat_manager.get_history(session_id, format_for_api=True)
        sys_prompt = system_prompt or self.chat_manager.get_system_prompt(session_id)

        # 重新渲染用户消息（含多图）与占位的助手气泡
        if current_image:
            images = current_image if isinstance(current_image, list) else [current_image]
            user_content = [{"path": p} for p in images]
            if question:
                user_content.append(question)
        else:
            user_content = question
        chatbot_history.append({"role": "user", "content": user_content})
        chatbot_history.append({"role": "assistant", "content": "▌"})
        yield chatbot_history, session_id

        final_answer = ""
        try:
            for partial in api_client.stream_api(
                image_path=current_image,
                question=question,
                history=history,
                system_prompt=sys_prompt,
                use_tools=use_tools,
            ):
                final_answer = partial
                chatbot_history[-1] = {"role": "assistant", "content": partial + " ▌"}
                yield chatbot_history, session_id
            chatbot_history[-1] = {"role": "assistant", "content": final_answer}
        except Exception as e:
            chatbot_history[-1] = {"role": "assistant", "content": f"API调用失败: {str(e)}"}
            yield chatbot_history, session_id
            return

        self.chat_manager.add_message(session_id, "user", question, image_path=current_image)
        self.chat_manager.add_message(session_id, "assistant", final_answer)
        yield chatbot_history, session_id

    def create_new_session(self):
        session_id = self.chat_manager.create_session(user_id=self.user_id)
        return self.chat_manager.format_for_chatbot(session_id), None, gr.Dropdown(
            choices=self._session_choices(), value=self._name_of(session_id)
        ), session_id

    def switch_session(self, session_name, session_id):
        if not session_name:
            return [], None, gr.Dropdown(choices=self._session_choices()), session_id, DEFAULT_SYSTEM_PROMPT
        for s in self.chat_manager.get_all_sessions(user_id=self.user_id):
            if s["name"] == session_name:
                session_id = s["session_id"]
                break
        return (
            self.chat_manager.format_for_chatbot(session_id),
            self.chat_manager.get_current_image(session_id),
            gr.Dropdown(choices=self._session_choices(), value=session_name),
            session_id,
            self.chat_manager.get_system_prompt(session_id),
        )

    def delete_session(self, session_name, session_id):
        if not session_name:
            return [], None, gr.Dropdown(choices=self._session_choices()), session_id
        for s in self.chat_manager.get_all_sessions(user_id=self.user_id):
            if s["name"] == session_name:
                deleted_session_id = s["session_id"]
                self.chat_manager.delete_session(deleted_session_id, user_id=self.user_id)
                self._session_api_clients.pop(deleted_session_id, None)
                self._rate_buckets.pop(deleted_session_id, None)
                break
        session_id = self._ensure_session(None)
        return self.chat_manager.format_for_chatbot(session_id), self.chat_manager.get_current_image(session_id), gr.Dropdown(
            choices=self._session_choices(), value=self._name_of(session_id)
        ), session_id

    def clear_chat(self, session_id):
        session_id = self._ensure_session(session_id)
        self.chat_manager.clear_history(session_id)
        return [], None, session_id

    @staticmethod
    def update_model_choices(provider):
        """根据 Provider 联动模型下拉框（P0-3）"""
        models = PROVIDERS.get(provider, {}).get("models", [])
        value = models[0] if models else None
        return gr.Dropdown(choices=models, value=value)

    def init_browser_session(self):
        """每个浏览器加载时为其分配独立会话，避免多用户共享同一全局会话"""
        session_id = self.chat_manager.create_session(user_id=self.user_id)
        return (
            self.chat_manager.format_for_chatbot(session_id),
            gr.Dropdown(choices=self._session_choices(), value=self._name_of(session_id)),
            session_id,
        )

    def create_interface(self):
        with gr.Blocks(title="VLM Chat", fill_height=True, theme=LIGHT_THEME, js=INJECT_CSS_JS) as demo:
            # 每个浏览器独立的会话标识（多用户隔离）
            session_state = gr.State(None)
            with gr.Row(elem_id="app-row", equal_height=True):
                # ═══ 侧边栏 ═══
                with gr.Column(min_width=260, scale=0, elem_id="sidebar"):
                    gr.HTML('<div style="color:#e4e4e7;font-size:20px;font-weight:700;letter-spacing:-0.5px;padding:0 2px;">VLM Chat</div>')
                    new_chat_btn = gr.Button("+ 新建对话", elem_classes="new-chat-btn", size="sm")
                    session_dropdown = gr.Dropdown(
                        choices=self._session_choices(),
                        label="历史对话",
                        interactive=True,
                        elem_classes="session-dropdown",
                    )

                    # ── 模型 / Provider 设置（P0-3）──
                    _default_models = PROVIDERS.get(DEFAULT_PROVIDER, {}).get("models", [])
                    provider_dropdown = gr.Dropdown(
                        choices=[(conf["label"], key) for key, conf in PROVIDERS.items()],
                        value=DEFAULT_PROVIDER,
                        label="模型提供方",
                        interactive=True,
                        elem_classes="session-dropdown",
                    )
                    model_dropdown = gr.Dropdown(
                        choices=_default_models,
                        value=_default_models[0] if _default_models else None,
                        label="模型",
                        interactive=True,
                        elem_classes="session-dropdown",
                    )

                    with gr.Accordion("自定义模型 API", open=False):
                        use_custom_api_checkbox = gr.Checkbox(
                            value=False,
                            label="使用自定义 OpenAI 兼容接口",
                            interactive=True,
                        )
                        custom_base_url_textbox = gr.Textbox(
                            value="",
                            label="API 地址",
                            placeholder="例如：https://api.openai.com/v1",
                            interactive=True,
                            elem_classes="session-dropdown",
                        )
                        custom_api_key_textbox = gr.Textbox(
                            value="",
                            label="API Key",
                            placeholder="仅保存在当前运行时，不写入数据库",
                            type="password",
                            interactive=True,
                            elem_classes="session-dropdown",
                        )
                        custom_model_textbox = gr.Textbox(
                            value="",
                            label="模型名称",
                            placeholder="例如：gpt-4o、qwen-vl-plus、your-vlm-model",
                            interactive=True,
                            elem_classes="session-dropdown",
                        )
                        gr.Markdown(
                            "启用后会优先使用这里填写的 Base URL / API Key / 模型名，"
                            "适用于 OpenAI 兼容协议的模型服务。"
                        )

                    # ── System Prompt（P0-4）──
                    system_prompt_textbox = gr.Textbox(
                        value=DEFAULT_SYSTEM_PROMPT,
                        label="系统提示词",
                        lines=3,
                        interactive=True,
                        elem_classes="session-dropdown",
                    )

                    # ── 工具调用 / 联网搜索开关（P0-4）──
                    use_tools_checkbox = gr.Checkbox(
                        value=False,
                        label="启用联网搜索",
                        interactive=ENABLE_TOOLS,
                    )

                    with gr.Accordion("知识库", open=False):
                        kb_summary = gr.Markdown(self._rag_summary())
                        kb_document_dropdown = gr.Dropdown(
                            choices=self._rag_document_choices(),
                            label="已入库文档",
                            interactive=True,
                            elem_classes="session-dropdown",
                        )
                        with gr.Row():
                            kb_refresh_btn = gr.Button("刷新", size="sm", variant="secondary")
                            kb_show_chunks_btn = gr.Button("查看切片", size="sm", variant="secondary")
                        with gr.Row():
                            kb_delete_btn = gr.Button("删除文档", size="sm", variant="secondary")
                            kb_clear_btn = gr.Button("清空知识库", size="sm", variant="secondary", elem_classes="danger-btn")
                        kb_detail = gr.Markdown("上传 PDF 后会自动入库。")

                    with gr.Group(elem_classes="sidebar-footer"):
                        delete_btn = gr.Button("删除当前对话", elem_classes="danger-btn", size="sm", variant="secondary")

                # ═══ 主聊天区 ═══
                with gr.Column(scale=1, min_width=400, elem_id="main-area"):
                    gr.Markdown("**基于 Qwen-VL-Plus 的智能图文问答**", elem_id="top-bar")

                    chatbot = gr.Chatbot(
                        height=500,
                        show_label=False,
                        elem_id="chat-area",
                        placeholder="上传图片或输入问题开始对话…",
                        render_markdown=True,
                        sanitize_html=False,
                        show_copy_button=True,
                        latex_delimiters=[
                            {"left": "$$", "right": "$$", "display": True},
                            {"left": "$", "right": "$", "display": False},
                            {"left": "\\(", "right": "\\)", "display": False},
                            {"left": "\\[", "right": "\\]", "display": True},
                        ],
                    )

                    with gr.Group(elem_id="input-box"):
                        multimodal_input = gr.MultimodalTextbox(
                            file_types=["image", ".pdf"],
                            placeholder="输入问题，或上传图片（可多张）/ PDF 文档…",
                            show_label=False,
                            sources=["upload"],
                            max_plain_text_length=2000,
                        )
                        with gr.Row(elem_classes="input-actions"):
                            regenerate_btn = gr.Button("重新生成", elem_classes="clear-btn", size="sm")
                            stop_btn = gr.Button("停止生成", elem_classes="clear-btn", size="sm")
                            clear_btn = gr.Button("清空对话", elem_classes="clear-btn", size="sm")

            # ── 事件 ───────────────────────────────────
            demo.load(
                fn=self.init_browser_session,
                outputs=[chatbot, session_dropdown, session_state],
            )

            # Provider 切换联动模型下拉框（P0-3）
            provider_dropdown.change(
                fn=self.update_model_choices,
                inputs=[provider_dropdown],
                outputs=[model_dropdown],
            )

            done = multimodal_input.submit(
                fn=self.process_query,
                inputs=[
                    multimodal_input, chatbot, session_state,
                    provider_dropdown, model_dropdown, system_prompt_textbox, use_tools_checkbox,
                    use_custom_api_checkbox, custom_base_url_textbox,
                    custom_api_key_textbox, custom_model_textbox,
                ],
                outputs=[chatbot, multimodal_input, session_state],
            )
            done.then(
                fn=lambda sid: gr.Dropdown(choices=self._session_choices(), value=self._name_of(sid)),
                inputs=[session_state],
                outputs=[session_dropdown],
            )
            done.then(
                fn=self.refresh_knowledge_base,
                outputs=[kb_document_dropdown, kb_summary, kb_detail],
            )

            new_chat_btn.click(
                fn=self.create_new_session,
                outputs=[chatbot, multimodal_input, session_dropdown, session_state],
            )

            session_dropdown.change(
                fn=self.switch_session,
                inputs=[session_dropdown, session_state],
                outputs=[chatbot, multimodal_input, session_dropdown, session_state, system_prompt_textbox],
            )

            delete_btn.click(
                fn=self.delete_session,
                inputs=[session_dropdown, session_state],
                outputs=[chatbot, multimodal_input, session_dropdown, session_state],
            )

            clear_btn.click(
                fn=self.clear_chat,
                inputs=[session_state],
                outputs=[chatbot, multimodal_input, session_state],
            )

            kb_refresh_btn.click(
                fn=self.refresh_knowledge_base,
                outputs=[kb_document_dropdown, kb_summary, kb_detail],
            )
            kb_show_chunks_btn.click(
                fn=self.show_rag_chunks,
                inputs=[kb_document_dropdown],
                outputs=[kb_detail],
            )
            kb_delete_btn.click(
                fn=self.delete_rag_document,
                inputs=[kb_document_dropdown],
                outputs=[kb_document_dropdown, kb_summary, kb_detail],
            )
            kb_clear_btn.click(
                fn=self.clear_knowledge_base,
                outputs=[kb_document_dropdown, kb_summary, kb_detail],
            )

            # 重新生成最近一轮回答（P1-7）
            regen_event = regenerate_btn.click(
                fn=self.regenerate,
                inputs=[
                    chatbot, session_state,
                    provider_dropdown, model_dropdown, system_prompt_textbox, use_tools_checkbox,
                    use_custom_api_checkbox, custom_base_url_textbox,
                    custom_api_key_textbox, custom_model_textbox,
                ],
                outputs=[chatbot, session_state],
            )

            # 停止生成：取消正在进行的流式任务（P1-7）
            stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[done, regen_event])

        return demo

    def run(self):
        success, message = self.api_client.test_connection()
        if success:
            print("[OK] API连接测试成功！")
        else:
            print(f"[WARN] API连接测试失败: {message}")

        demo = self.create_interface()
        auth = (GRADIO_AUTH_USER, GRADIO_AUTH_PASSWORD) if GRADIO_AUTH_USER and GRADIO_AUTH_PASSWORD else None
        if APP_ENV == "production" and not auth and (GRADIO_SHARE or GRADIO_SERVER_NAME not in ("127.0.0.1", "localhost")):
            raise RuntimeError(
                "生产/对外监听模式必须配置 GRADIO_AUTH_USER 和 GRADIO_AUTH_PASSWORD，"
                "避免未授权访问图文会话与模型接口。"
            )
        if auth:
            print("[INFO] 已启用登录鉴权")
        print(f"[INFO] 启动Gradio服务器: http://{GRADIO_SERVER_NAME}:{GRADIO_SERVER_PORT}")
        if GRADIO_SHARE:
            # Gradio share 隧道依赖 demo.launch；生产环境推荐关闭 share 并使用反向代理暴露服务。
            demo.launch(
                server_name=GRADIO_SERVER_NAME,
                server_port=GRADIO_SERVER_PORT,
                share=GRADIO_SHARE,
                auth=auth,
            )
            return

        from fastapi import FastAPI, Response
        import uvicorn

        api_app = FastAPI(title="VLM Chat Assistant")

        @api_app.get("/health")
        def health():
            return {
                "status": "ok",
                "provider": self.api_client.provider,
                "model": self.api_client.model_name,
                "sessions": self.chat_manager.get_session_count(),
            }

        @api_app.get("/metrics")
        def metrics():
            return Response(
                content=self.metrics.render_prometheus(),
                media_type="text/plain; version=0.0.4",
            )

        mounted_app = gr.mount_gradio_app(
            api_app,
            demo,
            path="/",
            server_name=GRADIO_SERVER_NAME,
            server_port=GRADIO_SERVER_PORT,
            auth=auth,
        )
        uvicorn.run(mounted_app, host=GRADIO_SERVER_NAME, port=GRADIO_SERVER_PORT)


def main():
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("[WARN] 未设置 DASHSCOPE_API_KEY 环境变量")
        print("       如需使用 DashScope，请配置该变量；也可以在前端填写自定义 OpenAI 兼容 API。")
    VLMChatAssistant().run()


if __name__ == "__main__":
    main()
