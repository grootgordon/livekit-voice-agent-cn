"""standalone:验证火山豆包大模型流式 ASR 的密钥 + 协议(独立于 LiveKit)。

用法(在 agent-py 目录):
  uv run python test_volc_asr.py /path/to/test.wav

wav 建议 16000Hz / 单声道 / 16bit(pcm_s16le)。会逐块推流并打印 interim/final 文本。
需 .env.local 里有 VOLC_ASR_APP_KEY / VOLC_ASR_ACCESS_KEY。
"""

import asyncio
import os
import sys
import wave

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import stt as stt_mod

from src.stt_volcengine import VolcengineSTT

CHUNK_MS = 200


async def main(wav_path: str) -> None:
    load_dotenv(".env.local")
    if not os.environ.get("VOLC_ASR_API_KEY"):
        print("⚠️  请在 .env.local 设置 VOLC_ASR_API_KEY(新版控制台 API Key)")
        sys.exit(1)

    engine = VolcengineSTT(
        api_key=os.environ["VOLC_ASR_API_KEY"],
        resource_id=os.environ.get("VOLC_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration"),
        language="",  # 中英混合自动
    )

    wf = wave.open(wav_path, "rb")
    rate, channels, sw = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
    print(f"wav: rate={rate} ch={channels} sample_width={sw}")
    if rate != 16000 or channels != 1 or sw != 2:
        print("⚠️  建议 16000Hz/单声道/16bit;将尝试由 LiveKit 重采样到 16k。")

    stream = engine.stream()
    frames_per_chunk = max(1, int(rate * CHUNK_MS / 1000))

    async def feed() -> None:
        try:
            while True:
                raw = wf.readframes(frames_per_chunk)
                if not raw:
                    break
                samples = len(raw) // (sw * channels)
                frame = rtc.AudioFrame(
                    data=raw,
                    sample_rate=rate,
                    num_channels=channels,
                    samples_per_channel=samples,
                )
                stream.push_frame(frame)
                await asyncio.sleep(CHUNK_MS / 1000)  # 按真实节奏推流
        finally:
            stream.end_input()

    async def consume() -> None:
        async for ev in stream:
            if ev.type == stt_mod.SpeechEventType.FINAL_TRANSCRIPT:
                print(f"[FINAL]   {ev.alternatives[0].text}")
            elif ev.type == stt_mod.SpeechEventType.INTERIM_TRANSCRIPT:
                print(f"[interim] {ev.alternatives[0].text}")

    await asyncio.gather(feed(), consume())
    await engine.aclose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python test_volc_asr.py <test.wav>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
