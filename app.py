"""
主应用入口
基于Gradio构建的智能图文问答助手Web界面
ChatGPT风格：左侧会话列表 + 中间聊天区
"""
import os
import sys
import logging

os.environ["OPENAI_LOG"] = "error"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
logging.disable(logging.DEBUG)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from src.api_client import VLMAPIClient
from src.chat_manager import ChatManager
from src.image_processor import ImageProcessor
from src.config import GRADIO_SERVER_NAME, GRADIO_SERVER_PORT, GRADIO_SHARE

# ── 暗色主题 ─────────────────────────────────────────────────────
DARK_THEME = gr.themes.Base(
    neutral_hue=gr.themes.colors.Color(
        c50="#fafafa", c100="#f4f4f5", c200="#e4e4e7", c300="#d4d4d8",
        c400="#a1a1aa", c500="#71717a", c600="#52525b", c700="#3f3f46",
        c800="#27272a", c900="#18181b", c950="#09090b",
    ),
    primary_hue=gr.themes.colors.emerald,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
)

# ── JavaScript注入暗色样式（最高优先级） ─────────────────────────
INJECT_CSS_JS = """
() => {
    const css = `
    /* ── 全局 ──────────────────────── */
    html, body, .gradio-container {
        background: #111 !important;
        margin: 0 !important; padding: 0 !important;
        max-width: 100% !important;
    }
    footer { display: none !important; }

    /* ── 侧边栏 ────────────────────── */
    #sidebar {
        background: #0d0d0d !important;
        border-right: 1px solid #222 !important;
        padding: 24px 16px !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
        overflow-y: auto !important;
        height: 100vh !important;
    }
    #sidebar * { background: transparent; }
    #sidebar h3, #sidebar .sidebar-title {
        color: #e4e4e7 !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
        margin: 0 0 4px !important;
    }
    #sidebar .new-chat-btn,
    #sidebar button.new-chat-btn {
        background: #1a1a1a !important;
        color: #d4d4d8 !important;
        border: 1px solid #333 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        transition: all 0.15s !important;
    }
    #sidebar .new-chat-btn:hover { background: #252525 !important; border-color: #555 !important; }

    /* 下拉框暗色 */
    #sidebar label { color: #71717a !important; font-size: 11px !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.8px !important; }
    #sidebar .session-dropdown input,
    #sidebar .session-dropdown .wrap {
        background: #1a1a1a !important;
        color: #d4d4d8 !important;
        border: 1px solid #333 !important;
        border-radius: 10px !important;
    }
    #sidebar .session-dropdown input:focus,
    #sidebar .session-dropdown .wrap:focus-within { border-color: #10b981 !important; }

    /* 侧边栏底部 */
    .sidebar-footer {
        margin-top: auto !important;
        padding-top: 16px !important;
        border-top: 1px solid #1e1e1e !important;
    }
    .danger-btn, button.danger-btn {
        background: transparent !important;
        border: 1px solid #2d1111 !important;
        color: #f87171 !important;
        border-radius: 8px !important;
        font-size: 12px !important;
        padding: 8px 14px !important;
        transition: all 0.15s !important;
    }
    .danger-btn:hover { background: #1a0808 !important; border-color: #4a1a1a !important; }

    /* ── 主聊天区 ───────────────────── */
    #main-area {
        background: #111 !important;
        display: flex !important;
        flex-direction: column !important;
        height: 100vh !important;
        padding: 0 !important;
    }
    #top-bar {
        padding: 18px 32px !important;
        border-bottom: 1px solid #222 !important;
        flex-shrink: 0 !important;
        background: #111 !important;
    }
    #top-bar p { color: #d4d4d8 !important; font-size: 15px !important; font-weight: 600 !important; margin: 0 !important; }

    /* 聊天消息 */
    #chat-area {
        flex: 1 !important;
        min-height: 0 !important;
        overflow-y: auto !important;
        background: #111 !important;
        padding: 16px 0 !important;
    }
    #chat-area * { background: transparent; }
    #chat-area .user .message-bubble-border,
    #chat-area .user > div > div {
        background: #1e1e1e !important;
        border-radius: 18px !important;
        border: none !important;
        padding: 12px 20px !important;
    }
    #chat-area .bot .message-bubble-border,
    #chat-area .bot > div > div {
        background: transparent !important;
        border: none !important;
        padding: 12px 20px !important;
    }
    #chat-area .message, #chat-area p, #chat-area span, #chat-area div {
        color: #d4d4d8 !important;
    }
    #chat-area .message { font-size: 14px !important; line-height: 1.8 !important; }
    #chat-area img { border-radius: 12px !important; max-width: 300px !important; max-height: 300px !important; }
    #chat-area .avatar-container { display: none !important; }

    /* ── 输入区 ─────────────────────── */
    #input-box {
        padding: 16px 32px 28px !important;
        border-top: 1px solid #222 !important;
        flex-shrink: 0 !important;
        background: #111 !important;
    }
    #input-box .container {
        background: #1e1e1e !important;
        border: 1px solid #333 !important;
        border-radius: 16px !important;
        padding: 6px 10px !important;
        transition: all 0.2s !important;
    }
    #input-box .container:focus-within {
        border-color: #10b981 !important;
        box-shadow: 0 0 0 3px rgba(16,185,129,0.12) !important;
    }
    #input-box textarea, #input-box input {
        background: transparent !important;
        color: #e4e4e7 !important;
        font-size: 14px !important;
        border: none !important;
    }
    #input-box textarea::placeholder, #input-box input::placeholder { color: #52525b !important; }
    #input-box button { border-radius: 10px !important; }
    .input-actions { padding: 8px 0 0 !important; }
    .clear-btn, button.clear-btn {
        background: transparent !important;
        border: 1px solid #333 !important;
        color: #71717a !important;
        border-radius: 8px !important;
        font-size: 12px !important;
        padding: 5px 16px !important;
        transition: all 0.15s !important;
    }
    .clear-btn:hover { background: #1e1e1e !important; color: #a1a1aa !important; }

    /* ── 全局暗色文字 ───────────────── */
    .gradio-container, .gradio-container * { color: #d4d4d8; }
    a { color: #10b981 !important; }
    .prose { color: #d4d4d8 !important; }
    `;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
}
"""


