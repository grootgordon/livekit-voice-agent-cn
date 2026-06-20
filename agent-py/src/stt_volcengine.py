"""火山引擎「豆包大模型流式语音识别」自定义 STT。

封装双向流式 WebSocket 协议(`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`),
适配 LiveKit 的流式 STT 接口(stt.STT / stt.SpeechStream)。模式参考官方
`livekit-plugins-rtzr`(同为 WebSocket 流式 STT)。

协议要点(官方文档 https://www.volcengine.com/docs/6561/1354869):
- 鉴权:WebSocket 握手 HTTP 头 X-Api-App-Key / X-Api-Access-Key / X-Api-Resource-Id / X-Api-Connect-Id
- 二进制分帧(大端):4B header + (seq 4B 仅响应) + payload_size 4B + payload
  header 4 nibble 对:[protocol_ver|header_size][msg_type|flags][serialization|compression][reserved]
- 首帧 full client request(JSON + gzip);后续 audio only(裸 PCM + gzip,末包 flags=0b0010)
- 响应 full server response:gzip JSON,含 result.text / result.utterances[].definite
- 中英混合:双向流式 bigmodel 默认即支持(language 留空 → 中英文+方言自动)
"""

from __future__ import annotations

import asyncio
import gzip
import json
import uuid
from dataclasses import dataclass

import aiohttp

from livekit import rtc
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    LanguageCode,
    stt,
    utils,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr

# 默认走「双向流式优化版」(仅结果变化时返回,RTF/首字时延更优)
DEFAULT_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
# 豆包流式语音识别模型 1.0 小时版;2.0 用 volc.seedasr.sauc.duration
DEFAULT_RESOURCE_ID = "volc.bigasr.sauc.duration"
DEFAULT_MODEL_NAME = "bigmodel"

_DEFAULT_CHUNK_MS = 200  # 双向流式模式 200ms 单包性能最优
_IDLE_TIMEOUT_SECONDS = 25.0
_RECV_COMPLETION_TIMEOUT = 5.0
_IDLE_CHECK_INTERVAL = 1.0

# ── 协议常量 ──────────────────────────────────────────────────────────────
PROTOCOL_VERSION = 0x1
HEADER_SIZE = 0x1  # 1 * 4 = 4 字节

# message type
MSG_FULL_CLIENT_REQUEST = 0x1
MSG_AUDIO_ONLY = 0x2
MSG_FULL_SERVER_RESPONSE = 0x9
MSG_ERROR = 0xF

# message type specific flags
FLAG_NO_SEQ = 0x0
FLAG_POS_SEQ = 0x1
FLAG_LAST_NO_SEQ = 0x2  # 最后一包(音频结束)
FLAG_LAST_NEG_SEQ = 0x3

# serialization
SER_NONE = 0x0
SER_JSON = 0x1

# compression
COMP_NONE = 0x0
COMP_GZIP = 0x1


def _header(msg_type: int, flags: int, serialization: int, compression: int) -> bytes:
    b0 = (PROTOCOL_VERSION << 4) | HEADER_SIZE
    b1 = (msg_type << 4) | flags
    b2 = (serialization << 4) | compression
    b3 = 0x00
    return bytes([b0, b1, b2, b3])


def _frame(header: bytes, payload: bytes, compress: bool = True) -> bytes:
    body = gzip.compress(payload) if compress else payload
    return header + len(body).to_bytes(4, "big") + body


@dataclass
class _STTOptions:
    endpoint: str = DEFAULT_ENDPOINT
    api_key: str = ""  # 新版控制台 API Key(X-Api-Key)
    resource_id: str = DEFAULT_RESOURCE_ID
    model_name: str = DEFAULT_MODEL_NAME
    format: str = "pcm"  # pcm / wav / ogg / mp3(内部需 pcm_s16le)
    rate: int = 16000
    bits: int = 16
    channel: int = 1
    language: str = ""  # 留空 → 中英文+方言自动(中英混合)
    enable_itn: bool = True
    enable_punc: bool = True
    show_utterances: bool = True
    result_type: str = "single"  # single=增量(仅当前句),更贴合 LiveKit
    end_window_size: int = 800  # 静音超过该值(ms)判停出 definite
    chunk_ms: int = _DEFAULT_CHUNK_MS


