# 基于VLM的智能图文问答助手

## 项目简介

本项目是一个基于视觉语言模型（VLM）的智能图文问答助手，支持"看图/看文档能聊天"的多模态交互。用户可以上传图片（自然场景或文档）并提出问题，助手会基于图片内容进行中文问答和基础推理。

### 核心功能

- 📷 **多模态输入**：支持多张图片、PDF 文档 + 文本问题
- 💬 **多轮对话**：支持上下文记忆、流式输出、重新生成、停止生成和复制回答
- 🧠 **中文问答**：针对中文图文内容进行准确问答
- 🔍 **工具调用**：支持联网搜索工具，补充实时信息
- 🔀 **多 Provider**：支持 DashScope、OpenAI、OpenRouter、本地 Ollama 等 OpenAI 兼容接口
- 🖥️ **Web UI**：Claude 风格现代化响应式界面，支持 Markdown、LaTeX、Mermaid 等富文本展示
- 🐳 **容器化部署**：提供 Dockerfile 和 docker-compose.yml

### 技术栈

| 技术维度 | 选择方案 | 说明 |
|---------|---------|------|
| **视觉语言模型** | Qwen-VL / GPT-4o / OpenRouter / Ollama | 多 Provider OpenAI 兼容调用 |
| **前端框架** | React + Vite + TypeScript / Gradio 5.x | React 为现代前端入口，Gradio 保留兼容入口 |
| **API接口** | OpenAI兼容接口 | 简化调用逻辑 |
| **图片处理** | Pillow | 图片格式验证和处理 |
| **文档处理** | pypdf | PDF 文本提取 |
| **会话存储** | SQLite | 本地持久化会话 |

## 快速开始

### 环境要求

- Python 3.10+（Docker 镜像使用 Python 3.11；本地建议使用项目 `.venv`）
- Node.js 20+（仅构建或开发 React 前端时需要）
- 至少配置一个模型 Provider 的 API Key，或在前端填写自定义 OpenAI 兼容接口

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置API密钥

复制环境变量模板并配置至少一个 Provider 的 API Key。也可以不在 `.env` 写 Key，启动后在前端“自定义模型 API”面板中填写 OpenAI 兼容 API 地址、API Key 和模型名。

```bash
cp .env.example .env
```

OpenAI 兼容接口示例：

```bash
DEFAULT_PROVIDER=openai
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=your-openai-compatible-api-key
MODEL_NAME=qwen-vl-plus
```

如果你的 OpenAI 兼容服务使用自定义模型名，可以用 `MODEL_NAME` 指定默认模型，也可以用 `OPENAI_MODELS` 配置前端下拉模型列表：

```bash
OPENAI_MODELS=qwen-vl-plus,qwen-vl-max,custom-vlm
```

DashScope 示例：

**Windows:**
```bash
set DASHSCOPE_API_KEY=your-api-key
```

**Linux/Mac:**
```bash
export DASHSCOPE_API_KEY=your-api-key
```

