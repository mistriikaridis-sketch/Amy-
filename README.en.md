# Yuegao (阅稿)

[中文](README.md) | **English** | [日本語](README.ja.md) | [Other languages](#documentation-languages)

> Turn links into readable transcripts. Run locally: paste a video / podcast / audio URL, then open the paper-style reading page.

**Yuegao** is a local-reading-oriented fork of [VideoTranscriptAPI](https://github.com/zlxlabs/VideoTranscriptAPI).

**Bring your own keys.** This repository ships **no** production API keys. Copy `config/config.example.jsonc` → `config/config.jsonc` and set your own LLM / optional TikHub tokens. Never commit `config.jsonc`, `users.json`, or `.env`.

**License**: [PolyForm Noncommercial License 1.0.0](LICENSE) — noncommercial use only. Keep every `Required Notice:` line.

Package id remains `video-transcript-api`; UI title is 阅稿 / Yuegao. Fork version **1.3.0**.

![Home](docs/images/home.png)

## Quick start

```bash
git clone <your-yuegao-repo-url>
cd yuegao
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
# edit config.jsonc: api.auth_token + llm.api_key / llm.base_url (your own keys)
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Smoke: `uv run python scripts/ops/smoke_check.py --base http://127.0.0.1:8200`

Local file upload is **off by default** (`VTA_UPLOADS_ENABLED` must be exactly `true` to enable). The UI only shows link transcription unless upload is enabled.

## Languages

UI switcher: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar (`?lang=` on static pages; `/view/...&lang=` on reading pages).  
Default site language: config `language`.

## ASR without CapsWriter

See [docs/guides/asr-degrade.md](docs/guides/asr-degrade.md) — Path A (Markdown → `/view`) and `LOCAL_WHISPER_PYTHON` / `AMY_PYTHON`.

## Security

[SECURITY.md](SECURITY.md) — LAN tokens, public `/view` links, optional Feishu/TikHub, no hosted minutes E2E.

## Documentation languages

- [中文](README.md) (full)
- [English](README.en.md) (this file)
- Stubs: [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [العربية](README.ar.md)

Do **not** push to `zlxlabs/VideoTranscriptAPI`. Use a new public repository URL.
