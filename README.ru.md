# Юэгао Yuegao — Русский

[中文](README.md) | [English](README.en.md) | **Русский**

Превращает ссылку в читаемую расшифровку. Запускается локально: вставьте URL видео, подкаста или аудио и откройте страницу чтения.

Загрузки локальных аудио и видео нет. Ключи API в репозиторий не входят. Скопируйте `config/config.example.jsonc` в `config/config.jsonc` и укажите свой ключ LLM.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

Языки интерфейса: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
Лицензия: [PolyForm Noncommercial](LICENSE). Полная инструкция: [English](README.en.md).
