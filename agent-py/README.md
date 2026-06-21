# LiveKit Agent · Python(国内模型生态)

Python 语音 agent,用**国内模型**做大脑,**不依赖 LiveKit Cloud Inference**——
因此在**本地 LiveKit Server** 上也能跑真实(中英混合)语音对话。

| 组件 | 选型 | 形态 |
| --- | --- | --- |
| STT | **火山豆包大模型流式 ASR** | 自定义 STT(`src/stt_volcengine.py`,封装双向 WebSocket) |
| LLM | **DeepSeek** | `openai.LLM.with_deepseek`(官方插件) |
| TTS | **sherpa-voice**(本地,默认)/ **MiniMax**(云端)/ **火山 2.0**(双向流式) | `openai.TTS`→本地服务;`minimax.TTS`;`VolcengineTTS` 自定义 |
| Turn detector | **火山 STT 端点**（`definite` → `END_OF_SPEECH`） | 不用 v1-mini 本地原生库，避免 macOS SIGSEGV |
| 传输层 | LiveKit Cloud ⇄ 本地 Server | 复用仓库根 `.livekit.env` 的 `LIVEKIT_PROFILE` |

> STT 默认 **language 留空 → 中英文 + 方言自动识别(中英混合)**。
>
> TTS 默认走本地 **sherpa-voice**(零成本、纯中文;`TTS_PROVIDER=sherpa`,需先启动 [`../sherpa-voice`](../sherpa-voice) 服务,否则 502)。
> 设 `TTS_PROVIDER=minimax` 切云端 MiniMax(需有效 `MINIMAX_API_KEY`);
> 或 `TTS_PROVIDER=volc` 切火山豆包语音合成 2.0(双向流式,`VOLC_ASR_API_KEY` 与 STT 共用 + 必填 `VOLC_TTS_VOICE`,音质/中英混合最优;实现见 [`src/tts_volcengine.py`](src/tts_volcengine.py),先用 `uv run python test_volc_tts.py` 验证)。

## 前置

- **uv**(Python 包管理,自带 Python 3.12):`brew install uv`(已配国内 PyPI 镜像)
- 三家模型 key(见下)
- 传输层凭据已在仓库根 `.livekit.env`(默认 `LIVEKIT_PROFILE=local`)

## 配置密钥

```bash
cp .env.example .env.local
# 填入三组 key:DEEPSEEK_API_KEY、MINIMAX_API_KEY、VOLC_ASR_API_KEY
```

| 变量 | 来源 |
| --- | --- |
| `DEEPSEEK_API_KEY` | https://platform.deepseek.com |
| `MINIMAX_API_KEY` + `MINIMAX_BASE_URL`(可选 `MINIMAX_VOICE`) | 国内站 https://platform.minimaxi.com(配 `https://api.minimaxi.com`);国际站 https://platform.minimax.io(配 `https://api.minimax.io`)。**国内/国际 key 不通用** |
| `VOLC_ASR_API_KEY` / `VOLC_ASR_RESOURCE_ID` | 火山引擎控制台(新版)→ 语音技术 → [API Keys](https://console.volcengine.com/speech/new/setting/apikeys) |

## 安装

```bash
cd agent-py
uv sync                                        # 装依赖(国内镜像)
# download-files 仅在使用 v1-mini turn detector 时需要;默认 STT 端点模式可跳过
```

## 先单独验证 STT(推荐)

填好火山 key 后,拿一段 16k/单声道/16bit wav 验证密钥 + 协议:

```bash
uv run python test_volc_asr.py /path/to/test.wav
# 期望:逐行打印 [interim] / [FINAL] 中文(可夹英文)文本
```

跑通这一步,说明 STT 自定义件没问题;再做端到端。

## 运行(端到端)

完整步骤见仓库根 [README.md](../README.md)。本地 Server 模式示例:

```bash
# 终端0: LiveKit Server(需另行安装,见根 README「本地 LiveKit Server」)
livekit-server --dev

# 终端1:本 agent(根 .livekit.env 设 LIVEKIT_PROFILE=local)
cd agent-py && uv run python src/agent.py dev

# 终端2:前端
cd agent-web && npm run dev
```

打开 http://localhost:5173 → 允许麦克风 → Agent 名填 `my-agent` → 开始通话。

## 目录

```
agent-py/
├── pyproject.toml
├── .env.local            # 模型密钥(gitignored)
├── test_volc_asr.py      # standalone STT 验证脚本
├── test_volc_tts.py      # standalone 火山 TTS 验证脚本(TTS_PROVIDER=volc)
└── src/
    ├── agent.py            # AgentSession 主程序
    ├── livekit_profile.py  # 传输层 profile 解析(读根 .livekit.env)
    ├── stt_volcengine.py   # 火山豆包大模型流式 ASR 自定义 STT
    └── tts_volcengine.py   # 火山豆包语音合成 2.0 双向流式 自定义 TTS
```

## 已验证

- ✅ `uv sync` + `download-files` + 导入检查通过
- ✅ **STT 单点**:喂 16k 中文 wav,火山豆包大模型流式 ASR 正确转写(interim + FINAL)
- ✅ **LLM 单点**:DeepSeek(`openai.LLM.with_deepseek`)正常应答
- ✅ **TTS 单点(云端)**:MiniMax 国内站 `api.minimaxi.com` 正常合成音频
- ✅ **TTS 单点(本地)**:sherpa-voice(theresa)`/health` 返回 ok,合成 24kHz PCM 正常(默认 provider)
- 🚧 **TTS 单点(火山)**:已实现(双向流式 V3 + X-Api-Key,无 APP ID),待用 `VOLC_ASR_API_KEY`(与 STT 共用)+ `VOLC_TTS_VOICE` 跑 `uv run python test_volc_tts.py` 验证
- ✅ **端到端(本地 server)**:本地 LiveKit Server + 本 agent + agent-web 浏览器;
  agent 入房后用 **DeepSeek 生成问候、MiniMax 国内站合成发声**(日志见 `wss://api.minimaxi.com/ws/v1/t2a_v2`),
  浏览器聊天面板显示 agent 消息——**全程不碰 LiveKit Cloud Inference**。

## 协议参考

火山大模型流式 ASR 双向流式协议(鉴权 / 4 字节头大端分帧 / 负包 / gzip):https://www.volcengine.com/docs/6561/1354869
