# Yuegao (阅稿)

[中文](README.md) | **English** | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Português](README.pt.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [العربية](README.ar.md)

> Turn a link into a readable transcript. Run it locally: paste a video, podcast, or audio URL, then open the paper reading page.

The product accepts **links only**. The submit page does not offer local audio or video upload.

**Bring your own keys.** This repository ships no production API keys. Copy `config/config.example.jsonc` to `config/config.jsonc` and set your own LLM key and optional downloader tokens. Never commit `config.jsonc`, `users.json`, or `.env`.

**License**: [PolyForm Noncommercial License 1.0.0](LICENSE) — noncommercial use only. Keep every `Required Notice:` line.

The package id remains `video-transcript-api`. The UI title is 阅稿 / Yuegao. Version **1.3.0**.

![Home](docs/images/home.png)

## Quick start

```bash
git clone <your-yuegao-repo-url>
cd yuegao
# Install uv: https://docs.astral.sh/uv/
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
# Edit config.jsonc: api.auth_token plus llm.api_key / llm.base_url
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Open the home page in a browser. The example config listens on port `8000`; some deploy notes use `8200`.

Smoke check: `uv run python scripts/ops/smoke_check.py --base http://127.0.0.1:8000`

## What you supply

- Your own LLM key, stored only in `config/config.jsonc` (gitignored).
- Optional downloader keys (for example TikHub) when you want those sites.
- Optional local Whisper. If CapsWriter is not running, point `LOCAL_WHISPER_PYTHON` or `AMY_PYTHON` at an interpreter that already has faster-whisper or openai-whisper. Do not commit a machine-specific path.

`capswriter-asr` and `llm-compat` install from public Git repositories. See `[tool.uv.sources]` in `pyproject.toml`.

## Languages

The home, submit, history, and reading pages switch among zh-CN, en, ja, ko, es, fr, pt, de, ru, and ar.

Static pages take `?lang=`. Reading pages take `/view/...&lang=`. The default is the `language` field in config.

## Security

See [SECURITY.md](SECURITY.md). A `/view/{token}` URL is a public read-only capability: anyone with the link can read that transcript. Do not expose a LAN deploy to the open internet without a proxy or VPN. Do not commit `config/config.jsonc`, `config/users.json`, `.env`, or `data/`.

## Upstream

This tree is a local-reading fork. Its paper UI is Yuegao's own. Do not push to `zlxlabs/VideoTranscriptAPI`. Publish to your own repository URL.
