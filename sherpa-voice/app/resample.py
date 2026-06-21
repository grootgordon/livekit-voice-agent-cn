"""重采样 + 音量处理 + PCM 编码。

aishell3 原始 8kHz, openai.TTS 固定 24kHz → 需上采样(3×)。
8kHz→24kHz 是上采样, 线性插值即可(源已无更高频信息, 不引入额外损失)。
"""

from __future__ import annotations

import numpy as np


def resample(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """线性插值重采样。"""
    if src_sr == dst_sr:
        return np.asarray(samples, dtype=np.float32)
    n_src = len(samples)
    if n_src == 0:
        return np.zeros(0, dtype=np.float32)
    n_dst = int(round(n_src * dst_sr / src_sr))
    idx = np.linspace(0, n_src - 1, n_dst)
    return np.interp(idx, np.arange(n_src), samples).astype(np.float32)


def to_int16_bytes(samples: np.ndarray) -> bytes:
    """float32(-1~1, 越界 clip) → 小端 int16 PCM bytes。"""
    arr = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    return (arr * 32767).astype("<i2").tobytes()
