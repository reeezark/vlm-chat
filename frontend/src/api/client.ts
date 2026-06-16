import type {
  AppConfig,
  ChatMessage,
  ChatSession,
  KnowledgeBaseState,
  ModelSettings,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getConfig: () => requestJson<AppConfig>('/api/config'),

  listSessions: async () => {
    const data = await requestJson<{ sessions: ChatSession[] }>('/api/sessions');
    return data.sessions;
  },

  createSession: async () => {
    const data = await requestJson<{ session: ChatSession }>('/api/sessions', { method: 'POST' });
    return data.session;
  },

  deleteSession: (sessionId: string) =>
    requestJson<{ ok: boolean }>(`/api/sessions/${sessionId}`, { method: 'DELETE' }),

  getMessages: async (sessionId: string) => {
    const data = await requestJson<{ messages: ChatMessage[] }>(`/api/sessions/${sessionId}/messages`);
    return data.messages;
  },

  sendMessage: async (
    sessionId: string,
    content: string,
    files: File[],
    settings: ModelSettings,
  ) => {
    const form = new FormData();
    form.append('session_id', sessionId);
    form.append('message', content);
    form.append('provider', settings.provider);
    form.append('model', settings.model);
    form.append('system_prompt', settings.systemPrompt);
    form.append('use_tools', String(settings.useTools));
    form.append('use_custom_api', String(settings.useCustomApi));
    form.append('custom_base_url', settings.customBaseUrl);
    form.append('custom_api_key', settings.customApiKey);
    form.append('custom_model', settings.customModel);
    files.forEach((file) => form.append('files', file));

    const data = await requestJson<{ sessionId: string; messages: ChatMessage[] }>('/api/chat', {
      method: 'POST',
      body: form,
    });
    return data;
  },

  getKnowledgeBase: () => requestJson<KnowledgeBaseState>('/api/knowledge-base'),
};
