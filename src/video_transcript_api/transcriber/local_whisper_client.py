"""Local Whisper ASR fallback when CapsWriter is unavailable.

Uses a configured external Python that has faster-whisper or openai-whisper.
Runs out-of-process so this app's virtualenv does not need whisper packages.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logging import setup_logger, load_config

logger = setup_logger("local_whisper")

_HELPER = r'''
import json, sys, time
audio, out_txt, out_json, engine, model, language, device, compute_type = sys.argv[1:9]
language = None if language in ("", "auto", "None") else language
segments_out = []
text_parts = []
engine_used = engine
model_used = model
t0 = time.time()

def emit(segs):
    for s in segs:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        text_parts.append(text)
        segments_out.append({
            "start_time": float(s["start"]),
            "end_time": float(s["end"]),
            "text": text,
        })

if engine in ("auto", "faster-whisper"):
    try:
        from faster_whisper import WhisperModel
        if model in ("", "auto"):
            model = "tiny"
        model_used = model
        engine_used = "faster-whisper"
        wm = WhisperModel(model, device=device or "cpu", compute_type=compute_type or "int8")
        stream, info = wm.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
        )
        segs = [{"start": s.start, "end": s.end, "text": s.text} for s in stream]
        emit(segs)
    except Exception as exc:
        if engine == "faster-whisper":
            raise
        sys.stderr.write(
            "faster-whisper failed (often Hugging Face Hub offline / model not cached); "
            f"falling back to openai-whisper: {exc}\n"
        )
        engine = "openai-whisper"

if engine in ("auto", "openai-whisper") and not segments_out:
    try:
        import whisper
    except ImportError as exc:
        raise SystemExit(
            "openai-whisper is not installed in local_whisper.python; "
            "pip install openai-whisper in that interpreter, or set engine/faster-whisper with a cached model. "
            f"detail={exc}"
        )
    if model_used in ("", "auto") or engine_used == "faster-whisper" and not segments_out:
        if model in ("", "auto"):
            model = "tiny"
        model_used = model
    engine_used = "openai-whisper"
    try:
        wm = whisper.load_model(model_used)
    except Exception as exc:
        raise SystemExit(
            f"openai-whisper could not load model={model_used!r}. "
            "Pre-download once online into ~/.cache/whisper (tiny.pt / base.pt), "
            "or copy those files onto this machine. "
            f"detail={exc}"
        )
    result = wm.transcribe(audio, language=language, fp16=False)
    segs = result.get("segments") or []
    emit([{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segs])
    if not text_parts and result.get("text"):
        text_parts.append(result["text"].strip())

text = "\n".join(text_parts).strip()
if not text:
    raise SystemExit(
    "empty transcript from local whisper "
    "(no speech detected in audio, or ASR returned blank — not a missing-model error if load_model succeeded)"
)
Path = __import__("pathlib").Path
Path(out_txt).write_text(text + "\n", encoding="utf-8")
payload = {
    "task_id": "local_whisper",
    "file_name": Path(audio).name,
    "duration": segments_out[-1]["end_time"] if segments_out else 0,
    "segments": segments_out,
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "processing_time": time.time() - t0,
    "error": None,
    "engine": engine_used,
    "model": model_used,
}
Path(out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"ok": True, "chars": len(text), "segments": len(segments_out),
                  "engine": engine_used, "model": model_used,
                  "seconds": round(time.time() - t0, 1)}, ensure_ascii=False))
'''


def _cfg() -> Dict[str, Any]:
    try:
        return (load_config().get("local_whisper") or {})
    except Exception:
        return {}


def is_available(config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Return (ok, detail) for health checks."""
    cfg = config if config is not None else _cfg()
    if cfg.get("enabled") is False:
        return False, "local_whisper.enabled=false"
    python = (cfg.get("python") or "").strip() or _default_python()
    if not python or not Path(python).exists():
        return False, f"python not found: {python or '(unset)'}"
    try:
        proc = subprocess.run(
            [
                python,
                "-c",
                "import importlib.util as u; "
                "print('fw' if u.find_spec('faster_whisper') else ''); "
                "print('ow' if u.find_spec('whisper') else '')",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return False, f"python probe failed: {exc}"
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    has_fw = "fw" in lines
    has_ow = "ow" in lines
    if not (has_fw or has_ow):
        return False, f"neither faster_whisper nor openai-whisper in {python}"
    engines = []
    if has_fw:
        engines.append("faster-whisper")
    if has_ow:
        engines.append("openai-whisper")
    return True, f"{python} ({', '.join(engines)})"


def _default_python() -> str:
    """Resolve a Whisper interpreter from config/env only. No machine-specific paths."""
    candidates = [
        os.environ.get("LOCAL_WHISPER_PYTHON") or "",
        os.environ.get("AMY_PYTHON") or "",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return ""


class LocalWhisperClient:
    """Run local Whisper and write CapsWriter-compatible txt + funasr json."""

    def __init__(self, output_dir: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else load_config()
        lw = self.config.get("local_whisper") or {}
        self.enabled = lw.get("enabled", True)
        self.python = (lw.get("python") or "").strip() or _default_python()
        self.engine = lw.get("engine", "auto")
        self.model = lw.get("model", "tiny")
        self.language = lw.get("language", "zh")
        self.device = lw.get("device", "cpu")
        self.compute_type = lw.get("compute_type", "int8")
        self.timeout = int(lw.get("timeout_seconds", 7200))
        storage = self.config.get("storage") or {}
        self.output_dir = output_dir or storage.get("workspace_dir") or "./data/workspace"
        os.makedirs(self.output_dir, exist_ok=True)
        self.last_failure_detail = ""

    def transcribe_file(
        self, file_path: str, media_duration: Optional[float] = None
    ) -> Tuple[bool, List[Path]]:
        self.last_failure_detail = ""
        if not self.enabled:
            self.last_failure_detail = "local_whisper disabled"
            return False, []
        ok, detail = is_available(self.config.get("local_whisper") or {"python": self.python, "enabled": True})
        if not ok:
            self.last_failure_detail = detail
            return False, []

        audio = Path(file_path)
        if not audio.exists():
            self.last_failure_detail = f"audio missing: {audio}"
            return False, []

        base = audio.stem
        out_dir = Path(self.output_dir)
        out_txt = out_dir / f"{base}.txt"
        out_json = out_dir / f"{base}_funasr.json"

        helper = tempfile.NamedTemporaryFile(
            "w", suffix="_lw_helper.py", delete=False, encoding="utf-8"
        )
        try:
            helper.write(_HELPER)
            helper.close()
            cmd = [
                self.python,
                helper.name,
                str(audio),
                str(out_txt),
                str(out_json),
                str(self.engine),
                str(self.model),
                str(self.language or "auto"),
                str(self.device),
                str(self.compute_type),
            ]
            logger.info(
                "local_whisper start audio=%s engine=%s model=%s python=%s",
                audio,
                self.engine,
                self.model,
                self.python,
            )
            t0 = time.time()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            elapsed = time.time() - t0
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()[-800:]
                self.last_failure_detail = f"local_whisper exit={proc.returncode}: {err}"
                logger.error(self.last_failure_detail)
                return False, []
            if not out_txt.exists() or out_txt.stat().st_size == 0:
                self.last_failure_detail = "local_whisper produced empty txt"
                return False, []
            generated = [out_txt]
            if out_json.exists():
                generated.append(out_json)
            meta = (proc.stdout or "").strip().splitlines()
            logger.info(
                "local_whisper done in %.1fs meta=%s files=%s",
                elapsed,
                meta[-1] if meta else "",
                [str(p) for p in generated],
            )
            return True, generated
        except subprocess.TimeoutExpired:
            self.last_failure_detail = f"local_whisper timeout after {self.timeout}s"
            logger.error(self.last_failure_detail)
            return False, []
        except Exception as exc:
            self.last_failure_detail = f"local_whisper error: {exc}"
            logger.exception(self.last_failure_detail)
            return False, []
        finally:
            try:
                os.unlink(helper.name)
            except Exception:
                pass
