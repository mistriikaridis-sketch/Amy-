# Yuegao — Español

[中文](README.md) | [English](README.en.md) | **Español**

Convierte un enlace en una transcripción legible. Se ejecuta en local: pega la URL de un vídeo, pódcast o audio y abre la página de lectura.

No hay subida de audio o vídeo local. El repositorio no incluye claves de API. Copia `config/config.example.jsonc` a `config/config.jsonc` y pon tu propia clave de LLM.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Idiomas de la interfaz: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
Licencia: [PolyForm Noncommercial](LICENSE). Guía completa: [English](README.en.md).
