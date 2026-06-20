# LiveKit Agent · Web

一个基于 **LiveKit Cloud** 的实时语音 Agent Web 端：浏览器与 AI Agent 进行实时语音/文字对话。
前端采用 React + [`livekit-client`](https://github.com/livekit/client-sdk-js)（2026 最新 **Session API + TokenSource** 架构），后端用一个 Express token 服务签发带 agent dispatch 的 JWT。

> 参考文档：https://docs.livekit.io/agents.md 与 https://docs.livekit.io/frontends/build.md

---

## 架构

```
 浏览器 (React + livekit-client)                  LiveKit Cloud                     Agent (你需要单独部署)
 ┌─────────────────────────────┐                ┌──────────────────┐             ┌──────────────────────┐
 │  useSession(TokenSource     │  1) POST        │                  │  3) dispatch │  AgentSession(        │
 │    .endpoint('/api/token')) │ ──/api/token──▶ │  自动派发 agent  │ ───────────▶ │    stt/llm/tts)       │
 │      │                      │  (room_config)  │   进房间         │              │   语音/文字对话       │
 │      ▼                      │  2) token       │                  │  4) WebRTC   │                      │
 │  Room.connect (WebRTC) ◀━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│   ← 实时音视频/转写   │
 └─────────────────────────────┘                 └──────────────────┘             └──────────────────────┘
            │
            │  (开发期 Vite 代理 /api → 8787；生产期 Express 同源托管 dist/)
            ▼
 ┌─────────────────────┐
 │ Express token 服务   │  livekit-server-sdk 签发 JWT，把 room_config 透传
 │ POST /api/token     │  → LiveKit Cloud 收到后自动把 agent 拉进房间
 └─────────────────────┘
```

关键点：前端 `useSession({ agentName })` 会自动把 agent 派发信息打包进 `room_config`；token 服务只需把它**原样透传**给 `AccessToken`，LiveKit Cloud 就会在参与者连进房间的瞬间自动派发对应 agent。

---

## 前置条件

- **Node.js ≥ 20**（已用 v20.20.0 验证）
- 一个 **LiveKit Cloud** 项目：https://cloud.livekit.io → 项目设置里拿到
  - `LIVEKIT_URL`（形如 `wss://xxx.livekit.cloud`）
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
- **一个正在运行的 Agent**（agentName 与前端一致）。前端本身不包含 agent；没有 agent 时能连进房间，但不会有人和你对话（约 20s 后状态变为"出错"）。

---

## 快速开始

```bash
cd agent-web
npm install            # 已配置 .npmrc 走 npmmirror 国内镜像
# LiveKit 凭据统一在仓库根 .livekit.env 管理（见下方「Cloud ⇄ 本地 切换」）
# 首次使用:cd .. && cp .livekit.env.example .livekit.env，再填入 Cloud 凭据
npm run dev            # 同时启动 token 服务(:8787) 和 Vite 前端(:5173)
```

打开 **http://localhost:5173** ，允许麦克风权限 → 填 Agent 名称（默认 `my-agent`，需与已部署 agent 一致）→「开始通话」。

> token 接口默认是相对路径 `/api/token`，开发期由 Vite 代理到 `:8787`，无需关心跨域。

### 生产构建（单进程）

```bash
npm run build          # 输出 dist/
npm start              # Express 同时托管 dist/ 和 /api/token，打开 http://localhost:8787
```

---

## Cloud ⇄ 本地 LiveKit Server 切换

传输层（SFU/信令）在 LiveKit Cloud 与自托管 Server 之间是**同一套协议**，切换只是换 URL/key/secret。
本仓库用**仓库根 `.livekit.env`** 的 `LIVEKIT_PROFILE` 一行统一切换：token 服务和 agent 启动时都会
向上查找该文件，按 profile 把对应预设写进标准环境变量（`LIVEKIT_URL/KEY/SECRET`）。

根 `.livekit.env`（从 `.livekit.env.example` 复制，已 gitignore）结构：

```
LIVEKIT_PROFILE=local            # cloud | local
LIVEKIT_URL_CLOUD=wss://...      LIVEKIT_URL_LOCAL=ws://localhost:7880
LIVEKIT_API_KEY_CLOUD=API...     LIVEKIT_API_KEY_LOCAL=devkey
LIVEKIT_API_SECRET_CLOUD=...     LIVEKIT_API_SECRET_LOCAL=secret
```

### 用本地 Server

LiveKit Server **不在本仓库内**，需另行安装。详见根 [README.md](../README.md)。

```bash
# 终端0 — LiveKit Server
livekit-server --dev    # ws://localhost:7880, devkey/secret

# 根 .livekit.env 设 LIVEKIT_PROFILE=local，然后:
cd agent-py && uv run python src/agent.py dev    # 终端1
cd agent-web && npm run dev                      # 终端2
```

切回 Cloud：把 `LIVEKIT_PROFILE` 改回 `cloud`，重启 agent + 前端。

> 本伞形仓库的 **agent-py** 使用国内模型插件，本地 Server 上可跑真实语音对话（不依赖 LiveKit Cloud Inference）。

---

## 让它能真正对话：部署一个 Agent

前端连进房间后，需要同名的 agent 被派发进来。最省事的是用 LiveKit Inference（Cloud 内置模型，**无需额外 API key**）：

**方式 A：用官方 starter（推荐）**

```bash
# 安装 LiveKit CLI（如尚未）
brew install livekit-cli

lk agent init my-agent --template agent-starter-node   # 或 agent-starter-python
cd my-agent
# 按 README 配好 LiveKit 凭据后：
pnpm dev   # 开发模式，会连接到你的 LiveKit Cloud 项目
```

本项目同级的 `../agents` 目录就是 LiveKit Agents Python SDK 源码，可直接参考/运行其 `examples`。

**方式 B：手写一个最小 Node agent（核心片段）**

```ts
// agent.ts — 完整模板见 https://github.com/livekit-examples/agent-starter-node
import { type JobContext, ServerOptions, cli, defineAgent, voice } from '@livekit/agents';
import * as livekit from '@livekit/agents-plugin-livekit';
import * as silero from '@livekit/agents-plugin-silero';
import { Agent } from './agent'; // class Agent extends voice.Agent { instructions = '...' }

export default defineAgent({
  prewarm: async (proc) => { proc.userData.vad = await silero.VAD.load(); },
  entry: async (ctx: JobContext) => {
    const session = new voice.AgentSession({
      vad: ctx.proc.userData.vad,
      stt: 'deepgram/nova-3:multi',
      llm: 'openai/gpt-4.1-mini',
      tts: 'cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc',
      turnHandling: { turnDetection: new livekit.turnDetector.MultilingualModel() },
    });
    await session.start({ agent: new Agent(), room: ctx.room });
    await ctx.connect();
    session.generateReply({ instructions: 'Greet the user and offer help.' });
  },
});
cli.runApp(new ServerOptions({ agent: import.meta.url, agentName: 'my-agent' })); // ← 名字要和前端一致
```

> 也可以改用 OpenAI Realtime 等单模型方案，见 https://docs.livekit.io/agents/start/voice-ai.md

---

## 配置项

| 变量 | 位置 | 说明 |
| --- | --- | --- |
| `LIVEKIT_PROFILE` | 根 `.livekit.env` | `cloud` 或 `local`，切换传输层（见下） |
| `LIVEKIT_URL_*` / `LIVEKIT_API_KEY_*` / `LIVEKIT_API_SECRET_*` | 根 `.livekit.env` | Cloud / local 两套预设，服务端签发 token 用，**勿泄露到前端** |
| `PORT` | `agent-web/.env` | token 服务端口，默认 8787 |
| `VITE_AGENT_NAME` | `agent-web/.env` | 前端默认 agent 名（也可在连接页输入框临时改） |
| `VITE_TOKEN_ENDPOINT` | `agent-web/.env` | 可选，覆盖 token 接口地址，默认 `/api/token` |

---

## 项目结构

```
agent-web/
├── server/index.mjs        # Express token 服务（/api/token + /api/health，生产期托管 dist/）
├── src/
│   ├── main.tsx            # 入口
│   ├── App.tsx             # 连接页 ↔ 会话页 切换
│   ├── index.css           # 深色 UI
│   └── components/
│       ├── ConnectScreen.tsx  # agent 名输入 + 开始通话
│       ├── SessionView.tsx    # useSession + SessionProvider，管理会话生命周期
│       ├── AgentStage.tsx     # useAgent 状态徽章 + BarVisualizer + RoomAudioRenderer
│       ├── Controls.tsx       # 麦克风开关 / 挂断
│       └── ChatPanel.tsx      # useSessionMessages 转写+文字聊天
├── vite.config.ts          # React + /api 代理 → 8787
└── .env(.example)          # LiveKit Cloud 凭据
```

---

## 常见问题

- **状态停在"连接房间中…"或变为"出错：Agent did not join the room"** → 房间已连上，但没有同名 agent 加入。检查 agent 是否在运行，以及 `agentName` 是否完全一致。
- **浏览器拿不到麦克风 / 没声音** → 麦克风需要安全上下文。`localhost` 可用；远程访问需 HTTPS。Chrome 地址栏左侧确认麦克风权限已授予。
- **`/api/token` 返回 500 "missing LIVEKIT_API_KEY"** → 仓库根 `.livekit.env` 未配置或 `LIVEKIT_PROFILE` 对应预设缺失。
- **端口被占用（EADDRINUSE 8787/5173）** → 关掉之前的 `npm run dev` 进程再启动。
- **国内安装慢** → 已自带 `.npmrc` 指向 `registry.npmmirror.com`；如需官方源删除该文件即可。

---

## 已验证

使用真实 LiveKit Cloud 凭据完成端到端验证：
- ✅ `tsc --noEmit` 类型检查 0 错误；`vite build` 构建通过
- ✅ `/api/health` 返回 `configured:true`；`RoomServiceClient` 凭据校验通过
- ✅ `/api/token` 返回的 JWT 正确包含 `roomConfig.agents[0].agentName`（agent dispatch 透传正确）
- ✅ 浏览器真实连入 LiveKit Cloud 房间（Cloud 侧确认创建房间、participants=1），状态从 `连接中 → 准备就绪，正在聆听`，控制台 0 报错
- （未含：与 agent 的真实语音对话——需另部署 agent，属本方案"纯前端"范围之外）

### 本地 LiveKit Server（`LIVEKIT_PROFILE=local`，从 `livekit/` 源码编译）

- ✅ `mage build` 产出 `livekit/bin/livekit-server`（v1.13.1）；`./run-dev.sh --dev` 监听 `127.0.0.1:7880`，devkey/secret，单节点免 Redis
- ✅ token server 与 agent 启动日志均打印 `🛰 LiveKit transport = LOCAL (ws://localhost:7880)`；`/api/health` 返回 `profile:"local"`
- ✅ profile 切到 `cloud` 后 token server 解析为 `CLOUD (wss://…livekit.cloud)`，双向切换成立
- ✅ `/api/token` 返回 `server_url=ws://localhost:7880`，JWT 由 `devkey` 签发，含 `roomConfig.agents[0].agentName=my-agent`（派发透传在本地同样有效）
- ✅ agent worker 连上本地 server 并注册（server version 1.13.1）；浏览器连入后 agent 收到并运行 dispatch job（`AJ_…`）——**传输/派发链路端到端打通**
- ⚠️ 本地模式下 `inference.STT` 报 `Error connecting to LiveKit WebSocket`、`AgentSession closed reason:error`：agent 大脑(STT/LLM/TTS)是 Cloud 托管的 LiveKit Inference，本地不提供。属预期的「Layer 2」限制，需改用模型插件才能本地对话。
