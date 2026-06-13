#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

echo "[1/2] 语法编译检查"
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

echo "[2/2] 单元测试"
"${PYTHON_BIN}" -m pytest -q --cov=src --cov-report=term-missing
