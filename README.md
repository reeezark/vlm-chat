# 基于VLM的智能图文问答助手

## 项目简介

本项目是一个基于视觉语言模型（VLM）的智能图文问答助手，支持"看图/看文档能聊天"的多模态交互。用户可以上传图片（自然场景或文档）并提出问题，助手会基于图片内容进行中文问答和基础推理。

### 核心功能

- 📷 **多模态输入**：支持上传图片（自然场景、文档截图）+ 文本问题
- 💬 **多轮对话**：支持上下文记忆和追问功能
- 🧠 **中文问答**：针对中文图文内容进行准确问答
- 🔍 **基础推理**：实现简单的逻辑推理能力
- 🖥️ **Web UI**：提供友好的交互界面

### 技术栈

| 技术维度 | 选择方案 | 说明 |
|---------|---------|------|
| **视觉语言模型** | Qwen-VL-Plus | 阿里云DashScope API调用 |
| **前端框架** | Gradio 4.x | 快速搭建交互界面 |
| **API接口** | OpenAI兼容接口 | 简化调用逻辑 |
| **图片处理** | Pillow | 图片格式验证和处理 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API密钥

本项目使用阿里云DashScope API，需要设置环境变量：

**Windows:**
```bash
set DASHSCOPE_API_KEY=your-api-key
```

**Linux/Mac:**
```bash
export DASHSCOPE_API_KEY=your-api-key
```

获取API密钥：访问 [阿里云百炼平台](https://help.aliyun.com/zh/model-studio/getting-started/get-api-key)

### 3. 运行应用

```bash
python app.py
```

应用启动后，访问 `http://localhost:7860` 即可使用。

## 项目结构

```
vlm-chat-assistant/
│
├── app.py                    # 主应用入口（Gradio界面）
├── requirements.txt          # 项目依赖
├── README.md                 # 项目说明文档
│
├── src/
│   ├── __init__.py           # 模块初始化
│   ├── config.py             # 配置文件（API密钥、模型名称）
│   ├── api_client.py         # DashScope API调用封装
│   ├── chat_manager.py       # 会话管理（上下文维护）
│   ├── image_processor.py    # 图片预处理
│
├── data/
│   ├── test_images/          # 测试图片目录
│   │   ├── natural_scene/    # 自然场景图片
│   │   ├── document/         # 文档图片
│   ├── temp_images/          # 临时图片存储
│   ├── evaluation_dataset.json # 评测数据集
│
├── evaluation/
│   ├── evaluator.py          # 评测脚本
│   ├── evaluation_report.md  # 评测结果报告
│
└── static/
    └── examples/             # 示例图片
```

## 使用说明

### 图片问答

1. 上传图片（支持 JPG、PNG、WebP 格式，最大 5MB）
2. 输入问题（如："这张图片里有什么？"）
3. 点击提交，等待模型回复
4. 可以继续追问（无需再次上传图片）

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

本项目使用阿里云DashScope的OpenAI兼容接口：

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
用户交互层 (Gradio Web UI)
    ↓ HTTP/WebSocket
应用逻辑层 (Gradio Backend)
    ↓ API调用
模型服务层 (阿里云DashScope API)
    ↓ Qwen-VL-Plus
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