获取API密钥：访问 [阿里云百炼平台](https://help.aliyun.com/zh/model-studio/getting-started/get-api-key)

生产或对外部署时，请务必配置：

```bash
APP_ENV=production
GRADIO_AUTH_USER=your-user
GRADIO_AUTH_PASSWORD=your-strong-password
```

### 3. 运行应用

```bash
python app.py
```

默认启动 Gradio 兼容入口，访问 `http://localhost:7860` 即可使用。

如需使用重构后的 React 前端：

```bash
cd frontend
npm install
npm run build
cd ..
FRONTEND_MODE=react python app.py
```

React 前端访问 `http://localhost:7860`，Gradio 兼容入口访问 `http://localhost:7860/gradio`。

React 开发模式：

```bash
python app.py
cd frontend
npm install
npm run dev
```

开发模式访问 `http://127.0.0.1:5173`，Vite 会代理 `/api` 到后端。

如果未配置默认 Provider 的 API Key，应用仍可启动；首次对话前请在侧边栏“自定义模型 API”中填写：

- **API 地址**：OpenAI 兼容接口地址，例如 `https://api.openai.com/v1`
- **API Key**：当前模型服务的访问密钥，仅保存在运行时客户端，不写入数据库
- **模型名称**：例如 `gpt-4o`、`qwen-vl-plus` 或私有部署模型名

### 4. Docker 部署

```bash
docker compose up --build
```

会话数据库和上传文件默认持久化到 `./data`。如果将 `GRADIO_SERVER_NAME` 设置为 `0.0.0.0` 或开启 `GRADIO_SHARE=true`，生产环境必须启用鉴权。

## 项目结构

```
vlm-chat-assistant/
│
├── app.py                    # 主应用入口（FastAPI API + Gradio 兼容入口）
├── requirements.txt          # 项目依赖
├── README.md                 # 项目说明文档
│
├── frontend/                 # React + Vite + TypeScript 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── api/              # REST API 封装
│   │   ├── components/       # React 组件
│   │   ├── hooks/            # Zustand 状态管理
│   │   ├── styles/           # 响应式样式
│   │   ├── types/            # TypeScript 类型
│   │   └── utils/            # Markdown 等工具
│
├── src/
│   ├── __init__.py           # 模块初始化
│   ├── config.py             # 配置文件（Provider、安全、上传、性能）
│   ├── api_client.py         # 多 Provider API 调用封装
│   ├── chat_manager.py       # SQLite 会话管理（上下文维护）
│   ├── image_processor.py    # 图片/PDF 预处理
│   ├── tools.py              # 工具调用（联网搜索）
│
├── data/
│   ├── test_images/          # 测试图片目录
│   │   ├── natural_scene/    # 自然场景图片
│   │   ├── document/         # 文档图片
│   ├── sessions/             # SQLite 会话数据库
│   ├── uploads/              # 上传图片持久化目录
│   ├── temp_images/          # 临时图片存储
│   ├── evaluation_dataset.json # 评测数据集
│
├── evaluation/
│   ├── evaluator.py          # 评测脚本
│   ├── evaluation_report.md  # 评测结果报告
│
├── Dockerfile                # 容器镜像构建
└── docker-compose.yml        # 本地容器化部署
```

## 使用说明

### React 前端

React 前端提供更清晰的组件化体验：

- 左侧侧边栏：新建、切换、删除会话，查看知识库摘要。
- 中间聊天区：展示 Markdown 回答、图片附件、加载状态和错误提示。
- 右侧配置区：切换 Provider、模型、系统提示词、联网搜索和自定义 OpenAI 兼容 API。
- 响应式布局：窄屏下侧边栏、模型配置和聊天区自动纵向排列。

### 图片问答

1. 上传图片（支持 JPG、PNG、WebP 格式，默认最大 5MB）或 PDF 文档
2. 输入问题（如："这张图片里有什么？"）
3. 点击提交，模型会流式回复
4. 可以继续追问、重新生成、停止生成或复制回答

### 自定义模型 API

侧边栏支持两种模型选择方式：

- **内置 Provider**：通过“模型提供方”和“模型”下拉框选择 DashScope、OpenAI、OpenRouter、Ollama 等预置配置。
- **自定义 OpenAI 兼容接口**：展开“自定义模型 API”，勾选“使用自定义 OpenAI 兼容接口”，填写 `Base URL`、`API Key` 和模型名后提交问题。

自定义配置适用于私有网关、自建模型服务、中转服务或任何兼容 `/v1/chat/completions` 的多模态模型接口。

React 前端支持将自定义 `API 地址` 和 `API Key` 保存到浏览器 `localStorage`：

- 点击“保存配置”后，下次访问页面会自动回填配置并启用自定义接口。
- 点击“清除配置”会删除本地保存的 API 地址和 API Key。
- 保存前会校验 API 地址和 API Key 是否为空。
- 本地保存为明文，仅适合个人设备或可信浏览器环境。
自定义模型客户端按浏览器会话隔离，不同会话可同时使用不同的 API 地址、API Key 和模型名，避免互相覆盖配置。

### 安全与稳定性配置

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| `APP_ENV` | `development` | 生产环境建议设为 `production` |
| `GRADIO_AUTH_USER` / `GRADIO_AUTH_PASSWORD` | 空 | 配置后启用登录鉴权；生产对外部署时必须配置 |
| `REQUESTS_PER_MINUTE` | `20` | 每个浏览器会话每分钟请求上限，设为 `0` 可关闭 |
| `MAX_IMAGES_PER_MESSAGE` | `4` | 单条消息最多图片数 |
| `MAX_DOC_SIZE_MB` | `10` | PDF 最大大小 |
| `MAX_PDF_PAGES` | `20` | 单个 PDF 最大解析页数 |
| `UPLOAD_RETENTION_SECONDS` | `604800` | 上传/临时文件保留时间 |
| `IMAGE_BASE64_CACHE_SIZE` | `128` | 本地图片 base64 编码缓存容量 |

### 支持的图像类型

- **自然场景**：商品图、人物、动物、建筑、风景等
- **文档图像**：讲义截图、论文页面、书籍段落、图表等

### 示例问题

```
- 这张图片里有什么？
- 图片中的文字内容是什么？
- 请描述图片中的场景
- 这个商品的品牌是什么？
- 这段讲义的主要内容是什么？
- 图片中的公式表示什么含义？
```

## API调用说明

本项目统一使用 OpenAI 兼容 Chat Completions 协议，可调用 DashScope、OpenAI、OpenRouter、Ollama 或前端自定义 API。

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="qwen-vl-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "图片路径"}},
                {"type": "text", "text": "用户问题"}
            ]
        }
    ]
)
```

更多API文档请参考：[DashScope API文档](https://help.aliyun.com/zh/model-studio/developer-reference/qwen-vl-compatible-with-openai)

## 状态检查与验证

后端启动后提供基础状态检查与进程内指标：

```bash
curl http://127.0.0.1:7860/health
curl http://127.0.0.1:7860/metrics
```

本地测试与构建：

```bash
# 后端单元测试
.venv/bin/python -m pytest -q

