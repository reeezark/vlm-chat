import { ChangeEvent, FormEvent, useRef, useState } from 'react';
import { Paperclip, SendHorizontal, X } from 'lucide-react';

interface Props {
  disabled: boolean;
  onSubmit: (content: string, files: File[]) => Promise<void>;
}

export function Composer({ disabled, onSubmit }: Props) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(event.target.files ?? []));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (disabled || (!content.trim() && files.length === 0)) return;
    await onSubmit(content, files);
    setContent('');
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {files.length > 0 && (
        <div className="attachment-list">
          {files.map((file) => (
            <span className="attachment-chip" key={`${file.name}-${file.size}`}>
              {file.name}
              <button type="button" onClick={() => setFiles(files.filter((item) => item !== file))}>
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="composer-row">
        <button
          className="icon-button"
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label="上传文件"
        >
          <Paperclip size={18} />
        </button>
        <textarea
          value={content}
          rows={1}
          placeholder="输入问题，或上传图片 / PDF 文档..."
          onChange={(event) => setContent(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              void handleSubmit(event);
            }
          }}
        />
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf"
          onChange={handleFiles}
          hidden
        />
        <button className="send-button" type="submit" disabled={disabled}>
          <SendHorizontal size={18} />
          发送
        </button>
      </div>
    </form>
  );
}
