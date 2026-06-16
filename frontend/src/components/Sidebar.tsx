import { Database, MessageSquarePlus, Trash2 } from 'lucide-react';
import { useChatStore } from '../hooks/useChatStore';

export function Sidebar() {
  const {
    sessions,
    activeSessionId,
    knowledgeBase,
    createSession,
    selectSession,
    deleteActiveSession,
    refreshKnowledgeBase,
  } = useChatStore();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">V</div>
        <div>
          <h1>VLM Assistant</h1>
          <p>图文与知识库问答</p>
        </div>
      </div>

      <button className="primary-action" onClick={createSession}>
        <MessageSquarePlus size={18} />
        新建对话
      </button>

      <section className="panel">
        <div className="panel-title">历史对话</div>
        <div className="session-list">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => selectSession(session.id)}
            >
              <span>{session.name}</span>
              <small>{session.messageCount} 轮</small>
            </button>
          ))}
        </div>
      </section>

      <section className="panel kb-panel">
        <div className="panel-title">
          <Database size={15} />
          知识库
        </div>
        <p className="muted">{knowledgeBase.summary}</p>
        <div className="kb-docs">
          {knowledgeBase.documents.slice(0, 4).map((doc) => (
            <div className="kb-doc" key={doc.document_id}>
              <span>{doc.filename}</span>
              <small>{doc.chunk_count} 段</small>
            </div>
          ))}
        </div>
        <button className="ghost-action" onClick={refreshKnowledgeBase}>
          刷新知识库
        </button>
      </section>

      <button className="danger-action" onClick={deleteActiveSession}>
        <Trash2 size={16} />
        删除当前对话
      </button>
    </aside>
  );
}
