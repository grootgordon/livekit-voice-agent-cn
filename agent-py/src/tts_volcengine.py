"""火山引擎「豆包语音合成大模型 2.0」双向流式 TTS(新版控制台接口)。

封装 WebSocket 双向流式协议(`wss://openspeech.bytedance.com/api/v3/tts/bidirection`),
适配 LiveKit 的流式 TTS 接口(tts.TTS / tts.SynthesizeStream)。模式参考官方
`livekit-plugins-minimax`(同为 WebSocket 流式 TTS)与本仓 `stt_volcengine.py`。

为什么不用插件 / 老版接口:
- 官方无 volcengine TTS 插件(PyPI 的 livekit-plugins-volcengine 是第三方,且多半走老版 appid);
- 新版控制台**仅需 X-Api-Key**(无 AppID / Access Token / Cluster),与 `stt_volcengine.py` 同款鉴权;
- 双向流式:文本可流式喂(TaskRequest 多次)、音频流式回(TTSResponse 边合成边发),低首字延迟。

协议要点(官方规格 + 运行依赖 `protocols_.py`):
- 鉴权:WebSocket 握手 HTTP 头 X-Api-Key / X-Api-Resource-Id(seed-tts-2.0)/ X-Api-Connect-Id
- 二进制分帧(大端):4B header + (event int32,当 flag=WithEvent) + (session_id,非连接类事件) + payload
  header 4 nibble 对:[protocol_ver|header_size][msg_type|flags][serialization|compression][reserved]
- 交互:StartConnection(1)→ConnectionStarted(50)→StartSession(100,带 speaker+audio_params)→
  SessionStarted(150)→TaskRequest(200,带 text,可多次)→TTSResponse(352,AudioOnlyServer=裸 PCM)
  /TTSSentenceEnd(351)→FinishSession(102)→SessionFinished(152)→FinishConnection(2)
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import struct
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import aiohttp

from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)

logger = logging.getLogger(__name__)


def _dbg(msg: str) -> None:
    """VOLC_TTS_DEBUG=1 时把协议交互详情打到 stderr,排查「无音频」等问题。"""
    if os.environ.get("VOLC_TTS_DEBUG"):
        import sys as _sys

        print(f"[volc-tts] {msg}", file=_sys.stderr, flush=True)

# 默认走「双向流式」(文本流式输入 / 音频流式输出,低时延)
DEFAULT_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
# 新版控制台大模型语音合成;复刻音色用 seed-icl-2.0
DEFAULT_RESOURCE_ID = "seed-tts-2.0"
# standard=低时延;expressive=高表现力(支持语音指令 context_texts / use_tag_parser)
DEFAULT_MODEL = "seed-tts-2.0-standard"
# 双向流式 JSON payload 必填 namespace(见官方 protocols / volcengine-audio)
_BIDIRECTION_NAMESPACE = "BidirectionalTTS"

_RECV_DRAIN_TIMEOUT = 10.0  # FinishSession 后等音频收尾
_TEXT_SETTLE_S = 3.0  # 发 FinishSession 前等服务器开始合成的上限(竞态兜底)
_WS_HEARTBEAT = 20.0


# ════════════════════════════════════════════════════════════════════════════
# 协议层:vendor 自火山官方「TTS Websocket Bidirection protocols」参考实现
# (纯 Python,无 WebSocket 库依赖;WS 传输由下方 aiohttp 适配)。
# ════════════════════════════════════════════════════════════════════════════


class MsgType(IntEnum):
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111


class MsgTypeFlagBits(IntEnum):
    NoSeq = 0
    PositiveSeq = 0b1
    LastNoSeq = 0b10
    NegativeSeq = 0b11
    WithEvent = 0b100  # payload 前含 event int32


class SerializationBits(IntEnum):
    Raw = 0
    JSON = 0b1


class CompressionBits(IntEnum):
    None_ = 0
    Gzip = 0b1


class EventType(IntEnum):
    None_ = 0
    # 上行 连接类
    StartConnection = 1
    FinishConnection = 2
    # 下行 连接类
    ConnectionStarted = 50
    ConnectionFailed = 51
    ConnectionFinished = 52
    # 上行 会话类
    StartSession = 100
    CancelSession = 101
    FinishSession = 102
    # 下行 会话类
    SessionStarted = 150
    SessionCanceled = 151
    SessionFinished = 152
    SessionFailed = 153
    # 上行 数据类
    TaskRequest = 200
    # 下行 TTS 数据类
    TTSSentenceStart = 350
    TTSSentenceEnd = 351
    TTSResponse = 352
    TTSSubtitle = 364


# 连接类事件不写 session_id(见 Message.marshal / from_bytes)
_CONNECTION_EVENTS_NO_SESSION = {
    EventType.StartConnection,
    EventType.FinishConnection,
    EventType.ConnectionStarted,
    EventType.ConnectionFailed,
    EventType.ConnectionFinished,
}
# 仅这些连接类下行事件带 connect_id
_EVENTS_WITH_CONNECT_ID = {
    EventType.ConnectionStarted,
    EventType.ConnectionFailed,
    EventType.ConnectionFinished,
}


@dataclass
class Message:
    """火山双向流式二进制帧。

    header(4B,大端):
      [version(4)|header_size(4)][msg_type(4)|flag(4)][serialization(4)|compression(4)][reserved(8)]
    flag=WithEvent 时:payload 前有 event(int32);非连接类事件还带 session_id(uint32 len + bytes);
    连接类下行(ConnectionStarted/Failed/Finished)还带 connect_id。
    最后是 payload(uint32 len + bytes)。
    """

    version: int = 1
    header_size: int = 1  # 1 → 4 字节头
    type: MsgType = MsgType.Invalid
    flag: MsgTypeFlagBits = MsgTypeFlagBits.NoSeq
    serialization: SerializationBits = SerializationBits.JSON
    compression: CompressionBits = CompressionBits.None_

    event: Any = EventType.None_
    session_id: str = ""
    connect_id: str = ""
    error_code: int = 0
    payload: bytes = b""

    def marshal(self) -> bytes:
        buf = io.BytesIO()
        header = bytes(
            [
                (self.version << 4) | self.header_size,
                (int(self.type) << 4) | int(self.flag),
                (int(self.serialization) << 4) | int(self.compression),
                0,
            ]
        )
        buf.write(header)

        if self.flag == MsgTypeFlagBits.WithEvent:
            buf.write(struct.pack(">i", int(self.event)))
            # 连接类事件不带 session_id
            if self.event not in _CONNECTION_EVENTS_NO_SESSION:
                sid = self.session_id.encode("utf-8")
                buf.write(struct.pack(">I", len(sid)))
                buf.write(sid)
        buf.write(struct.pack(">I", len(self.payload)))
        buf.write(self.payload)
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 4:
            raise ValueError(f"帧过短: {len(data)} 字节")
        m = cls()
        m.version = data[0] >> 4
        m.header_size = data[0] & 0x0F
        m.type = MsgType(data[1] >> 4)
        m.flag = MsgTypeFlagBits(data[1] & 0x0F)
        m.serialization = SerializationBits(data[2] >> 4)
        m.compression = CompressionBits(data[2] & 0x0F)
        off = 4 * m.header_size  # 本接口固定 4 字节头

        def read_int32() -> int:
            nonlocal off
            v = struct.unpack_from(">i", data, off)[0]
            off += 4
            return v

        def read_uint32() -> int:
            nonlocal off
            v = struct.unpack_from(">I", data, off)[0]
            off += 4
            return v

        def read_str(n: int) -> str:
            nonlocal off
            s = data[off : off + n].decode("utf-8", errors="replace")
            off += n
            return s

        if m.type == MsgType.Error:
            m.error_code = read_uint32()
            plen = read_uint32()
            m.payload = data[off : off + plen]
            return m

        if m.flag == MsgTypeFlagBits.WithEvent:
            ev = read_int32()
            try:
                m.event = EventType(ev)
            except ValueError:
                m.event = ev
            if m.event not in _CONNECTION_EVENTS_NO_SESSION:
                slen = read_uint32()
                if slen:
                    m.session_id = read_str(slen)
            if m.event in _EVENTS_WITH_CONNECT_ID:
                clen = read_uint32()
                if clen:
                    m.connect_id = read_str(clen)

        plen = read_uint32()
        m.payload = data[off : off + plen]
        return m


# ════════════════════════════════════════════════════════════════════════════
# LiveKit TTS 适配
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class _TTSOptions:
    endpoint: str = DEFAULT_ENDPOINT
    api_key: str = ""
    resource_id: str = DEFAULT_RESOURCE_ID
    speaker: str = ""
    model: str = DEFAULT_MODEL
    sample_rate: int = 24000  # LiveKit / openai.TTS / agent 链路固定 24kHz
    format: str = "pcm"


class VolcengineTTS(tts.TTS):
    """火山豆包语音合成大模型 2.0(双向流式)。"""

    def __init__(
        self,
        *,
        api_key: str,
        speaker: str,
        resource_id: str = DEFAULT_RESOURCE_ID,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        sample_rate: int = 24000,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True, aligned_transcript=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        if not api_key:
            raise ValueError("需要提供 api_key(新版控制台 X-Api-Key)")
        if not speaker:
            raise ValueError(
                "需要提供 speaker(音色 ID,从控制台 > 音色库获取)"
                " https://console.volcengine.com/speech/new/voices"
            )
        self._opts = _TTSOptions(
            endpoint=endpoint,
            api_key=api_key,
            resource_id=resource_id,
            speaker=speaker,
            model=model,
            sample_rate=sample_rate,
        )
        self._http_session = http_session

    @property
    def label(self) -> str:
        return f"Volcengine TTS ({self._opts.resource_id})"

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "volcengine"

    async def aclose(self) -> None:
        if self._http_session:
            await self._http_session.close()

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        # 流式 provider:用基类助手把 stream() 包成一次性 ChunkedStream
        return self._synthesize_with_stream(text=text, conn_options=conn_options)

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "VolcengineSynthesizeStream":
        return VolcengineSynthesizeStream(tts=self, conn_options=conn_options)


class VolcengineSynthesizeStream(tts.SynthesizeStream):
    def __init__(self, *, tts: VolcengineTTS, conn_options: APIConnectOptions):
        super().__init__(tts=tts, conn_options=conn_options)
        self._volc_tts: VolcengineTTS = tts
        self._opts = tts._opts
        self._synth_started = asyncio.Event()  # 服务器开始合成(收 350/352)后 set

    # ── 帧构造 ──────────────────────────────────────────────────────────
    def _build_control(
        self, *, event: EventType, session_id: str = "", payload: bytes = b"{}"
    ) -> bytes:
        m = Message(
            type=MsgType.FullClientRequest,
            flag=MsgTypeFlagBits.WithEvent,
            serialization=SerializationBits.JSON,
            compression=CompressionBits.None_,
        )
        m.event = event
        m.session_id = session_id
        m.payload = payload
        out = m.marshal()
        _dbg(f"send event={event.name} sid={session_id!r} payload={payload[:100]!r}")
        return out

    def _audio_params(self) -> dict[str, Any]:
        return {
            "format": self._opts.format,
            "sample_rate": self._opts.sample_rate,
        }

    def _session_payload(self, *, user_uid: str) -> bytes:
        req = {
            "namespace": _BIDIRECTION_NAMESPACE,
            "event": int(EventType.StartSession),
            "user": {"uid": user_uid},
            "req_params": {
                "speaker": self._opts.speaker,
                "model": self._opts.model,
                "audio_params": self._audio_params(),
            },
        }
        return json.dumps(req, ensure_ascii=False).encode("utf-8")

    def _task_payload(self, text: str) -> bytes:
        req = {
            "namespace": _BIDIRECTION_NAMESPACE,
            "event": int(EventType.TaskRequest),
            "req_params": {
                "text": text,
                "speaker": self._opts.speaker,
                "audio_params": self._audio_params(),
            },
        }
        return json.dumps(req, ensure_ascii=False).encode("utf-8")

    # ── 握手:等指定事件 ────────────────────────────────────────────────
    async def _await_event(
        self, ws: aiohttp.ClientWebSocketResponse, expected: EventType
    ) -> Message:
        while True:
            msg = await ws.receive()
            if msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
            ):
                raise APIConnectionError(
                    f"火山 TTS 握手阶段连接关闭 (close_code={ws.close_code})"
                )
            if msg.type != aiohttp.WSMsgType.BINARY:
                continue
            m = Message.from_bytes(bytes(msg.data))
            _dbg(f"recv(握手) type={m.type.name} event={m.event} sid={m.session_id!r} cid={m.connect_id!r} payload({len(m.payload)})={m.payload[:100]!r}")
            if m.type == MsgType.Error:
                raise APIStatusError(
                    message=f"火山 TTS 错误 code={m.error_code}: "
                    f"{m.payload.decode('utf-8', errors='replace')}",
                    status_code=500,
                    request_id=None,
                    body=m.payload,
                )
            if m.event == expected:
                return m
            if m.event in (EventType.ConnectionFailed, EventType.SessionFailed):
                raise APIStatusError(
                    message=f"火山 TTS {m.event.name}: "
                    f"{m.payload.decode('utf-8', errors='replace')}",
                    status_code=500,
                    request_id=None,
                    body=m.payload,
                )

    # ── 接收循环(合成阶段) ─────────────────────────────────────────────
    @utils.log_exceptions()
    async def _recv_loop(
        self, ws: aiohttp.ClientWebSocketResponse, output_emitter: tts.AudioEmitter
    ) -> None:
        while True:
            msg = await ws.receive()
            if msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
            ):
                return
            if msg.type != aiohttp.WSMsgType.BINARY:
                continue

            m = Message.from_bytes(bytes(msg.data))
            _dbg(f"recv type={m.type.name} event={m.event} flag={m.flag} sid={m.session_id!r} errcode={m.error_code} payload({len(m.payload)})={m.payload[:120]!r}")
            if m.type == MsgType.Error:
                raise APIStatusError(
                    message=f"火山 TTS 错误 code={m.error_code}: "
                    f"{m.payload.decode('utf-8', errors='replace')}",
                    status_code=500,
                    request_id=None,
                    body=m.payload,
                )
            if m.type == MsgType.AudioOnlyServer:
                # TTSResponse(352):裸 PCM,直接推
                if m.payload:
                    self._synth_started.set()
                    output_emitter.push(m.payload)
            elif m.type == MsgType.FullServerResponse:
                if m.event == EventType.TTSSentenceStart:
                    self._synth_started.set()
                elif m.event == EventType.TTSSentenceEnd:
                    output_emitter.flush()
                elif m.event == EventType.SessionFinished:
                    output_emitter.end_input()
                    return
                # TTSSentenceStart / TTSSubtitle / SessionStarted 等:忽略

    # ── 主循环 ──────────────────────────────────────────────────────────
    @utils.log_exceptions()
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._opts.sample_rate,
            num_channels=1,
            mime_type=f"audio/{self._opts.format}",
            stream=True,
        )

        session_id = str(uuid.uuid4())
        connect_id = str(uuid.uuid4())
        user_uid = str(uuid.uuid4())
        headers = {
            "X-Api-Key": self._opts.api_key,
            "X-Api-Resource-Id": self._opts.resource_id,
            "X-Api-Connect-Id": connect_id,
        }

        own_session = self._volc_tts._http_session is None
        http_session = self._volc_tts._http_session or aiohttp.ClientSession()
        try:
            try:
                ws = await asyncio.wait_for(
                    http_session.ws_connect(
                        self._opts.endpoint, headers=headers, heartbeat=_WS_HEARTBEAT
                    ),
                    timeout=self._conn_options.timeout,
                )
            except asyncio.TimeoutError as e:
                raise APITimeoutError("火山 TTS WebSocket 连接超时") from e
            except Exception as e:
                raise APIConnectionError(f"火山 TTS 连接失败: {e}") from e

            try:
                # StartConnection → ConnectionStarted
                await ws.send_bytes(
                    self._build_control(event=EventType.StartConnection)
                )
                await self._await_event(ws, EventType.ConnectionStarted)

                # StartSession → SessionStarted
                await ws.send_bytes(
                    self._build_control(
                        event=EventType.StartSession,
                        session_id=session_id,
                        payload=self._session_payload(user_uid=user_uid),
                    )
                )
                await self._await_event(ws, EventType.SessionStarted)
                output_emitter.start_segment(segment_id=session_id)

                # 并发:收音频 + 发文本
                recv_task = asyncio.create_task(self._recv_loop(ws, output_emitter))
                try:
                    async for data in self._input_ch:
                        if isinstance(data, self._FlushSentinel):
                            output_emitter.flush()
                            continue
                        await ws.send_bytes(
                            self._build_control(
                                event=EventType.TaskRequest,
                                session_id=session_id,
                                payload=self._task_payload(data),
                            )
                        )
                finally:
                    # 等(最多 _TEXT_SETTLE_S)服务器开始合成再发 FinishSession,
                    # 否则 TaskRequest 与 FinishSession 背靠背会触发空句子 flush(竞态)。
                    try:
                        await asyncio.wait_for(
                            self._synth_started.wait(), timeout=_TEXT_SETTLE_S
                        )
                    except asyncio.TimeoutError:
                        _dbg("synth_started 超时,仍发 FinishSession")
                    # FinishSession,等音频收尾(SessionFinished)
                    try:
                        await ws.send_bytes(
                            self._build_control(
                                event=EventType.FinishSession, session_id=session_id
                            )
                        )
                    except Exception:
                        pass
                    try:
                        await asyncio.wait_for(
                            recv_task, timeout=_RECV_DRAIN_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        await utils.aio.gracefully_cancel(recv_task)
            finally:
                try:
                    await ws.send_bytes(
                        self._build_control(event=EventType.FinishConnection)
                    )
                except Exception:
                    pass
                try:
                    await ws.close()
                except Exception:
                    pass
        finally:
            if own_session:
                try:
                    await http_session.close()
                except Exception:
                    pass