class VolcengineSTT(stt.STT):
    """火山豆包大模型流式 ASR。"""

    def __init__(
        self,
        *,
        api_key: str,
        resource_id: str = DEFAULT_RESOURCE_ID,
        endpoint: str = DEFAULT_ENDPOINT,
        model_name: str = DEFAULT_MODEL_NAME,
        language: str = "",
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=True,
                interim_results=True,
                offline_recognize=False,
            )
        )
        if not api_key:
            raise ValueError("需要提供 api_key(新版控制台 API Key)")
        self._params = _STTOptions(
            endpoint=endpoint,
            api_key=api_key,
            resource_id=resource_id,
            model_name=model_name,
            language=language,
        )
        self._http_session = http_session

    @property
    def model(self) -> str:
        return self._params.model_name

    @property
    def provider(self) -> str:
        return "volcengine"

    async def aclose(self) -> None:
        if self._http_session:
            await self._http_session.close()

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        raise NotImplementedError("单次识别不支持,请用 stream()。")

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SpeechStream":
        return SpeechStream(stt=self, conn_options=conn_options)


class SpeechStream(stt.SpeechStream):
    def __init__(self, *, stt: VolcengineSTT, conn_options: APIConnectOptions) -> None:
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=stt._params.rate)
        self._volc_stt: VolcengineSTT = stt
        self._opts = stt._params
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._owns_session = False
        self._recv_task: asyncio.Task[None] | None = None
        self._seq = 0  # 音频包序号(正序,递增)
        self._sent_full_request = False

    # ── 连接 ────────────────────────────────────────────────────────────
    def _build_full_request_payload(self) -> bytes:
        audio_cfg: dict = {
            "format": self._opts.format,
            "rate": self._opts.rate,
            "bits": self._opts.bits,
            "channel": self._opts.channel,
        }
        if self._opts.language:
            audio_cfg["language"] = self._opts.language  # 留空→中英混合自动
        cfg = {
            "user": {"uid": "livekit-agent"},
            "audio": audio_cfg,
            "request": {
                "model_name": self._opts.model_name,
                "enable_itn": self._opts.enable_itn,
                "enable_punc": self._opts.enable_punc,
                "show_utterances": self._opts.show_utterances,
                "result_type": self._opts.result_type,
                "end_window_size": self._opts.end_window_size,
            },
        }
        return json.dumps(cfg, ensure_ascii=False).encode("utf-8")

    def _build_auth_headers(self) -> dict:
        """新版控制台鉴权:X-Api-Key + Resource-Id + Request-Id + Sequence=-1。"""
        return {
            "X-Api-Key": self._opts.api_key,
            "X-Api-Resource-Id": self._opts.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Sequence": "-1",
        }

    async def _ensure_connected(self) -> None:
        if self._ws is not None:
            return
        headers = self._build_auth_headers()
        try:
            if self._volc_stt._http_session is not None:
                session = self._volc_stt._http_session
            else:
                session = aiohttp.ClientSession()
                self._owns_session = True
            self._session = session
            self._ws = await asyncio.wait_for(
                session.ws_connect(self._opts.endpoint, headers=headers, heartbeat=20.0),
                timeout=self._conn_options.timeout,
            )
        except asyncio.TimeoutError as e:
            raise APITimeoutError("火山 ASR WebSocket 连接超时") from e
        except Exception as e:
            raise APIConnectionError(f"火山 ASR 连接失败: {e}") from e

        # 首帧:full client request(JSON + gzip)
        payload = self._build_full_request_payload()
        frame = _frame(
            _header(MSG_FULL_CLIENT_REQUEST, FLAG_NO_SEQ, SER_JSON, COMP_GZIP),
            payload,
            compress=True,
        )
        await self._ws.send_bytes(frame)
        self._sent_full_request = True
        self._recv_task = asyncio.create_task(self._recv_loop(), name="volc.recv_loop")

    async def _send_audio(self, frame_bytes: bytes, last: bool = False) -> None:
        assert self._ws is not None
        flags = FLAG_LAST_NO_SEQ if last else FLAG_NO_SEQ
        header = _header(MSG_AUDIO_ONLY, flags, SER_NONE, COMP_GZIP)
        await self._ws.send_bytes(_frame(header, frame_bytes, compress=True))

    # ── 主循环 ──────────────────────────────────────────────────────────
    @utils.log_exceptions()
    async def _run(self) -> None:
        bstream = utils.audio.AudioByteStream(
            sample_rate=self._opts.rate,
            num_channels=1,
            samples_per_channel=self._opts.rate // (1000 // self._opts.chunk_ms),
        )
        try:
            async for data in self._input_ch:
                frames: list[rtc.AudioFrame] = []
                if isinstance(data, rtc.AudioFrame):
                    frames.extend(bstream.write(data.data.tobytes()))
                elif isinstance(data, self._FlushSentinel):
                    frames.extend(bstream.flush())

                if frames and self._ws is None:
                    await self._ensure_connected()

                for frame in frames:
                    if self._ws is not None:
                        await self._send_audio(frame.data.tobytes(), last=False)
        finally:
            # 发送最后一包(负包)并等接收收尾
            if self._ws is not None:
                try:
                    await self._send_audio(b"", last=True)
                except Exception:
                    pass
                if self._recv_task:
                    try:
                        await asyncio.wait_for(self._recv_task, timeout=_RECV_COMPLETION_TIMEOUT)
                    except asyncio.TimeoutError:
                        await utils.aio.gracefully_cancel(self._recv_task)
                try:
                    await self._ws.close()
                except Exception:
                    pass
            if self._owns_session and self._session is not None:
                try:
                    await self._session.close()
                except Exception:
                    pass

    # ── 接收解析 ────────────────────────────────────────────────────────
    @utils.log_exceptions()
    async def _recv_loop(self) -> None:
        in_speech = False
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type != aiohttp.WSMsgType.BINARY:
                if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                    break
                if msg.type == aiohttp.WSMsgType.ERROR:
                    raise APIConnectionError(f"火山 ASR WS 错误: {self._ws.exception()}")
                continue

            data = bytes(msg.data)
            if len(data) < 4:
                continue
            msg_type = (data[1] >> 4) & 0xF
            comp = data[2] & 0xF

            if msg_type == MSG_FULL_SERVER_RESPONSE:
                # header(4) + sequence(4) + payload_size(4) + payload
                psize = int.from_bytes(data[8:12], "big")
                payload = data[12 : 12 + psize]
                if comp == COMP_GZIP:
                    try:
                        payload = gzip.decompress(payload)
                    except Exception:
                        continue
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                events = self._to_events(obj, in_speech)
                for ev, in_speech in events:
                    self._event_ch.send_nowait(ev)
            elif msg_type == MSG_ERROR:
                code = int.from_bytes(data[4:8], "big") if len(data) >= 8 else 0
                msize = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
                txt = data[12 : 12 + msize].decode("utf-8", errors="replace")
                raise APIStatusError(
                    message=f"火山 ASR 错误 code={code}: {txt}",
                    status_code=500,
                    request_id=None,
                    body=None,
                )

    def _to_events(self, obj: dict, in_speech: bool) -> list[tuple[stt.SpeechEvent, bool]]:
        """把火山响应 JSON 转成 (SpeechEvent, in_speech_after) 序表。"""
        result = obj.get("result") or {}
        text = (result.get("text") or "").strip()
        utts = result.get("utterances") or []
        is_definite = any(u.get("definite") for u in utts)

        out: list[tuple[stt.SpeechEvent, bool]] = []
        if not text:
            return out

        if not in_speech:
            out.append((stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH), True))
            in_speech = True

        lang = LanguageCode(self._opts.language or "zh")

        if is_definite:
            out.append(
                (
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[
                            stt.SpeechData(text=text, language=lang),
                        ],
                    ),
                    True,
                )
            )
            out.append((stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH), False))
            in_speech = False
        else:
            out.append(
                (
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                        alternatives=[
                            stt.SpeechData(text=text, language=lang),
                        ],
                    ),
                    True,
                )
            )
        return out
