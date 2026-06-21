"""配置: 从 .env / 环境变量读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


def _bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    port: int = int(os.environ.get("PORT", "8001"))
    model_dir: Path = Path(os.environ.get("MODEL_DIR", "models/theresa"))
    num_threads: int = int(os.environ.get("NUM_THREADS", "4"))
    target_sample_rate: int = int(os.environ.get("TARGET_SAMPLE_RATE", "24000"))
    speaker_id: int = int(os.environ.get("SPEAKER_ID", "0"))
    normalize_volume: bool = _bool(os.environ.get("NORMALIZE_VOLUME"), True)
    normalize_gain: float = float(os.environ.get("NORMALIZE_GAIN", "1.0"))
    speed: float = float(os.environ.get("SPEED", "1.0"))

    @property
    def model_dir_abs(self) -> Path:
        p = self.model_dir
        return p if p.is_absolute() else (ROOT / p).resolve()


settings = Settings()
