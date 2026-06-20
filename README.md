# LiveKit Voice Agent（国内模型生态）

基于 [LiveKit Agents](https://docs.livekit.io/agents/) 的实时语音对话方案：**Python Agent + React Web 前端**。

本仓库是**伞形 monorepo**，只包含应用层代码；LiveKit Server / Agents SDK 等上游项目**不纳入**版本库，按需自行安装。

| 子项目 | 说明 |
| --- | --- |
| [`agent-py/`](agent-py/) | Python 语音 Agent：STT 火山豆包 / LLM DeepSeek / TTS MiniMax |
| [`agent-web/`](agent-web/) | React 前端 + Express Token 服务（Session API + agent dispatch） |

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

> **为何用 Python Agent？** 模型走国内 API（DeepSeek / MiniMax / 火山），**不依赖 LiveKit Cloud Inference**，因此在自托管 LiveKit Server 上也能跑真实语音对话。

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
cd agent-py && uv sync && cd ..
cd agent-web && npm install && cd ..
```

### 4. 启动（两个终端）

```bash
# 终端 1 — Python Agent
cd agent-py && uv run python src/agent.py dev

# 终端 2 — Web（Token 服务 :8787 + Vite :5173）
cd agent-web && npm run dev
```

### 5. 浏览器验证

1. 打开 http://localhost:5173
2. 允许麦克风权限
3. Agent 名称填 **`my-agent`**（与 agent-py 中 `agent_name` 一致）
4. 点击「开始通话」，说中英混合句子

启动成功时，两个终端应分别打印 `🛰  LiveKit transport = CLOUD (...)` 和 `🟢 Token server: http://localhost:8787`。

---

## 本地 LiveKit Server（可选）

本仓库**不包含** LiveKit Server 源码。若要在本地跑（`LIVEKIT_PROFILE=local`），任选一种方式启动 SFU：

### 方式 A：`livekit-server --dev`（最简单）

```bash
# macOS
brew install livekit

# 或从 GitHub Releases 下载二进制
# https://github.com/livekit/livekit/releases

livekit-server --dev
# 默认：ws://localhost:7880  key=devkey  secret=secret
```

### 方式 B：Docker

```bash
docker run --rm \
  -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
  livekit/livekit-server --dev
```

### 切换 profile 并启动应用

```bash
# .livekit.env 中设置：
#   LIVEKIT_PROFILE=local
# （LOCAL 预设已在 .livekit.env.example 中填好 devkey/secret）

# 终端 0 — LiveKit Server
livekit-server --dev

# 终端 1 — Agent
cd agent-py && uv run python src/agent.py dev

# 终端 2 — Web
cd agent-web && npm run dev
```

更多自托管说明见 [LiveKit 官方文档](https://docs.livekit.io/home/self-hosting/local/)。

---

## Cloud ⇄ Local 切换

根目录 `.livekit.env` 改一行，重启 agent-py 和 agent-web 即可：

```
LIVEKIT_PROFILE=cloud   # 或 local
```

两个子项目启动时都会**向上查找**该文件，自动写入 `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`。

---

## 目录结构

```
livekit-voice-agent-cn/
├── .livekit.env.example    # 传输层配置模板（Cloud + Local 双预设）
├── agent-py/               # Python 语音 Agent
├── agent-web/              # React 前端 + Token 服务
└── scripts/
    └── check-secrets.sh    # 提交前密钥扫描
```

---

## 子项目文档

- [agent-py/README.md](agent-py/README.md) — 模型配置、STT 单点验证
- [agent-web/README.md](agent-web/README.md) — 前端架构、Token 服务、生产构建

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
