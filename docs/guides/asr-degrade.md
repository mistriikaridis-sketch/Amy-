# ASR 降级路径（CapsWriter 可选）

阅稿**不依赖** CapsWriter 也能日常使用。按优先级：

## 路径总览

| 路径 | 做什么 | 依赖 |
|------|--------|------|
| **Path A** | 外部 ASR（如 Amy：yt-dlp + Whisper）产出 Markdown/纯文本 → 导入 VTA cache → 打开 `/view/{token}` | VTA 进程 + 已有文稿；**不需要** CapsWriter |
| **local_whisper** | VTA 本机出字：用外部 Python（装有 `faster-whisper` 或 `openai-whisper`）转写上传/下载的音频 | `config.local_whisper` + 环境变量（见下） |
| **Path B（可选）** | CapsWriter / FunASR WebSocket，走完整 `POST /api/transcribe` URL 流水线 | 另外部署 ASR Server |

`/health` 里 CapsWriter `degraded` 是预期：只要 Path A 或 `local_whisper` 可用，首页与阅读页仍可工作。

## 环境变量

解析本地 Whisper 解释器时，顺序为：

1. `config/config.jsonc` → `local_whisper.python`（非空则优先）
2. 环境变量 **`LOCAL_WHISPER_PYTHON`**
3. 环境变量 **`AMY_PYTHON`**（Amy / 其它已装 whisper 的解释器）
4. 实现内的本机候选路径（若存在）

示例（Windows PowerShell）：

```powershell
$env:LOCAL_WHISPER_PYTHON = "C:\Path\To\python.exe"   # 该解释器需能 import faster_whisper 或 whisper
# 或
$env:AMY_PYTHON = "C:\Path\To\Amy\venv\Scripts\python.exe"
```

`config.example.jsonc` 中：

```jsonc
"local_whisper": {
    "enabled": true,
    "python": "",          // 空则走上述环境变量 / 候选
    "engine": "auto",      // auto | faster-whisper | openai-whisper
    "model": "tiny",
    "language": "zh",
    "device": "cpu",
    "compute_type": "int8",
    "timeout_seconds": 7200
}
```

## Path A：文稿 → `/view`

典型流程：

1. 用任意工具得到带正文的 `.md` / 纯文本（Amy、本地 Whisper、飞书妙记导出等）。
2. 用导入脚本（例如旁路的 `amy-to-view`）写入 VTA 的 cache，并拿到 `view_token`。
3. 浏览器打开 `http://127.0.0.1:<port>/view/<view_token>`。
4. （可选）在阅读页点「重新校对 / 总结」，需已配置 LLM。

官方本机说明可参考维护者机器上的 `vta-install/PATH-A-OFFICIAL.md`（不随开源仓分发的私有路径以你本机为准）。开源仓内以本文 + [进阶页](/static/help-advanced.html) 为准。

## 何时才需要 CapsWriter

仅当你要 **不经外部 ASR、直接让 VTA `POST /api/transcribe` 吃 URL/本地媒体并在服务端出字** 时。模型体积大，开源默认按「可选」处理。

## 健康检查

```bash
curl -s http://127.0.0.1:8200/livez
curl -s http://127.0.0.1:8200/health
uv run python scripts/ops/smoke_check.py --base http://127.0.0.1:8200
```

`local_whisper` / CapsWriter / FunASR / LLM 任一 optional 项失败只会 `degraded`，不导致进程退出。

## local_whisper：模型与离线

### 推荐：engine: openai-whisper（本机已有 .pt 时）

aster-whisper 默认从 Hugging Face Hub 拉 CTranslate2 权重；**无外网 / Hub 超时**时会失败。
若本机已有 OpenAI Whisper 权重（常见路径 ~/.cache/whisper/tiny.pt），把 local_whisper.engine 设为 openai-whisper，即可离线出字，无需访问 Hub。

uto 模式会先试 faster-whisper，失败再回退 openai-whisper（Hub 超时会多等一会儿）。


首次跑某 `model`（如 `tiny` / `base` / `small`）时，`faster-whisper` / `openai-whisper` 会从 Hugging Face Hub **拉取权重**。若机器无外网或 Hub 不可达，会看到类似：

`cannot find the appropriate snapshot folder … check your internet connection`

**做法（任选）：**

1. **有网时预热一次**：用配置里的同一 Python 跑短音频，让模型落到缓存（Hugging Face 默认在用户目录的 `huggingface` / `hub` 缓存）。
2. **离线**：把已下载的模型目录拷到目标机，设置环境变量例如  
   `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`（以及必要时 `HF_HOME` / `HUGGINGFACE_HUB_CACHE` 指向该缓存）。
3. **指定较小模型**：`local_whisper.model` 用 `tiny` 或 `base`，CPU 更友好；长音频再换大模型。
4. **FunASR 不可达时**：关掉说话人识别，或依赖已落地的 FunASR→CapsWriter/`local_whisper` 回退；仍失败则走 **Path A**（外部 ASR → `import_markdown_to_view.py`）。

冒烟（需本机已装 whisper 且模型可本地解析）：

```bash
# 用配置中的 local_whisper.python
python -c "import faster_whisper; print('faster-whisper ok')"
# 或
python -c "import whisper; print('openai-whisper ok')"
```

## 仓内 Path A 脚本

```bash
uv run python scripts/ops/import_markdown_to_view.py path/to/transcript.md
```

详见 [path-a-markdown-import.md](path-a-markdown-import.md)。
