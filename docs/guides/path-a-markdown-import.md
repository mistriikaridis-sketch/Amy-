# Path A: Markdown to /view

Import an existing transcript (Amy-style YAML Markdown or plain .md) into Yuegao without CapsWriter / FunASR.

`ash
uv run python scripts/ops/import_markdown_to_view.py path/to/transcript.md
uv run python scripts/ops/import_markdown_to_view.py path/to/transcript.md --summarize
`

Optional env: VTA_ROOT (repo root), VTA_CACHE_DIR, VTA_BASE_URL (default http://127.0.0.1:8200).

See also [asr-degrade.md](asr-degrade.md).
