# Yuegao — Deutsch

[中文](README.md) | [English](README.en.md) | **Deutsch**

Macht aus einem Link eine lesbare Abschrift. Lokal ausführen: Video-, Podcast- oder Audio-URL einfügen und die Leseseite öffnen.

Es gibt keinen Upload lokaler Audio- oder Videodateien. API-Schlüssel liegen nicht im Repository. Kopieren Sie `config/config.example.jsonc` nach `config/config.jsonc` und tragen Sie Ihren eigenen LLM-Schlüssel ein.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Oberflächensprachen: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
Lizenz: [PolyForm Noncommercial](LICENSE). Vollständige Anleitung: [English](README.en.md).
