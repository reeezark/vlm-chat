import { create } from 'zustand';
import { api } from '../api/client';
import type {
  AppConfig,
  ChatMessage,
  ChatSession,
  KnowledgeBaseState,
  ModelSettings,
} from '../types';

interface ToastState {
  type: 'error' | 'success' | 'info';
  message: string;
}

interface ChatState {
  config: AppConfig | null;
  sessions: ChatSession[];
  activeSessionId: string;
  messages: ChatMessage[];
  settings: ModelSettings;
  knowledgeBase: KnowledgeBaseState;
  isBootstrapping: boolean;
  isSending: boolean;
  toast: ToastState | null;
  init: () => Promise<void>;
  createSession: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  deleteActiveSession: () => Promise<void>;
  updateSettings: (patch: Partial<ModelSettings>) => void;
  saveLocalApiConfig: () => void;
  clearLocalApiConfig: () => void;
  sendMessage: (content: string, files: File[]) => Promise<void>;
  refreshKnowledgeBase: () => Promise<void>;
  clearToast: () => void;
}

const LOCAL_API_CONFIG_KEY = 'vlm-chat-assistant.api-config';

const emptyKnowledgeBase: KnowledgeBaseState = {
  summary: '知识库信息加载中...',
  documents: [],
};

function loadLocalApiConfig(): Partial<ModelSettings> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(LOCAL_API_CONFIG_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as { apiKey?: string; apiUrl?: string };
    if (!parsed.apiKey && !parsed.apiUrl) return {};
    return {
      useCustomApi: true,
      customApiKey: parsed.apiKey ?? '',
      customBaseUrl: parsed.apiUrl ?? '',
    };
  } catch {
    return {};
  }
}

function defaultSettings(config: AppConfig): ModelSettings {
  const provider = config.defaultProvider;
  const providerConfig = config.providers.find((item) => item.id === provider) ?? config.providers[0];
  return {
    provider: providerConfig?.id ?? 'dashscope',
    model: providerConfig?.models[0] ?? '',
    systemPrompt: config.defaultSystemPrompt,
    useTools: false,
    useCustomApi: false,
    customBaseUrl: '',
    customApiKey: '',
    customModel: '',
    ...loadLocalApiConfig(),
  };
}

export const useChatStore = create<ChatState>((set, get) => ({
  config: null,
  sessions: [],
  activeSessionId: '',
  messages: [],
  settings: {
    provider: 'dashscope',
    model: '',
    systemPrompt: '',
    useTools: false,
    useCustomApi: false,
    customBaseUrl: '',
    customApiKey: '',
    customModel: '',
  },
  knowledgeBase: emptyKnowledgeBase,
  isBootstrapping: true,
  isSending: false,
  toast: null,

  init: async () => {
    try {
      const [config, sessions, knowledgeBase] = await Promise.all([
        api.getConfig(),
        api.listSessions(),
        api.getKnowledgeBase(),
      ]);
      let nextSessions = sessions;
      let activeSession = nextSessions[0];
      if (!activeSession) {
        activeSession = await api.createSession();
        nextSessions = [activeSession];
      }
      const messages = await api.getMessages(activeSession.id);
      set({
        config,
        sessions: nextSessions,
        activeSessionId: activeSession.id,
        messages,
        settings: defaultSettings(config),
        knowledgeBase,
        isBootstrapping: false,
      });
    } catch (error) {
      set({
        isBootstrapping: false,
        toast: { type: 'error', message: error instanceof Error ? error.message : '初始化失败' },
      });
    }
  },

  createSession: async () => {
    const session = await api.createSession();
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: session.id,
      messages: [],
      toast: { type: 'success', message: '已创建新会话' },
    }));
  },

  selectSession: async (sessionId: string) => {
    const messages = await api.getMessages(sessionId);
    set({ activeSessionId: sessionId, messages });
  },

  deleteActiveSession: async () => {
    const { activeSessionId, sessions } = get();
    if (!activeSessionId) return;
    await api.deleteSession(activeSessionId);
    const remaining = sessions.filter((item) => item.id !== activeSessionId);
    if (remaining.length === 0) {
      const session = await api.createSession();
      set({
        sessions: [session],
        activeSessionId: session.id,
        messages: [],
        toast: { type: 'success', message: '已删除会话' },
      });
      return;
    }
    const messages = await api.getMessages(remaining[0].id);
    set({
      sessions: remaining,
      activeSessionId: remaining[0].id,
      messages,
      toast: { type: 'success', message: '已删除会话' },
    });
  },

  updateSettings: (patch) => {
    const { config, settings } = get();
    const next = { ...settings, ...patch };
    if (patch.provider && config) {
      const provider = config.providers.find((item) => item.id === patch.provider);
      next.model = provider?.models[0] ?? '';
    }
    set({ settings: next });
  },

  saveLocalApiConfig: () => {
    const { settings } = get();
    const apiUrl = settings.customBaseUrl.trim();
    const apiKey = settings.customApiKey.trim();
    if (!apiUrl || !apiKey) {
      set({ toast: { type: 'error', message: '请填写 API 地址和 API Key 后再保存' } });
      return;
    }
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(
      LOCAL_API_CONFIG_KEY,
      JSON.stringify({ apiUrl, apiKey }),
    );
    set({
      settings: {
        ...settings,
        useCustomApi: true,
        customBaseUrl: apiUrl,
        customApiKey: apiKey,
      },
      toast: { type: 'success', message: '配置已保存到本地浏览器' },
    });
  },

  clearLocalApiConfig: () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(LOCAL_API_CONFIG_KEY);
    }
    set((state) => ({
      settings: {
        ...state.settings,
        useCustomApi: false,
        customBaseUrl: '',
        customApiKey: '',
      },
      toast: { type: 'success', message: '本地配置已清除' },
    }));
  },

  sendMessage: async (content, files) => {
    const { activeSessionId, settings, messages } = get();
    if (!content.trim() && files.length === 0) return;

    const optimistic: ChatMessage[] = [
      ...messages,
      {
        role: 'user',
        content: content.trim() || (files.length > 0 ? '上传文件' : ''),
        images: [],
        timestamp: Date.now() / 1000,
      },
      {
        role: 'assistant',
        content: '正在思考...',
        images: [],
        timestamp: Date.now() / 1000,
      },
    ];
    set({ messages: optimistic, isSending: true, toast: null });
    try {
      const result = await api.sendMessage(activeSessionId, content, files, settings);
      const [sessions, knowledgeBase] = await Promise.all([
        api.listSessions(),
        api.getKnowledgeBase(),
      ]);
      set({
        activeSessionId: result.sessionId,
        messages: result.messages,
        sessions,
        knowledgeBase,
        isSending: false,
      });
    } catch (error) {
      set({
        messages,
        isSending: false,
        toast: { type: 'error', message: error instanceof Error ? error.message : '发送失败' },
      });
    }
  },

  refreshKnowledgeBase: async () => {
    const knowledgeBase = await api.getKnowledgeBase();
    set({ knowledgeBase });
  },

  clearToast: () => set({ toast: null }),
}));