class VLMChatAssistant:
    """VLM聊天助手应用"""

    def __init__(self):
        self.api_client = VLMAPIClient()
        self.chat_manager = ChatManager()
        self.image_processor = ImageProcessor()

        self.chat_manager.cleanup_expired_sessions()
        if not self.chat_manager.current_session_id:
            self.chat_manager.create_session()

    def _session_choices(self) -> list[str]:
        return [s["name"] for s in self.chat_manager.get_all_sessions()]

    def _current_name(self) -> str:
        cur = self.chat_manager.get_current_session()
        return cur["name"] if cur else ""

    def process_query(self, multimodal_input, chatbot_history):
        session_id = self.chat_manager.current_session_id
        if not session_id:
            return chatbot_history, None
        if multimodal_input is None:
            return chatbot_history, None

        question = (multimodal_input.get("text") or "").strip()
        files = multimodal_input.get("files") or []
        image_path = files[0] if files else None

        if not question and not image_path:
            return chatbot_history, None
        if image_path and not question:
            question = "请描述这张图片的内容"

        current_image = None
        if image_path:
            is_valid, msgs = self.image_processor.validate_image(image_path)
            if not is_valid:
                chatbot_history.append({"role": "user", "content": question or "上传图片"})
                chatbot_history.append({"role": "assistant", "content": "图片验证失败: " + "; ".join(msgs)})
                return chatbot_history, None
            current_image = image_path

        session_image = self.chat_manager.get_current_image()
        use_image = current_image or session_image
        history = self.chat_manager.get_history(session_id, format_for_api=True)

        try:
            self.chat_manager.add_message(session_id, "user", question, image_path=current_image)
            response = self.api_client.call_api(image_path=use_image, question=question, history=history)
            self.chat_manager.add_message(session_id, "assistant", response)
            chatbot_history = self.chat_manager.format_for_chatbot(session_id)
        except Exception as e:
            chatbot_history.append({"role": "user", "content": question or "上传图片"})
            chatbot_history.append({"role": "assistant", "content": f"API调用失败: {str(e)}"})

        return chatbot_history, None

    def create_new_session(self):
        self.chat_manager.create_session()
        return self.chat_manager.format_for_chatbot(), None, gr.Dropdown(
            choices=self._session_choices(), value=self._current_name()
        )

    def switch_session(self, session_name):
        if not session_name:
            return [], None, gr.Dropdown(choices=self._session_choices())
        for s in self.chat_manager.get_all_sessions():
            if s["name"] == session_name:
                self.chat_manager.set_current_session(s["session_id"])
                break
        return self.chat_manager.format_for_chatbot(), self.chat_manager.get_current_image(), gr.Dropdown(
            choices=self._session_choices(), value=session_name
        )

    def delete_session(self, session_name):
        if not session_name:
            return [], None, gr.Dropdown(choices=self._session_choices())
        for s in self.chat_manager.get_all_sessions():
            if s["name"] == session_name:
                self.chat_manager.delete_session(s["session_id"])
                break
        return self.chat_manager.format_for_chatbot(), self.chat_manager.get_current_image(), gr.Dropdown(
            choices=self._session_choices(), value=self._current_name()
        )

    def clear_chat(self):
        self.chat_manager.clear_history()
        return [], None

    def create_interface(self):
        with gr.Blocks(title="VLM Chat", fill_height=True) as demo:
            with gr.Row(elem_id="app-row", equal_height=True):
                # ═══ 侧边栏 ═══
                with gr.Column(min_width=260, scale=0, elem_id="sidebar"):
                    gr.HTML('<div style="color:#e4e4e7;font-size:20px;font-weight:700;letter-spacing:-0.5px;padding:0 2px;">VLM Chat</div>')
                    new_chat_btn = gr.Button("+ 新建对话", elem_classes="new-chat-btn", size="sm")
                    session_dropdown = gr.Dropdown(
                        choices=self._session_choices(),
                        value=self._current_name(),
                        label="历史对话",
                        interactive=True,
                        elem_classes="session-dropdown",
                    )
                    with gr.Group(elem_classes="sidebar-footer"):
                        delete_btn = gr.Button("删除当前对话", elem_classes="danger-btn", size="sm", variant="secondary")

                # ═══ 主聊天区 ═══
                with gr.Column(scale=1, min_width=400, elem_id="main-area"):
                    gr.Markdown("**基于 Qwen-VL-Plus 的智能图文问答**", elem_id="top-bar")

                    chatbot = gr.Chatbot(
                        height=500,
                        show_label=False,
                        elem_id="chat-area",
                        value=self.chat_manager.format_for_chatbot(),
                        placeholder="上传图片或输入问题开始对话…",
                    )

                    with gr.Group(elem_id="input-box"):
                        multimodal_input = gr.MultimodalTextbox(
                            file_types=["image"],
                            placeholder="输入问题或上传图片…",
                            show_label=False,
                            sources=["upload"],
                            max_plain_text_length=2000,
                        )
                        with gr.Row(elem_classes="input-actions"):
                            clear_btn = gr.Button("清空对话", elem_classes="clear-btn", size="sm")

            # ── 事件 ───────────────────────────────────
            done = multimodal_input.submit(
                fn=self.process_query,
                inputs=[multimodal_input, chatbot],
                outputs=[chatbot, multimodal_input],
            )
            done.then(
                fn=lambda: gr.Dropdown(choices=self._session_choices(), value=self._current_name()),
                outputs=[session_dropdown],
            )

            new_chat_btn.click(
                fn=self.create_new_session,
                outputs=[chatbot, multimodal_input, session_dropdown],
            )

            session_dropdown.change(
                fn=self.switch_session,
                inputs=[session_dropdown],
                outputs=[chatbot, multimodal_input, session_dropdown],
            )

            delete_btn.click(
                fn=self.delete_session,
                inputs=[session_dropdown],
                outputs=[chatbot, multimodal_input, session_dropdown],
            )

            clear_btn.click(
                fn=self.clear_chat,
                outputs=[chatbot, multimodal_input],
            )

        return demo

    def run(self):
        success, message = self.api_client.test_connection()
        if success:
            print("[OK] API连接测试成功！")
        else:
            print(f"[WARN] API连接测试失败: {message}")

        demo = self.create_interface()
        print(f"[INFO] 启动Gradio服务器: http://{GRADIO_SERVER_NAME}:{GRADIO_SERVER_PORT}")
        demo.launch(
            server_name=GRADIO_SERVER_NAME,
            server_port=GRADIO_SERVER_PORT,
            share=GRADIO_SHARE,
            theme=DARK_THEME,
            js=INJECT_CSS_JS,
        )


def main():
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("[ERROR] 未设置 DASHSCOPE_API_KEY 环境变量")
        print("请设置环境变量后运行:")
        print("  Windows: set DASHSCOPE_API_KEY=your-api-key")
        return
    VLMChatAssistant().run()


if __name__ == "__main__":
    main()
