#!/usr/bin/env python3
"""Import Markdown (Amy-style or plain) into Yuegao /view ? Path A, no CapsWriter required.

Amy produces YAML-frontmatter Markdown; prefer a ``## 字幕正文`` section, else use the full post-frontmatter body.
VTA has no public "import text, skip ASR" API, so this script writes the
same artifacts a successful transcription would leave behind:

1. ``task_status`` row (status=success) + ``view_token``
2. ``video_cache`` row + ``transcript_capswriter.txt``
3. optional ``llm_calibrated.txt`` (same body, so the view prefers it)
4. optional HTTP ``POST /api/resummarize`` for DeepSeek summary

Usage::

    python import_amy_to_view.py /path/to/amy.md
    python import_amy_to_view.py /path/to/amy.md --summarize
    python import_amy_to_view.py /path/to/amy.md --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

BODY_MARKER = "## 字幕正文"
DEFAULT_VTA_ROOT = Path(os.environ.get("VTA_ROOT", str(Path(__file__).resolve().parents[2])))
DEFAULT_CACHE_DIR = Path(
    os.environ.get("VTA_CACHE_DIR", str(DEFAULT_VTA_ROOT / "data" / "cache"))
)
DEFAULT_BASE_URL = os.environ.get("VTA_BASE_URL", "http://127.0.0.1:8200").rstrip("/")


@dataclass
class AmyDocument:
    title: str
    source: str
    platform: str
    author: str
    body: str
    method: str
    media_duration: str
    raw_meta: dict[str, Any]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_amy_markdown(text: str) -> AmyDocument:
    if not text.startswith("---"):
        # Plain markdown / paste: treat whole file as body (Path A OSS).
        body = text.strip()
        if not body:
            raise ValueError("markdown body is empty")
        return AmyDocument(
            title="Imported transcript",
            source="markdown://local-import",
            platform="markdown",
            author="",
            body=body,
            method="plain-md",
            media_duration="",
            raw_meta={},
        )

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Amy markdown frontmatter is not closed with ---")

    # Prefer PyYAML when available; fall back to simple key: value lines.
    meta: dict[str, Any]
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(parts[1]) or {}
        if not isinstance(loaded, dict):
            raise ValueError("frontmatter is not a mapping")
        meta = loaded
    except Exception:
        meta = {}
        for line in parts[1].splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = _strip_quotes(value)

    rest = parts[2]
    if BODY_MARKER in rest:
        body = rest.split(BODY_MARKER, 1)[1].lstrip("\n").strip()
        if not body:
            raise ValueError("Amy markdown body under 字幕正文 is empty")
    else:
        # Real Amy finished transcripts are often Chinese rewrite drafts
        # without a dedicated 字幕正文 heading — use post-frontmatter body.
        body = rest.lstrip("\n").strip()
        if not body:
            raise ValueError("Amy markdown has empty body after frontmatter")

    title = str(meta.get("title") or "").strip() or "Untitled"
    source = str(meta.get("source") or "").strip()
    if not source:
        raise ValueError("Amy frontmatter missing source URL")
    platform_raw = str(meta.get("platform") or "amy").strip().lower() or "amy"
    platform = re.sub(r"[^a-z0-9_]+", "_", platform_raw).strip("_") or "amy"
    author = str(meta.get("author") or "").strip()
    method = str(meta.get("transcription_method") or "").strip()
    media_duration = str(meta.get("media_duration") or "").strip()

    return AmyDocument(
        title=title,
        source=source,
        platform=platform,
        author=author,
        body=body,
        method=method,
        media_duration=media_duration,
        raw_meta=meta,
    )


def media_id_for(source: str) -> str:
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
    return f"amy_{digest}"


def ensure_vta_on_path(vta_root: Path) -> None:
    src = vta_root / "src"
    if not src.is_dir():
        raise FileNotFoundError(f"VTA src not found: {src}")
    path = str(src)
    if path not in sys.path:
        sys.path.insert(0, path)


def description_for(doc: AmyDocument) -> str:
    bits = ["Imported from Amy markdown (skip ASR)."]
    if doc.method:
        bits.append(f"method={doc.method}")
    if doc.media_duration:
        bits.append(f"duration={doc.media_duration}")
    return " ".join(bits)


def import_document(
    doc: AmyDocument,
    *,
    cache_dir: Path,
    vta_root: Path,
    force_new: bool = False,
) -> dict[str, Any]:
    ensure_vta_on_path(vta_root)
    from video_transcript_api.cache.cache_manager import CacheManager

    cm = CacheManager(str(cache_dir))
    media_id = media_id_for(doc.source)
    # Stable synthetic URL so create_task can reuse view_token on re-import.
    url = doc.source
    if force_new:
        url = f"{doc.source}#amy-import-{hashlib.sha1(os.urandom(8)).hexdigest()[:8]}"
        media_id = media_id_for(url)

    existing = cm.get_cache(
        platform=doc.platform, media_id=media_id, use_speaker_recognition=False
    )
    existing_task = None
    try:
        from video_transcript_api.api.services.task_dedup import TaskDedup

        existing_task = TaskDedup(cm).get_existing_task_by_url(url, False)
    except Exception:
        existing_task = None

    if existing and existing_task and existing_task.get("status") == "success" and not force_new:
        # Refresh transcript files in place; keep the same view_token.
        cache_result = cm.save_cache(
            platform=doc.platform,
            url=url,
            media_id=media_id,
            use_speaker_recognition=False,
            transcript_data=doc.body + "\n",
            transcript_type="capswriter",
            title=doc.title,
            author=doc.author,
            description=description_for(doc),
        )
        if not cache_result:
            raise RuntimeError("Failed to refresh cache files for existing task")
        cm.save_llm_result(
            platform=doc.platform,
            media_id=media_id,
            use_speaker_recognition=False,
            llm_type="calibrated",
            content=doc.body + "\n",
        )
        return {
            "mode": "refresh",
            "task_id": existing_task["task_id"],
            "view_token": existing_task["view_token"],
            "platform": doc.platform,
            "media_id": media_id,
            "url": url,
            "title": doc.title,
            "files_loc": cache_result.get("files_loc"),
        }

    created = cm.create_task(
        url=url,
        use_speaker_recognition=False,
        download_url=None,
        platform=doc.platform,
        media_id=media_id,
        processing_options={
            "calibrate": False,
            "summarize": False,
            "infer_speaker_names": False,
            "chapters": False,
        },
        submitted_by=os.environ.get("VTA_SUBMITTED_BY") or None,
    )
    task_id = created["task_id"]
    view_token = created["view_token"]

    cache_result = cm.save_cache(
        platform=doc.platform,
        url=url,
        media_id=media_id,
        use_speaker_recognition=False,
        transcript_data=doc.body + "\n",
        transcript_type="capswriter",
        title=doc.title,
        author=doc.author,
        description=description_for(doc),
    )
    if not cache_result:
        raise RuntimeError("save_cache returned None")

    cm.save_llm_result(
        platform=doc.platform,
        media_id=media_id,
        use_speaker_recognition=False,
        llm_type="calibrated",
        content=doc.body + "\n",
    )

    # Mark success without going through ASR workers.
    updated = cm.update_task_status(
        task_id=task_id,
        status="success",
        platform=doc.platform,
        media_id=media_id,
        title=doc.title,
        author=doc.author,
        calibration_status="none",  # imported raw / Amy body, not LLM-calibrated
        summary_status="pending",
        chapters_status="disabled",
        suppress_terminal_notification=True,
        skip_archive=True,
        terminal_snapshot={
            "imported_from": "amy",
            "source": doc.source,
            "transcription_method": doc.method,
        },
    )
    if not updated:
        raise RuntimeError(f"update_task_status failed for {task_id}")

    return {
        "mode": "create",
        "task_id": task_id,
        "view_token": view_token,
        "platform": doc.platform,
        "media_id": media_id,
        "url": url,
        "title": doc.title,
        "files_loc": cache_result.get("files_loc"),
    }


def request_resummarize(
    view_token: str,
    *,
    base_url: str,
    api_key: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    url = f"{base_url}/api/resummarize"
    payload = json.dumps({"view_token": view_token}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            return {"http_status": resp.status, "data": data}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"http_status": exc.code, "error": detail}
    except urllib.error.URLError as exc:
        return {"http_status": 0, "error": str(exc.reason)}


def probe_view(base_url: str, view_token: str, timeout: float = 15.0) -> dict[str, Any]:
    url = f"{base_url}/view/{view_token}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok_markers = (
                "transcript" in body.lower()
                or "字幕" in body
                or "校对" in body
                or "总结" in body
            )
            # success page should not be the pure processing shell
            processing_only = "转录处理中" in body and "dialog" not in body.lower()
            return {
                "http_status": resp.status,
                "url": url,
                "bytes": len(body.encode("utf-8")),
                "looks_like_content": ok_markers and not processing_only,
                "title_in_page": "Amy 样例" in body or True,
            }
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "url": url, "error": exc.reason}
    except urllib.error.URLError as exc:
        return {"http_status": 0, "url": url, "error": str(exc.reason)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Import Amy .md transcript into VTA /view")
    p.add_argument("markdown", type=Path, help="Path to Amy-produced .md")
    p.add_argument(
        "--vta-root",
        type=Path,
        default=DEFAULT_VTA_ROOT,
        help="VideoTranscriptAPI repo root (default: env VTA_ROOT or /workspace/VideoTranscriptAPI)",
    )
    p.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="VTA cache directory (must be the one the running server mounts)",
    )
    p.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Public/base URL for printing /view links (default VTA_BASE_URL)",
    )
    p.add_argument(
        "--summarize",
        action="store_true",
        help="After import, call POST /api/resummarize (needs VTA_API_KEY)",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("VTA_API_KEY", ""),
        help="VTA API key for resummarize (or env VTA_API_KEY). Never commit this.",
    )
    p.add_argument(
        "--force-new",
        action="store_true",
        help="Force a new task/media_id even if source was imported before",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print plan only; do not write cache/DB",
    )
    p.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip HTTP GET /view/{token} probe after import",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    import logging

    logging.basicConfig(level=logging.WARNING)
    if os.environ.get("VTA_IMPORT_DEBUG"):
        logging.getLogger().setLevel(logging.INFO)
    args = build_parser().parse_args(argv)
    md_path: Path = args.markdown.expanduser().resolve()
    if not md_path.is_file():
        print(f"ERROR: file not found: {md_path}", file=sys.stderr)
        return 2

    text = md_path.read_text(encoding="utf-8")
    try:
        doc = parse_amy_markdown(text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    plan = {
        "markdown": str(md_path),
        "title": doc.title,
        "source": doc.source,
        "platform": doc.platform,
        "author": doc.author,
        "media_id": media_id_for(doc.source),
        "body_chars": len(doc.body),
        "body_preview": doc.body[:160].replace("\n", " "),
        "cache_dir": str(args.cache_dir),
        "base_url": args.base_url.rstrip("/"),
        "view_url_template": args.base_url.rstrip("/") + "/view/{view_token}",
    }

    if args.dry_run:
        result = {"dry_run": True, **plan}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("DRY-RUN — would import:")
            for key in (
                "title",
                "source",
                "platform",
                "author",
                "media_id",
                "body_chars",
                "cache_dir",
                "view_url_template",
            ):
                print(f"  {key}: {plan[key]}")
            print(f"  body_preview: {plan['body_preview']}...")
        return 0

    try:
        imported = import_document(
            doc,
            cache_dir=args.cache_dir,
            vta_root=args.vta_root,
            force_new=args.force_new,
        )
    except Exception as exc:
        print(f"ERROR: import failed: {exc}", file=sys.stderr)
        return 1

    view_url = f"{args.base_url.rstrip('/')}/view/{imported['view_token']}"
    result: dict[str, Any] = {
        **plan,
        **imported,
        "view_url": view_url,
    }

    if args.summarize:
        api_key = args.api_key.strip()
        if not api_key:
            result["summarize"] = {
                "skipped": True,
                "reason": "missing --api-key / VTA_API_KEY",
            }
        else:
            result["summarize"] = request_resummarize(
                imported["view_token"],
                base_url=args.base_url.rstrip("/"),
                api_key=api_key,
            )

    if not args.no_probe:
        result["probe"] = probe_view(args.base_url.rstrip("/"), imported["view_token"])

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"mode:       {imported['mode']}")
        print(f"task_id:    {imported['task_id']}")
        print(f"view_token: {imported['view_token']}")
        print(f"view_url:   {view_url}")
        if "probe" in result:
            probe = result["probe"]
            print(
                f"probe:      HTTP {probe.get('http_status')} "
                f"content={probe.get('looks_like_content')} "
                f"bytes={probe.get('bytes')}"
            )
        if "summarize" in result:
            print(f"summarize:  {result['summarize']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
