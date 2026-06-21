"""OpenAI 兼容 TTS 服务。

POST /v1/audio/speech —— 返回 24kHz int16 PCM, chunked streaming(边合成边发)。
agent-py 端: tts=openai.TTS(base_url="http://localhost:8001/v1",
                            model="tts-1", voice="0", response_format="pcm")
模型由 .env 的 MODEL_DIR 决定(默认 theresa;可换 aishell3)。voice 传数字字符串可覆盖 speaker sid。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .engine import TTSEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sherpa-voice")

# 模块导入时加载模型(~6s), uvicorn 启动时完成
engine = TTSEngine()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, engine.warmup)
    logger.info(
        "就绪 @ :%d (model %dHz -> %dHz PCM, sid=%d, threads=%d)",
        settings.port,
        engine.source_sample_rate,
        settings.target_sample_rate,
        settings.speaker_id,
        settings.num_threads,
    )
    yield


app = FastAPI(title="sherpa-voice", version="0.1.0", lifespan=lifespan)


class SpeechRequest(BaseModel):
    input: str
    model: str | None = None  # 忽略(openai client 必传; 服务端按 MODEL_DIR 加载)
    voice: str | None = None  # 传数字字符串可覆盖 speaker sid
    response_format: str | None = "pcm"  # 仅支持 pcm
    speed: float | None = None  # 忽略, 用 .env 的 SPEED


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_sr": engine.source_sample_rate,
        "output_sr": settings.target_sample_rate,
    }


@app.get("/v1/models")
async def list_models():
    model_id = settings.model_dir.name  # theresa | aishell3(随 .env 的 MODEL_DIR)
    return {
        "object": "list",
        "data": [{"id": model_id, "object": "model", "owned_by": "sherpa-voice"}],
    }


@app.post("/v1/audio/speech")
async def audio_speech(req: SpeechRequest):
    text = (req.input or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="input 不能为空")

    sid = settings.speaker_id
    if req.voice and str(req.voice).isdigit():
        sid = int(req.voice)

    async def gen() -> AsyncIterator[bytes]:
        async for chunk in engine.synthesize_stream(text, sid=sid):
            yield chunk

    return StreamingResponse(gen(), media_type="audio/pcm")
