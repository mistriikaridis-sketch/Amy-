# 閲稿 Yuegao — 日本語

[中文](README.md) | [English](README.en.md) | **日本語** | [Other languages](README.en.md#languages)

リンクを、読める原稿にします。手元で動かし、動画・ポッドキャスト・音声の URL を貼って、紙のような読書頁を開きます。

ローカルの音声・動画ファイルのアップロードはありません。API キーは同梱しません。`config/config.example.jsonc` を `config/config.jsonc` にコピーし、自分の LLM キーを書いてください。

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

界面言語: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar。  
ライセンス: [PolyForm Noncommercial](LICENSE)（非商用）。手順の詳細は [English](README.en.md)。
