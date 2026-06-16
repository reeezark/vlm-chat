import { KeyRound, Save, SlidersHorizontal, Trash2 } from 'lucide-react';
import { useChatStore } from '../hooks/useChatStore';

export function ModelSettingsPanel() {
  const {
    config,
    settings,
    updateSettings,
    saveLocalApiConfig,
    clearLocalApiConfig,
  } = useChatStore();
  const activeProvider = config?.providers.find((provider) => provider.id === settings.provider);

  return (
    <section className="settings-card">
      <div className="settings-title">
        <SlidersHorizontal size={17} />
        模型配置
      </div>

      <label>
        模型提供方
        <select
          value={settings.provider}
          onChange={(event) => updateSettings({ provider: event.target.value })}
        >
          {config?.providers.map((provider) => (
            <option value={provider.id} key={provider.id}>
              {provider.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        模型
        <select
          value={settings.model}
          onChange={(event) => updateSettings({ model: event.target.value })}
          disabled={settings.useCustomApi}
        >
          {activeProvider?.models.map((model) => (
            <option value={model} key={model}>
              {model}
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={settings.useTools}
          onChange={(event) => updateSettings({ useTools: event.target.checked })}
        />
        启用联网搜索
      </label>

      <label>
        系统提示词
        <textarea
          rows={3}
          value={settings.systemPrompt}
          onChange={(event) => updateSettings({ systemPrompt: event.target.value })}
        />
      </label>

      <div className="custom-api-box">
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={settings.useCustomApi}
            onChange={(event) => updateSettings({ useCustomApi: event.target.checked })}
          />
          使用自定义 OpenAI 兼容接口
        </label>
        <label>
          API 地址
          <input
            value={settings.customBaseUrl}
            placeholder="https://api.openai.com/v1"
            onChange={(event) => updateSettings({ customBaseUrl: event.target.value })}
          />
        </label>
        {!settings.customBaseUrl && !settings.customApiKey ? (
          <p className="form-hint">未检测到已保存配置，请填写 API 地址和 API Key。</p>
        ) : (
          <p className="form-hint success">已加载当前表单配置，可保存到本地浏览器。</p>
        )}
        <label>
          <span className="inline-label">
            <KeyRound size={14} />
            API Key
          </span>
          <input
            type="password"
            value={settings.customApiKey}
            placeholder="仅保存在当前运行时会话"
            onChange={(event) => updateSettings({ customApiKey: event.target.value })}
          />
        </label>
        <div className="settings-actions">
          <button type="button" className="primary-action compact" onClick={saveLocalApiConfig}>
            <Save size={14} />
            保存配置
          </button>
          <button type="button" className="ghost-action compact" onClick={clearLocalApiConfig}>
            <Trash2 size={14} />
            清除配置
          </button>
        </div>
        <label>
          模型名称
          <input
            value={settings.customModel}
            placeholder="gpt-4o / qwen-vl-plus / your-model"
            onChange={(event) => updateSettings({ customModel: event.target.value })}
          />
        </label>
      </div>
    </section>
  );
}
