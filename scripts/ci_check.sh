#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

echo "[1/3] 语法编译检查"
"${PYTHON_BIN}" -m py_compile \
  app.py \
  src/api_client.py \
  src/chat_manager.py \
  src/config.py \
  src/embeddings.py \
  src/image_processor.py \
  src/metrics.py \
  src/rag.py \
  src/tools.py

echo "[2/3] 单元测试"
"${PYTHON_BIN}" -m pytest -q --cov=src --cov-report=term-missing

echo "[3/3] 前端构建检查"
if command -v npm >/dev/null 2>&1 && [[ -f "frontend/package.json" ]]; then
  if [[ -f "frontend/package-lock.json" ]]; then
    (cd frontend && npm ci && npm run build)
  else
    (cd frontend && npm install && npm run build)
  fi
else
  echo "未检测到 npm 或 frontend/package.json，跳过前端构建检查"
fi
