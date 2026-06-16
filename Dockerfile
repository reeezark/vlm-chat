# VLM 智能图文问答助手 —— 容器镜像（P1-9）
FROM node:22-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

# 避免交互式提示，确保日志实时输出
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目源码
COPY . .
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# 持久化数据目录（会话数据库 + 上传图片）
RUN mkdir -p data/sessions data/uploads

# 容器内须监听 0.0.0.0 才能对外暴露
ENV GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    FRONTEND_MODE=react

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3).read()" || exit 1

CMD ["python", "app.py"]
