# React 前端重构说明

## 背景

原前端基于 Gradio 单体实现，主要问题包括：

- UI 组件、业务流程、模型调用、RAG、审计和服务启动集中在 `app.py`，单文件复杂度高。
- Gradio 回调承担大量状态编排，难以做组件级复用、路由扩展和精细交互反馈。
- 样式以注入 CSS/JS 为主，缺少现代前端工程化、类型约束和独立构建流程。
- 多端响应式、加载状态、错误提示和前端状态管理能力有限。

本次重构采用 React + Vite + TypeScript，并保留 Gradio 兼容入口，降低迁移风险。

## 技术选型

| 模块 | 选型 | 说明 |
|---|---|---|
| 前端框架 | React | 生态成熟，适合组件化 Chat UI |
| 构建工具 | Vite | 启动和构建速度快，配置轻量 |
| 类型系统 | TypeScript | 提升接口、状态和组件维护性 |
| 状态管理 | Zustand | 轻量、易测试，适合中小型应用 |
| 图标 | lucide-react | 轻量一致的 SVG 图标 |
| Markdown | marked + DOMPurify | Markdown 渲染并进行 HTML 净化 |
| 后端 API | FastAPI `/api/*` | 复用现有模型调用、RAG、审计和会话逻辑 |

## 目录结构

```text
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    api/
      client.ts              # REST API 封装
    components/
      ChatMessage.tsx        # 单条消息渲染
      ChatShell.tsx          # 主聊天布局
      Composer.tsx           # 输入框和附件上传
      ModelSettings.tsx      # 模型与自定义 API 配置
      Sidebar.tsx            # 会话与知识库侧边栏
    hooks/
      useChatStore.ts        # Zustand 全局状态
    styles/
      app.css                # 响应式样式系统
    types/
      index.ts               # API 和 UI 类型定义
    utils/
      markdown.ts            # Markdown 安全渲染
    App.tsx
    main.tsx
```

## 后端 API

React 前端通过以下接口访问后端：

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/config` | GET | 获取 Provider、默认模型、系统提示词和能力开关 |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/sessions` | POST | 创建新会话 |
| `/api/sessions/{session_id}/messages` | GET | 获取会话消息 |
| `/api/sessions/{session_id}` | DELETE | 删除会话 |
| `/api/chat` | POST | 提交文本、图片、PDF 与模型配置 |
| `/api/knowledge-base` | GET | 获取知识库摘要与文档列表 |

`/api/chat` 使用 `multipart/form-data`，支持文本、图片和 PDF 上传，并复用现有 `process_query()` 业务流程。

## 本地开发

启动后端：

```bash
cd /Users/bytedance/mywork/multiple/finalwork/vlm-chat-assistant
source .venv/bin/activate
python app.py
```

启动 React 开发服务器：

```bash
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

Vite 会把 `/api`、`/health`、`/metrics`、`/uploads` 代理到 `http://127.0.0.1:7860`。

## 生产构建

构建前端：

```bash
cd frontend
npm install
npm run build
```

启用 React 前端并启动后端：

```bash
cd ..
FRONTEND_MODE=react python app.py
```

访问：

```text
http://127.0.0.1:7860
```

Gradio 兼容入口保留在：

```text
http://127.0.0.1:7860/gradio
```

## Docker 部署

Dockerfile 已改为多阶段构建：

1. Node 阶段构建 `frontend/dist`
2. Python 阶段安装后端依赖
3. 将 React 静态产物复制到镜像中
4. 默认设置 `FRONTEND_MODE=react`

启动：

```bash
docker compose up --build
```

## 验收要点

- React 前端可加载 Provider、会话、知识库状态。
- 文本、图片、PDF 提交仍复用现有模型调用链路。
- 自定义 OpenAI 兼容 API 配置继续按浏览器会话隔离。
- 小屏幕下侧边栏、模型配置和聊天区可纵向排列。
- Gradio 旧入口仍可作为兼容模式使用。
