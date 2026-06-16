export interface ProviderConfig {
  id: string;
  label: string;
  models: string[];
  requiresApiKey?: boolean;
  baseUrl?: string;
}

export interface AppConfig {
  providers: ProviderConfig[];
  defaultProvider: string;
  defaultSystemPrompt: string;
  enableTools: boolean;
  enableRag: boolean;
  maxImagesPerMessage: number;
}

export interface ChatSession {
  id: string;
  name: string;
  messageCount: number;
  createdAt?: number;
  lastActive?: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  images: string[];
  timestamp?: number;
}

export interface ModelSettings {
  provider: string;
  model: string;
  systemPrompt: string;
  useTools: boolean;
  useCustomApi: boolean;
  customBaseUrl: string;
  customApiKey: string;
  customModel: string;
}

export interface ModelConfigSummary {
  provider: string;
  label: string;
  model: string;
  baseUrl: string;
  isCustom: boolean;
  keySource: string;
  hasApiKey: boolean;
  configHash: string;
}

export interface ModelConfigValidationResult {
  ok: boolean;
  errorCode: string;
  message: string;
  detail?: string;
  latencyMs?: number;
  summary?: ModelConfigSummary | null;
}

export interface KnowledgeDocument {
  document_id: string;
  filename: string;
  content_type?: string;
  chunk_count: number;
  created_at?: number;
}

export interface KnowledgeBaseState {
  summary: string;
  documents: KnowledgeDocument[];
}
