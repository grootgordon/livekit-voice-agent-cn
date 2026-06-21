# LiveKit Voice Agent（国内模型生态）

基于 [LiveKit Agents](https://docs.livekit.io/agents/) 的实时语音对话方案：**Python Agent + React Web 前端**。

本仓库是**伞形 monorepo**，只包含应用层代码；LiveKit Server / Agents SDK 等上游项目**不纳入**版本库，按需自行安装。

| 子项目 | 说明 |
| --- | --- |
| [`agent-py/`](agent-py/) | Python 语音 Agent：STT 火山豆包 / LLM DeepSeek / TTS sherpa-voice 或 MiniMax |
| [`sherpa-voice/`](sherpa-voice/) | 本地 OpenAI 兼容 TTS 服务（sherpa-onnx，零成本，默认 TTS provider） |
| [`agent-web/`](agent-web/) | React 前端 + Express Token 服务（Session API + agent dispatch） |
| [`agent-android/`](agent-android/) | Android 原生入口（Kotlin + Compose，端内签 token + 音频可视化） |

## 架构

```
浏览器 (agent-web)          LiveKit SFU              agent-py
┌─────────────────┐    WebRTC / 信令    ┌──────────────────────┐
│ React + Token   │ ◀────────────────▶ │ AgentSession         │
│ POST /api/token │                    │ STT → LLM → TTS      │
└────────┬────────┘                    └──────────────────────┘
         │ Express 签发 JWT + room_config.agent dispatch
         ▼
   根目录 .livekit.env（Cloud ⇄ Local 切换）
```

> **为何用 Python Agent？** STT/LLM 走国内 API（火山 / DeepSeek），TTS 本地 [`sherpa-voice`](sherpa-voice/) 或云端 MiniMax，**不依赖 LiveKit Cloud Inference**，因此在自托管 LiveKit Server 上也能跑真实语音对话。

---

## 前置条件

| 工具 | 用途 | 安装 |
| --- | --- | --- |
| **Node.js ≥ 20** | agent-web | [nodejs.org](https://nodejs.org/) 或 `nvm install 20` |
| **uv** | agent-py 依赖管理 | `brew install uv` 或 [uv 文档](https://docs.astral.sh/uv/) |
| **LiveKit 传输层** | 信令 + WebRTC 中继 | Cloud 或本地 Server（见下） |
| **模型 API Key** | STT / LLM / TTS | DeepSeek、MiniMax、火山引擎（见 [agent-py 配置](agent-py/README.md#配置密钥)） |

---

## 快速开始（推荐：LiveKit Cloud）

最快跑通端到端，无需自建 Server。

### 1. 克隆

```bash
git clone https://github.com/grootgordon/livekit-voice-agent-cn.git
cd livekit-voice-agent-cn
```

### 2. 配置凭据

```bash
# 传输层 — 从 https://cloud.livekit.io 项目 Settings 获取
cp .livekit.env.example .livekit.env
# 编辑 .livekit.env：
#   LIVEKIT_PROFILE=cloud
#   LIVEKIT_URL_CLOUD=wss://your-project.livekit.cloud
#   LIVEKIT_API_KEY_CLOUD=API...
#   LIVEKIT_API_SECRET_CLOUD=...

# 模型密钥 — 仅 agent-py 需要
cp agent-py/.env.example agent-py/.env.local
# 填入 DEEPSEEK_API_KEY、MINIMAX_API_KEY、VOLC_ASR_API_KEY（见 agent-py/README.md）

# 前端本地配置（可选，有默认值）
cp agent-web/.env.example agent-web/.env
```

> **安全提示**：`.livekit.env`、`.env.local`、`.env` 已在 `.gitignore` 中，**切勿提交真实密钥**。

### 3. 安装依赖

```bash
cd sherpa-voice && uv sync && cd ..   # 本地 TTS（默认 provider；仅用云端 MiniMax 可跳过）
cd agent-py && uv sync && cd ..
cd agent-web && npm install && cd ..
```

### 4. 启动（三个终端）

> agent-py 默认 `TTS_PROVIDER=sherpa`，**必须先启动 sherpa-voice，否则 TTS 报 502**。
> 若改用云端 MiniMax：在 `agent-py/.env.local` 设 `TTS_PROVIDER=minimax`（需有效 key），可跳过终端 1。

```bash
# 终端 1 — 本地 TTS（sherpa-voice @ :8001；用 MiniMax 可跳过）
cd sherpa-voice && ./start.sh

# 终端 2 — Python Agent
cd agent-py && uv run python src/agent.py dev

# 终端 3 — Web（Token 服务 :8787 + Vite :5173）
cd agent-web && npm run dev
```

### 5. 浏览器验证

1. 打开 http://localhost:5173
2. 允许麦克风权限
3. Agent 名称填 **`my-agent`**（与 agent-py 中 `agent_name` 一致）
4. 点击「开始通话」，说中英混合句子

启动成功时，各终端分别打印：sherpa-voice `就绪 @ :8001`、agent-py `🛰  LiveKit transport = CLOUD (...)`、Web `🟢 Token server: http://localhost:8787`。

---

## 本地 LiveKit Server（可选）

`livekit/` 是 LiveKit Server 的**本地克隆**（已 gitignore，不入版本库），内含预编译二进制 `livekit/bin/livekit-server`（v1.13.1），以及本地启动用的 `Makefile` 和 `config-lan.yaml`。本地跑（`LIVEKIT_PROFILE=local`）用 Makefile 两种模式：

| 模式 | 命令 | 监听 | 适用 |
| --- | --- | --- | --- |
| **dev** | `make -C livekit dev` | `127.0.0.1:7880` | 本机浏览器测试（最快） |
| **lan** | `make -C livekit lan` | `0.0.0.0:7880` | 手机 / APK 局域网访问 |

两者均用 `--dev`，内置 `key=devkey` / `secret=secret`（与 `.livekit.env` 的 LOCAL 预设一致），单节点免 Redis。端口：信号 7880 / RTC-TCP 7881 / RTC-UDP 50000–60000。

> `make lan` 通过 `livekit/config-lan.yaml` 覆盖 dev 默认的 `127.0.0.1` 绑定（改为监听所有网卡），并跳过 NAT 自 ping 验证以加速启动；key 不变。

### 方式 A：仓库内 Makefile（推荐）

```bash
# 终端 0 — 选一种模式
make -C livekit dev      # 仅本机浏览器
make -C livekit lan      # 局域网（手机 / APK 可连）

# 其他目标
make -C livekit stop     # 停掉本地 server
make -C livekit ip       # 打印本机局域网 IP
make -C livekit help     # 全部命令
```

> `Makefile` 与 `config-lan.yaml` 在 gitignore 的 `livekit/` 内，**不随仓库分发**。新环境克隆后若没有这两个文件，退回方式 B。

### 方式 B：直接跑二进制

```bash
cd livekit
./bin/livekit-server --dev                            # 等同 make dev
./bin/livekit-server --dev --config config-lan.yaml   # 等同 make lan
```

### 方式 C：brew / Docker（不依赖本仓库二进制）

```bash
# macOS
brew install livekit && livekit-server --dev

# Docker
docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
  livekit/livekit-server --dev
```

### 切换 profile 并启动应用

```bash
# .livekit.env 中设置：LIVEKIT_PROFILE=local
# （LOCAL 预设的 devkey/secret 已对齐 dev 模式）

# 终端 0 — LiveKit Server
make -C livekit dev     # 或 lan

# 终端 1 — Agent
cd agent-py && uv run python src/agent.py dev

# 终端 2 — Web
cd agent-web && npm run dev
```

### 手机 APK 访问本地 Server

`make dev` 只监听 `127.0.0.1`，手机连不上。要让 APK 走本地 server：

1. `make -C livekit lan` —— 启动局域网模式（bind `0.0.0.0`）
2. `make -C livekit ip` —— 取本机局域网 IP（如 `192.168.1.30`）
3. `.livekit.env` 的 `LIVEKIT_URL_LOCAL` 设为 `ws://<该IP>:7880`
4. 手机与电脑连**同一 Wi-Fi**，APK 里 Agent 名填 `my-agent`

> 局域网 IP 可能随网络变化，换网后用 `make -C livekit ip` 重新获取并更新 `.livekit.env`。

更多自托管说明见 [LiveKit 官方文档](https://docs.livekit.io/home/self-hosting/local/)。

---

## Cloud ⇄ Local 切换

根目录 `.livekit.env` 改一行，重启 agent-py 和 agent-web 即可：

```
LIVEKIT_PROFILE=cloud   # 或 local
```

两个子项目启动时都会**向上查找**该文件，自动写入 `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`。

---

## Android 真机入口（[`agent-android/`](agent-android/)）

`agent-android/` 是与 Web 端平级的安卓入口，安装到手机即可验证语音 Agent。与 Web 端不同，它在**手机本地签 token**（不依赖 token 服务），UI 上可一键切换 Cloud / 本地 Server。

- 构建出 APK：`cd agent-android && ./gradlew assembleDebug`，产物在 `app/build/outputs/apk/debug/app-debug.apk`
- 需 Android Studio（含 Android SDK + JDK 17）；打开 `agent-android/` 即可构建运行
- Agent 名填 `my-agent`，与 agent-py 的 `agent_name` 一致

详见 [agent-android/README.md](agent-android/README.md)。

> ⚠️ 密钥随 APK 打包——**仅供自用，切勿公开发布 APK**。

---

## 目录结构

```
livekit-voice-agent-cn/
├── .livekit.env.example    # 传输层配置模板（Cloud + Local 双预设）
├── agent-py/               # Python 语音 Agent（STT 火山 / LLM DeepSeek / TTS）
├── sherpa-voice/           # 本地 TTS 服务（sherpa-onnx，默认 TTS provider）
├── agent-web/              # React 前端 + Token 服务
├── agent-android/          # Android 原生入口（Kotlin + Compose）
└── scripts/
    └── check-secrets.sh    # 提交前密钥扫描
```

---

## 子项目文档

- [agent-py/README.md](agent-py/README.md) — 模型配置、STT 单点验证
- [sherpa-voice/README.md](sherpa-voice/README.md) — 本地 TTS 服务、音色模型、性能
- [agent-web/README.md](agent-web/README.md) — 前端架构、Token 服务、生产构建
- [agent-android/README.md](agent-android/README.md) — Android 构建、APK 产出、真机验证

---

## 常见问题

| 现象 | 排查 |
| --- | --- |
| 「Agent did not join the room」 | agent-py 是否在运行？前端 Agent 名是否为 `my-agent`？ |
| `/api/token` 500 | 根目录 `.livekit.env` 是否配置？`LIVEKIT_PROFILE` 对应预设是否完整？ |
| 本地 Server 连上但无语音 | 确认用的是 **agent-py**（国内模型），不是依赖 Cloud Inference 的 Node agent |
| STT 无响应 | 先跑 `uv run python test_volc_asr.py /path/to/test.wav` 验证火山 key |

---

## 安全

贡献者提交前请运行：

```bash
./scripts/check-secrets.sh
```

确保无 `.livekit.env`、`.env.local`、API Key 等敏感文件进入版本库。
