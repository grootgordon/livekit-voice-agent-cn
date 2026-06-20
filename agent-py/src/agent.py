"""LiveKit 语音 agent(国内模型生态)。

STT=火山豆包大模型流式 ASR(自定义)、LLM=DeepSeek、TTS=MiniMax、
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
    tts_kwargs: dict = {}
    if os.environ.get("MINIMAX_VOICE"):  # 可选:覆盖默认音色
        tts_kwargs["voice"] = os.environ["MINIMAX_VOICE"]

    session = AgentSession(
        stt=VolcengineSTT(
            api_key=os.environ["VOLC_ASR_API_KEY"],  # 新版控制台 API Key
            resource_id=os.environ.get(
                "VOLC_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration"
            ),
            language="",  # 留空 → 中英文+方言自动识别(中英混合)
        ),
        llm=openai.LLM.with_deepseek(model="deepseek-chat"),
        # 自动读 MINIMAX_API_KEY 与 MINIMAX_BASE_URL(国内 https://api.minimaxi.com)
        # 用 pcm 直传:避免 mp3 流式分帧在 PyAV 解码时偶发 InvalidDataError→SIGSEGV
        tts=minimax.TTS(audio_format="pcm", sample_rate=24000, **tts_kwargs),
        # 用火山 STT 的 definite utterance → END_OF_SPEECH,不用 v1-mini 本地 EOT。
        # v1-mini(livekit.local_inference 原生库)在部分 macOS 上与 TTS 并发时会 SIGSEGV,
        # 前端表现为 "Agent left the room unexpectedly"。
        turn_handling=TurnHandlingOptions(turn_detection="stt"),
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.generate_reply(instructions="用中文友好地问候用户,并询问能帮什么忙。")


if __name__ == "__main__":
    agents.cli.run_app(server)