# Python 语法编译检查
PYTHONPYCACHEPREFIX=/private/tmp/vlm_pycache python3 -m py_compile app.py src/config.py src/api_client.py

# React 前端构建
cd frontend
npm run build
```

也可以执行项目内聚合检查脚本：

```bash
bash scripts/ci_check.sh
```

## 评测数据集

### 数据集结构

项目包含自建的中文图文问答评测数据集（50-100条），覆盖：
- 自然场景问答（40条）
- 文档图像问答（40条）

### 评测指标

- **准确率**：回答与标准答案的匹配度
- **响应时间**：API调用耗时
- **多轮对话连贯性**：上下文理解准确度

运行评测：
```bash
python evaluation/evaluator.py
```

## 技术架构

```
用户交互层 (React Web UI / Gradio 兼容入口)
    ↓ HTTP / WebSocket
应用服务层 (FastAPI 路由 + Gradio 挂载)
    ↓ 会话、上传、RAG、工具调用
核心业务层 (ChatManager / ImageProcessor / RagManager / VLMAPIClient)
    ↓ OpenAI 兼容协议
模型服务层 (DashScope / OpenAI / OpenRouter / Ollama / 自定义接口)
```

## 常见问题

### 1. API调用失败

- 检查 `DASHSCOPE_API_KEY` 是否正确设置
- 确认API密钥有效且有足够额度
- 检查网络连接

### 2. 图片上传失败

- 确认图片格式为 JPG、PNG 或 WebP
- 图片大小不超过 5MB
- 图片文件完整可读

### 3. 响应时间过长

- 检查网络连接速度
- 确认图片大小适中（过大会增加处理时间）
- 尝试减少问题复杂度

## 许可证

本项目仅供学习和研究使用。

## 参考资料

- [Qwen2.5-VL官方文档](https://qwenlm.github.io/blog/qwen2.5-vl/)
- [阿里云DashScope API文档](https://help.aliyun.com/zh/model-studio/)
- [Gradio官方文档](https://gradio.org.cn/docs/)
