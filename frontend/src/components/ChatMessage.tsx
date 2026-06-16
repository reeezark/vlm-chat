import type { ChatMessage as ChatMessageType } from '../types';
import { renderMarkdown } from '../utils/markdown';

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <article className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">{isUser ? '你' : 'AI'}</div>
      <div className="message-card">
        {message.images.length > 0 && (
          <div className="message-images">
            {message.images.map((image) => (
              <img src={`/uploads/${image}`} alt="上传内容" key={image} />
            ))}
          </div>
        )}
        <div
          className="markdown-body"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
        />
      </div>
    </article>
  );
}
