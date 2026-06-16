import DOMPurify from 'dompurify';
import { marked } from 'marked';

marked.use({
  gfm: true,
  breaks: true,
});

export function renderMarkdown(value: string): string {
  return DOMPurify.sanitize(marked.parse(value || '', { async: false }) as string);
}
