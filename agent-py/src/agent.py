"""LiveKit 语音 agent(国内模型生态)。

STT=火山豆包大模型流式 ASR(自定义)、LLM=DeepSeek、TTS=sherpa-voice(本地)/MiniMax/火山、
话轮检测=STT 端点(火山 definite utterance)。全程不依赖 LiveKit Inference,
故在本地 LiveKit Server 上也能真实对话(中英混合)。

传输层(Cloud⇄本地)由仓库根 .livekit.env 的 LIVEKIT_PROFILE 决定。
"""

import faulthandler
import os

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
)
from livekit.plugins import minimax, openai

from livekit_profile import resolve_livekit_profile
from stt_volcengine import VolcengineSTT
from tts_volcengine import VolcengineTTS

load_dotenv(".env.local")
resolve_livekit_profile()  # transport: cloud | local(根 .livekit.env)
faulthandler.enable()  # 原生段错误(exit -11)时打印 C 栈,便于定位 av/onnx 崩溃


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "你是一个友好、高效的语音助手。用简洁的中文回答,可以夹杂必要的英文术语。"
                "不要使用 emoji、星号或复杂排版。如果用户用英文提问,可以用英文回答。"
            ),
        )


server = AgentServer()


@server.rtc_session(agent_name="my-agent")  # 需与前端 VITE_AGENT_NAME 一致
async def entry(ctx: agents.JobContext) -> None:
    # TTS provider 切换:sherpa(本地,默认)/ minimax(云端)/ volc(火山大模型 2.0,需 X-Api-Key)。
    # 详见 ../sherpa-voice 与 tts_volcengine.py。
    provider = os.environ.get("TTS_PROVIDER", "sherpa")
    if provider == "minimax":
        _voice = os.environ.get("MINIMAX_VOICE")  # 可选:覆盖默认音色
        tts = minimax.TTS(
            audio_format="pcm", sample_rate=24000,
            **({"voice": _voice} if _voice else {}),
        )
    elif provider == "volc":
        # 火山豆包语音合成大模型 2.0(双向流式);新版控制台仅需 X-Api-Key。
        # 与 STT 共用同一个 VOLC_ASR_API_KEY(新版控制台 key 需同时开通语音识别 + 语音合成大模型)。
        # VOLC_TTS_VOICE 必填:控制台>音色库的 seed-tts-2.0 音色 ID。
        tts = VolcengineTTS(
            api_key=os.environ["VOLC_ASR_API_KEY"],
            speaker=os.environ["VOLC_TTS_VOICE"],
            resource_id=os.environ.get("VOLC_TTS_RESOURCE_ID", "seed-tts-2.0"),
            model=os.environ.get("VOLC_TTS_MODEL", "seed-tts-2.0-standard"),
        )
    else:
        # openai.TTS 指向本地 OpenAI 兼容服务;openai 插件固定 sample_rate=24000,
        # 故 sherpa-voice 必须输出 24kHz PCM(已在其 engine 里源采样率→24kHz 重采样)。
        tts = openai.TTS(
            base_url=os.environ.get("SHERPA_VOICE_URL", "http://localhost:8001/v1"),
            model="tts-1",  # 让 openai 插件走 AudioChunkedStream(iter_bytes 读 raw PCM);服务端忽略 model
            voice=os.environ.get("SHERPA_VOICE", "0"),  # theresa 单说话人留 0;换 aishell3 则 sid 0-173
            response_format="pcm",  # 避免 mp3 在 PyAV 解码偶发 SIGSEGV
            api_key="not-needed",
        )

    session = AgentSession(
        stt=VolcengineSTT(
            api_key=os.environ["VOLC_ASR_API_KEY"],  # 新版控制台 API Key
            resource_id=os.environ.get(
                "VOLC_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration"
            ),
            language="",  # 留空 → 中英文+方言自动识别(中英混合)
        ),
        llm=openai.LLM.with_deepseek(model="deepseek-chat"),
        tts=tts,
        # 用火山 STT 的 definite utterance → END_OF_SPEECH,不用 v1-mini 本地 EOT。
        # v1-mini(livekit.local_inference 原生库)在部分 macOS 上与 TTS 并发时会 SIGSEGV,
        # 前端表现为 "Agent left the room unexpectedly"。
        turn_handling=TurnHandlingOptions(turn_detection="stt"),
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.generate_reply(instructions="用中文友好地问候用户,并询问能帮什么忙。")


if __name__ == "__main__":
    agents.cli.run_app(server)
