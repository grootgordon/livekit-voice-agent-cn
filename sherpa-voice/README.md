# sherpa-voice

本地 **OpenAI 兼容 TTS 服务**,封装 [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)(新一代 Kaldi / k2-fsa 生态的 ONNX 推理),供 `agent-py` 通过 LiveKit 原生 `openai.TTS` 插件调用。零 API 费用,纯 CPU 运行。

## 为什么单独成服务

- **隔离旧版依赖**:本机 macOS 12 Intel 锁死 `sherpa-onnx==1.9.30`(自带 onnxruntime 1.17,绕过新版 CoreML 崩溃)。独立 venv 避免污染 `agent-py`。
- **agent-py 改动最小**:LiveKit `openai.TTS` 原生支持指向自定义 OpenAI 兼容 endpoint,只需改 `base_url`。
- **chunked streaming**:`openai.TTS` 用 `iter_bytes()` 流式读,服务端边合成边发,降低首字延迟。

## 音色模型(默认 theresa)

服务按 `.env` 的 `MODEL_DIR` 加载模型,内置两个可选:

| 模型 | 采样率 | 说话人 | 说明 |
| --- | --- | --- | --- |
| **theresa**(默认) | 22050Hz | 单说话人(固定音色) | 米哈游角色音色(zh-hf-theresa 微调),音质较好、峰值够响 |
| aishell3 | 8000Hz | 174 个 sid(0-173) | icefall 多说话人,电话级音质,可切不同音色 |

## 架构

```
agent-py (openai.TTS, base_url=http://localhost:8001/v1)
        │  POST /v1/audio/speech  {input, voice, response_format="pcm"}
        ▼
sherpa-voice (FastAPI + sherpa-onnx 1.9.30)
   OfflineTts(theresa) 单例 ──callback──▶ 源采样率→24kHz 重采样 + 音量归一化
                                          ──chunked──▶ int16 PCM
```

## 前置:模型

模型不纳入版本库(避免重复占盘 + 泄露本机绝对路径),软链到 `kokoro/` 下已下载的:

```bash
mkdir -p models
ln -s ../../kokoro/models/sherpa/vits-zh-hf-theresa          models/theresa    # 默认
ln -s ../../kokoro/models/sherpa/vits-icefall-zh-aishell3   models/aishell3   # 可选
```

切换音色:改 `.env` 的 `MODEL_DIR` 为 `models/theresa` 或 `models/aishell3`。

## 部署

```bash
cd sherpa-voice
cp .env.example .env          # 按需改端口 / 音色
uv sync                        # 装依赖(首次)
./start.sh                     # 启动 → http://localhost:8001
```

## 验证

```bash
# 健康检查(model_sr 随模型变:theresa=22050, aishell3=8000)
curl -s localhost:8001/health
# => {"status":"ok","model_sr":22050,"output_sr":24000}

# 合成并保存为 wav 试听(24kHz)
curl -s -X POST localhost:8001/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"你好，我是本地语音助手。","voice":"0"}' \
  | python3 -c "import sys,wave,struct; d=sys.stdin.buffer.read(); \
w=wave.open('/tmp/t.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); \
w.writeframes(d); print('wrote /tmp/t.wav', len(d),'bytes')"
afplay /tmp/t.wav
```

## 与 agent-py 对接

`agent-py/.env.local` 设(或用默认值):

```
TTS_PROVIDER=sherpa
SHERPA_VOICE_URL=http://localhost:8001/v1
SHERPA_VOICE=0          # theresa 单说话人留 0;换 aishell3 则为 speaker sid(0-173)
```

`agent.py` 会用 `openai.TTS(base_url=..., response_format="pcm")`。切回云端:`TTS_PROVIDER=minimax`(需有效 key)。

## 已知限制(v1)

| 项 | 说明 |
| --- | --- |
| 语言 | **仅中文**(theresa / aishell3 都是纯中文模型,英文读不出)。中英双语 melo 模型在本机 sherpa-onnx 1.9.30 下 lexicon 不兼容,跑不通。 |
| 音质 | theresa 源 22050Hz(可接受);aishell3 源 8000Hz(电话级)。均上采样到 24kHz,不提升信息,整体弱于 MiniMax 24kHz 原生。 |
| 说话人 | theresa 单说话人(固定音色);aishell3 有 174 个 sid(0-173)可切。 |
| 音量 | aishell3 原始峰值仅 ~0.11(需 `NORMALIZE_GAIN≈8.0`);theresa 峰值 ~0.66 已够响(`gain=1.0`)。 |
| 首字延迟 | 本机 i7-4770HQ 纯 CPU 实测 RTF 0.13–0.17,首字延迟 ~0.6–1.5s(长句偏慢)。 |

## 性能(本机实测,见 `../kokoro/scripts/bench_sherpa.py`,本地不入库)

| 指标 | 值 | 对比 |
| --- | --- | --- |
| RTF | 0.13–0.17 | MiniMax 云端 ~0.1–0.3 |
| 首字延迟 | 0.6–1.5s | MiniMax ~0.3–0.6s |
| 冷启动 | ~6s | — |

## 许可证

- 代码(本服务 + 整个伞形仓库):**MIT**(见根 `LICENSE`)。
- sherpa-onnx / icefall:Apache-2.0。
- aishell3 模型:Apache-2.0(可商用)。
- theresa 模型:社区微调(zh-hf-theresa),按其原始来源许可。
