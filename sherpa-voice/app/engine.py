"""sherpa-onnx OfflineTts 单例, 线程安全合成 + callback 流式。

OfflineTts.generate 的线程安全性未文档化, 用 asyncio.Lock 串行化(单用户对话足够)。
合成在 executor 线程跑, callback 在该线程触发, 经 loop.call_soon_threadsafe 把音频块
推回 async 循环 → 真·边合成边发, 降低首字延迟。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import numpy as np
import sherpa_onnx

from . import resample as rsp
from .config import settings

logger = logging.getLogger("sherpa-voice")


class TTSEngine:
    def __init__(self) -> None:
        d = settings.model_dir_abs
        # 自动定位主模型(排除 int8 量化版),兼容 aishell3(model.onnx)与 theresa(theresa.onnx)
        onnx = [f for f in sorted(d.glob("*.onnx")) if "int8" not in f.name]
        if not onnx:
            raise FileNotFoundError(f"模型目录无 .onnx 文件: {d}")
        model_path = onnx[0]
        vits_kwargs: dict = {
            "model": str(model_path),
            "lexicon": str(d / "lexicon.txt"),
            "tokens": str(d / "tokens.txt"),
        }
        if (d / "dict").is_dir():  # theresa 等 jieba 中文模型需要; aishell3/icefall 无
            vits_kwargs["dict_dir"] = str(d / "dict")
        logger.info("加载模型: %s (dict_dir=%s)", model_path.name, (d / "dict").is_dir())
        vits = sherpa_onnx.OfflineTtsVitsModelConfig(**vits_kwargs)
        cfg = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=vits,
                num_threads=settings.num_threads,
                provider="cpu",
            )
        )
        t0 = time.perf_counter()
        self._tts = sherpa_onnx.OfflineTts(cfg)
        logger.info("模型加载 %.2fs (%s)", time.perf_counter() - t0, d)
        # aishell3 = 8000
        self._src_sr = int(getattr(self._tts, "sample_rate", 8000))
        self._lock = asyncio.Lock()
        self._warmed = False

    @property
    def source_sample_rate(self) -> int:
        return self._src_sr

    def warmup(self) -> None:
        """启动时跑一次推理, 消除 ONNX Runtime 首次推理的预热开销。"""
        if self._warmed:
            return
        t0 = time.perf_counter()
        self._tts.generate("预热", sid=settings.speaker_id, speed=1.0)
        logger.info("warmup %.2fs", time.perf_counter() - t0)
        self._warmed = True

    async def synthesize_stream(
        self, text: str, *, sid: int | None = None
    ) -> AsyncIterator[bytes]:
        """流式合成一句, 边生成边 yield 目标采样率的 int16 PCM 字节块。"""
        if sid is None:
            sid = settings.speaker_id

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | Exception | None] = asyncio.Queue()

        def _on_chunk(samples: np.ndarray, _progress: float) -> int:
            block = np.asarray(samples, dtype=np.float32)
            if settings.normalize_volume:
                block = block * settings.normalize_gain
            block = rsp.resample(block, self._src_sr, settings.target_sample_rate)
            loop.call_soon_threadsafe(queue.put_nowait, rsp.to_int16_bytes(block))
            return 1

        def _work() -> None:
            try:
                self._tts.generate(
                    text, sid=sid, speed=settings.speed, callback=_on_chunk
                )
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as exc:  # noqa: BLE001
                logger.exception("合成失败")
                loop.call_soon_threadsafe(queue.put_nowait, exc)

        async with self._lock:
            loop.run_in_executor(None, _work)
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
