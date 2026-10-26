# Yuegao — Português

[中文](README.md) | [English](README.en.md) | **Português**

Transforma um link numa transcrição legível. Corre localmente: cole o URL de um vídeo, podcast ou áudio e abra a página de leitura.

Não há envio de áudio ou vídeo local. O repositório não traz chaves de API. Copie `config/config.example.jsonc` para `config/config.jsonc` e use a sua chave de LLM.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Idiomas da interface: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
Licença: [PolyForm Noncommercial](LICENSE). Guia completo: [English](README.en.md).
