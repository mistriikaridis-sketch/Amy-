#!/usr/bin/env python3
"""Open-source smoke check for a running VTA instance.

Usage:
  python scripts/ops/smoke_check.py
  python scripts/ops/smoke_check.py --base http://127.0.0.1:8200 --view-token view_xxx

Exit 0 if /livez is 200 and required /health checks (sqlite, disk) are healthy.
Optional CapsWriter / FunASR / LLM may be degraded — printed, not fatal.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.status, json.loads(body) if body.strip().startswith("{") else body


def main() -> int:
    ap = argparse.ArgumentParser(description="VTA smoke check")
    ap.add_argument("--base", default="http://127.0.0.1:8200")
    ap.add_argument("--view-token", default="", help="optional /view token to GET")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    failures = []

    print(f"=== VTA smoke @ {base} ===")
    try:
        status, live = get_json(f"{base}/livez")
        if status == 200 and isinstance(live, dict) and live.get("status") == "ok":
            print("[OK] /livez 200")
        else:
            failures.append(f"/livez unexpected: {status} {live}")
            print(f"[FAIL] /livez {status} {live}")
    except Exception as exc:
        failures.append(f"/livez unreachable: {exc}")
        print(f"[FAIL] /livez unreachable: {exc}")

    try:
        status, health = get_json(f"{base}/health", timeout=20)
        print(f"[INFO] /health status={health.get('status') if isinstance(health, dict) else health}")
        if isinstance(health, dict):
            checks = health.get("checks") or {}
            for name, detail in checks.items():
                ok = detail.get("healthy")
                mark = "OK" if ok else ("INFO" if detail.get("optional") else "FAIL")
                line = f"[{mark}] {name}: healthy={ok}"
                if detail.get("error"):
                    line += f" error={detail['error']}"
                if detail.get("degrade_hint"):
                    line += f" | {detail['degrade_hint']}"
                if detail.get("free_gb") is not None:
                    line += f" free_gb={detail['free_gb']}"
                print(line)
                if name in ("sqlite", "disk_space") and not ok:
                    failures.append(f"required check failed: {name}")
    except Exception as exc:
        failures.append(f"/health failed: {exc}")
        print(f"[FAIL] /health: {exc}")

    if args.view_token:
        url = f"{base}/view/{args.view_token}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                code = resp.status
                body = resp.read(2000).decode("utf-8", "replace")
            if code == 200:
                print(f"[OK] /view HTTP 200 ({url})")
            else:
                failures.append(f"/view HTTP {code}")
                print(f"[FAIL] /view HTTP {code}")
            for brand in ("zlxlabs", "VideoTranscriptAPI", "bylixing", "张立行"):
                if brand in body:
                    print(f"[WARN] brand remnant in first 2KB of /view: {brand}")
        except Exception as exc:
            failures.append(f"/view fetch failed: {exc}")
            print(f"[FAIL] /view: {exc}")

    print()
    if failures:
        print("SMOKE FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
