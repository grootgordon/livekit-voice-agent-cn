# agent-android

LiveKit 语音 Agent 的 **Android 原生入口**，与仓库的 `agent-web`（浏览器入口）平级。装到手机后可直接连接 LiveKit Cloud 或本地自建 Server，验证 `agent-py` 的语音对话效果。

## 特点

- **端内签 token**：用 `java-jwt` 在手机本地签发带 agent dispatch 的 JWT（不引入 server-sdk-kotlin，以免与客户端 `protobuf-javalite` 冲突），**不依赖任何 token 服务**，手机独立运行。
- **Cloud / 本地 一键切换**：配置页两个预设，对应根目录 `.livekit.env` 的 Cloud / Local。
- **音频可视化**：用 `components-android` 的 `VoiceAssistantBarVisualizer` 直观显示连接状态与 Agent 说话波形。
- 配置经 DataStore 持久化，下次打开自动回填。

## 架构

```
Android 手机 (agent-android)         LiveKit SFU             agent-py
┌─────────────────────┐    WebRTC   ┌───────────────┐    ┌──────────────────┐
│ Compose UI          │ ◀─────────▶ │ Cloud / 本地  │ ◀▶ │ STT→LLM→TTS      │
│ 端内签 JWT          │             └───────────────┘    │ 火山/DeepSeek/   │
│ RoomScope + 麦克风  │                                  │ MiniMax          │
└──────────┬──────────┘                                  └──────────────────┘
           │ room_config.agents[0].agentName = "my-agent"
           ▼ 派发同名 Agent 进房
```

token claims 与 `../agent-web/server/index.mjs` 完全一致，所以同一个 `agent-py` worker 都能被派发进房。

## 前置条件

| 工具 | 说明 |
| --- | --- |
| **Android Studio**（含 Android SDK + JDK 17） | 构建 / 运行 APK |
| **真机或模拟器**（Android 8.0 / API 26+） | 真机效果更好（语音需真实麦克风） |
| **agent-py 在运行** | 真正说话的 Agent，必须先启动 |
| LiveKit 传输层 | Cloud，或本地 `livekit-server --dev` |

## 配置（在 App 内）

打开 App，配置页选择连接方式：

- **Cloud**：填 cloud.livekit.io → 项目 Settings 的 `wss://` URL / API Key / API Secret。
- **本地 Server**：默认 `devkey` / `secret`，URL 填运行 Server 的电脑局域网 IP，如 `ws://192.168.1.100:7880`（模拟器连宿主机用 `ws://10.0.2.2:7880`）。

Agent 名称默认 `my-agent`，须与 `agent-py` 的 `agent_name` 一致才会被派发进房。

## 构建出 APK

> 仓库已默认配置国内镜像以应对 `dl.google.com` / maven central 间歇不可达：`settings.gradle.kts` 用阿里云 maven（google + public + gradle-plugin），并保留 jitpack（`livekit-android` 的传递依赖 `audioswitch` 仅在此）；`gradle-wrapper.properties` 用腾讯云 gradle 镜像。海外网络下这些镜像同样可用，无需改动。

### 方式 A：Android Studio（推荐）

1. Android Studio → Open → 选 `agent-android/` 目录
2. 等 Gradle 同步完成（首次会下载依赖）
3. `Build → Build Bundle(s)/APK(s) → Build APK(s)`
4. 产物：`app/build/outputs/apk/debug/app-debug.apk`

### 方式 B：命令行

```bash
cd agent-android
./gradlew assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
```

> 命令行构建需要 JDK 17 与 Android SDK（设置 `ANDROID_HOME`，或在 `local.properties` 写 `sdk.dir=...`）。

## 安装到手机

- **adb**：`adb install app/build/outputs/apk/debug/app-debug.apk`
- **手动**：把 APK 拷到手机，开启「允许安装未知来源应用」后安装。

> debug APK 用 debug 签名、universal 包（不分 ABI），各机型通用。

## 本地端到端验证

```bash
# 终端 0 — 本地 LiveKit Server
livekit-server --dev            # ws://localhost:7880  devkey/secret

# 终端 1 — Agent（确保根 .livekit.env 里 LIVEKIT_PROFILE=local）
cd ../agent-py && uv run python src/agent.py dev
```

手机与电脑连同一 WiFi，App 选「本地 Server」，URL 填电脑 IP（`ipconfig getifaddr en0` 可查），点「开始通话」。授权麦克风后，可视化应从「连接中」→「聆听中」，开口说话即得 Agent 回复。

## 安全提示

⚠️ **API Key / Secret 会随 APK 一起打包**。本 APK 仅供你本人测试，**切勿公开发布或上传应用商店**——否则等同于公开你的 LiveKit Cloud 密钥。生产部署应改为后端签 token（参考 `../agent-web` 的 token 服务）。

## 故障排查

| 现象 | 排查 |
| --- | --- |
| 「连接出错」/ 一直连接中 | URL 是否可达（Cloud 的 `wss://` / 本地的 `ws://` + 同 WiFi IP）？Key/Secret 是否正确？agent-py 是否在跑？ |
| Agent 没进房 | Agent 名是否 = `my-agent`？agent-py 控制台是否显示接单？ |
| 模拟器连不上本地 Server | 用 `ws://10.0.2.2:7880`（模拟器内的 localhost 指向宿主机） |
| 听不到 Agent 声音 | 手机非静音、媒体音量正常；远端音频会自动播放 |
| Gradle 同步失败 | 确认 JDK 17、Android SDK 已安装；首次需联网下载依赖 |
