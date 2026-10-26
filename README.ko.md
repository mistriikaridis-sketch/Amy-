# 열람 Yuegao — 한국어

[中文](README.md) | [English](README.en.md) | **한국어**

링크를 읽을 수 있는 원고로 바꿉니다. 로컬에서 실행하고, 동영상·팟캐스트·오디오 URL을 붙여 종이 느낌의 읽기 페이지를 엽니다.

로컬 오디오·비디오 업로드는 없습니다. API 키는 저장소에 들어 있지 않습니다. `config/config.example.jsonc`를 `config/config.jsonc`로 복사한 뒤 본인 LLM 키를 넣으세요.

```bash
uv sync
cp config/config.example.jsonc config/config.jsonc
cp config/users.example.json config/users.json
uv run python main.py --check-config --config config/config.jsonc
uv run python main.py --start
```

UI 언어: zh-CN, en, ja, ko, es, fr, pt, de, ru, ar.  
라이선스: [PolyForm Noncommercial](LICENSE) (비상업). 자세한 단계는 [English](README.en.md).
