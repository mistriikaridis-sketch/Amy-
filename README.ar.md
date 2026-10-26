# يويغاو Yuegao — العربية

[中文](README.md) | [English](README.en.md) | **العربية**

يحوّل الرابط إلى نص مقروء. يعمل محلياً: الصق رابط فيديو أو بودكاست أو صوت، ثم افتح صفحة القراءة.

لا يوجد رفع لملفات صوت أو فيديو محلية. المستودع لا يتضمن مفاتيح API. انسخ `config/config.example.jsonc` إلى `config/config.jsonc` وضع مفتاح النموذج اللغوي الخاص بك.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

لغات الواجهة: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
الترخيص: [PolyForm Noncommercial](LICENSE). الدليل الكامل: [English](README.en.md).
