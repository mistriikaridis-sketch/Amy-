# Yuegao — Français

[中文](README.md) | [English](README.en.md) | **Français**

Transforme un lien en transcription lisible. À lancer en local : collez l’URL d’une vidéo, d’un podcast ou d’un audio, puis ouvrez la page de lecture.

Pas d’envoi de fichier audio ou vidéo local. Aucune clé d’API n’est livrée. Copiez `config/config.example.jsonc` vers `config/config.jsonc` et indiquez votre clé LLM.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Langues de l’interface : zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
Licence : [PolyForm Noncommercial](LICENSE). Guide complet : [English](README.en.md).
