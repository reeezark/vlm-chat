import { AlertCircle, Loader2 } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { Composer } from './Composer';
import { ModelSettingsPanel } from './ModelSettings';
import { useChatStore } from '../hooks/useChatStore';

export function ChatShell() {
  const {
    messages,
    isBootstrapping,
    isSending,
    toast,
    clearToast,
    sendMessage,
  } = useChatStore();

  if (isBootstrapping) {
    return (
      <main className="chat-shell center-state">
        <Loader2 className="spin" size={28} />
        <p>正在加载会话和模型配置...</p>
      </main>
    );
  }

  return (
    <main className="chat-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Modern VLM Workspace</p>
          <h2>图文、多文档与知识库问答</h2>
        </div>
        <a href="/gradio" className="gradio-link">
          Gradio 兼容入口
        </a>
      </header>

      {toast && (
        <div className={`toast ${toast.type}`} onClick={clearToast}>
          <AlertCircle size={16} />
          {toast.message}
        </div>
      )}

      <div className="content-grid">
        <section className="conversation">
          {messages.length === 0 ? (
            <div className="empty-state">
              <span>开始一次多模态问答</span>
              <h3>上传图片或 PDF，也可以直接输入问题。</h3>
              <p>支持内置 Provider 与自定义 OpenAI 兼容接口，API Key 按浏览器会话隔离。</p>
            </div>
          ) : (
            messages.map((message, index) => (
              <ChatMessage message={message} key={`${message.role}-${message.timestamp ?? index}-${index}`} />
            ))
          )}
          {isSending && (
            <div className="typing-indicator">
              <Loader2 className="spin" size={16} />
              模型正在生成回答...
            </div>
          )}
        </section>

        <ModelSettingsPanel />
      </div>

      <Composer disabled={isSending} onSubmit={sendMessage} />
    </main>
  );
}
