#!/usr/bin/env bash
# 启动 sherpa-voice TTS 服务
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8001}"
echo "==> sherpa-voice @ http://0.0.0.0:${PORT}  (模型加载 ~6s + warmup ~1s)"
exec uv run uvicorn app.server:app --host 0.0.0.0 --port "${PORT}"
