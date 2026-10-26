"""健康检查路由

提供系统健康状态检查端点，检查 SQLite、ASR 服务、磁盘空间、LLM 配置等。
"""

import os
import shutil
import sqlite3
import asyncio
from typing import Dict, Any

from fastapi import APIRouter

from ..context import get_cache_manager, get_config, get_logger, lazy_resource

logger = lazy_resource(get_logger)
config = lazy_resource(get_config)

router = APIRouter(tags=["health"])


@router.get("/livez")
async def liveness_probe():
    """纯存活探针端点

    仅表明进程可响应，**不查询任何下游依赖**（CapsWriter / FunASR / 磁盘）。
    供部署探针与 Uptime Kuma 24×7 探活使用：下游抖动不应触发误判/回滚。
    需要下游状态时请用 /health（深度检查）。

    Returns:
        dict: 固定 {"status": "ok"}，恒返回 200
    """
    return {"status": "ok"}


@router.get("/health")
async def health_check():
    """系统健康检查端点

    检查各核心组件的状态，返回整体健康状况。
    可选依赖（CapsWriter / FunASR / LLM key）缺失时标记 degraded，
    并给出可操作的 degrade 说明，不假装全绿。

    Returns:
        dict: 健康状态摘要
    """
    checks = {}

    checks["sqlite"] = _check_sqlite()
    checks["disk_space"] = _check_disk_space()
    checks["capswriter"] = await _check_websocket_service(
        config.get("capswriter", {}).get("server_url", "ws://localhost:6016"),
        "CapsWriter",
        optional=True,
        degrade_hint="CapsWriter unavailable (not installed or protocol too old) — will try local Whisper fallback when enabled",
    )
    checks["funasr"] = await _check_websocket_service(
        config.get("funasr_spk_server", {}).get("server_url", "ws://localhost:8767"),
        "FunASR",
        optional=True,
        degrade_hint="FunASR missing — speaker diarization unavailable; plain transcription can still proceed",
    )
    checks["llm"] = _check_llm_config()
    checks["local_whisper"] = _check_local_whisper()

    # Required checks drive unhealthy; optional only degrade.
    required_ok = all(
        checks[k].get("healthy", False) for k in ("sqlite", "disk_space")
    )
    # ASR is usable if CapsWriter OR local_whisper is healthy.
    asr_ok = checks["capswriter"].get("healthy", False) or checks["local_whisper"].get(
        "healthy", False
    )
    any_optional_down = any(
        not checks[k].get("healthy", False) for k in ("funasr", "llm")
    ) or not asr_ok
    if not required_ok:
        status = "unhealthy"
    elif any_optional_down or not checks["capswriter"].get("healthy", False):
        # CapsWriter missing is always reported as degraded even when local whisper works.
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "checks": checks,
        "asr_mode": (
            "capswriter"
            if checks["capswriter"].get("healthy", False)
            else (
                "local_whisper"
                if checks["local_whisper"].get("healthy", False)
                else "unavailable"
            )
        ),
    }


def _check_sqlite() -> Dict[str, Any]:
    """检查 SQLite 数据库连通性"""
    try:
        cache_manager = get_cache_manager()
        conn = sqlite3.connect(str(cache_manager.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"healthy": True, "required": True}
    except Exception as e:
        logger.warning(f"SQLite health check failed: {e}")
        return {"healthy": False, "required": True, "error": str(e)}


async def _check_websocket_service(
    url: str,
    name: str,
    *,
    optional: bool = False,
    degrade_hint: str = "",
) -> Dict[str, Any]:
    """检查 WebSocket 服务连通性"""
    try:
        import websockets
        async with asyncio.timeout(5):
            async with websockets.connect(url, close_timeout=3):
                pass
        return {"healthy": True, "optional": optional}
    except ImportError:
        return _check_tcp_port(url, name, optional=optional, degrade_hint=degrade_hint)
    except asyncio.TimeoutError:
        logger.warning(f"{name} health check timed out: {url}")
        result = {
            "healthy": False,
            "optional": optional,
            "error": "connection timed out",
        }
        if degrade_hint:
            result["degrade_hint"] = degrade_hint
        return result
    except Exception as e:
        logger.warning(f"{name} health check failed: {url}, error: {e}")
        result = {"healthy": False, "optional": optional, "error": str(e)}
        if degrade_hint:
            result["degrade_hint"] = degrade_hint
        return result


def _check_tcp_port(
    url: str,
    name: str,
    *,
    optional: bool = False,
    degrade_hint: str = "",
) -> Dict[str, Any]:
    """通过 TCP 连接检查端口可达性（websockets 不可用时的后备方案）"""
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 80

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return {"healthy": True, "optional": optional}
        out = {
            "healthy": False,
            "optional": optional,
            "error": f"port {port} unreachable",
        }
        if degrade_hint:
            out["degrade_hint"] = degrade_hint
        return out
    except Exception as e:
        logger.warning(f"{name} TCP health check failed: {e}")
        out = {"healthy": False, "optional": optional, "error": str(e)}
        if degrade_hint:
            out["degrade_hint"] = degrade_hint
        return out


def _check_disk_space() -> Dict[str, Any]:
    """检查磁盘空间（Windows / Linux 通用：shutil.disk_usage）。

    当可用空间低于 1GB 时标记为不健康。
    """
    try:
        usage = shutil.disk_usage(".")
        free_gb = usage.free / (1024 ** 3)

        healthy = free_gb >= 1.0
        result = {
            "healthy": healthy,
            "required": True,
            "free_gb": round(free_gb, 2),
        }
        if not healthy:
            result["error"] = f"low disk space: {free_gb:.2f} GB"
        return result
    except Exception as e:
        logger.warning(f"Disk space check failed: {e}")
        return {"healthy": False, "required": True, "error": str(e)}


def _check_llm_config() -> Dict[str, Any]:
    """检查 LLM API key 是否已配置（不发起真实调用）。

    缺 key 时 Path A 导入 MD 仍可用；需要校对/总结时会失败。
    """
    try:
        llm = config.get("llm", {}) or {}
        key = (llm.get("api_key") or "").strip()
        placeholder = key in ("", "your-llm-api-key-here", "your-api-key-here")
        if placeholder:
            return {
                "healthy": False,
                "optional": True,
                "error": "llm.api_key not configured",
                "degrade_hint": (
                    "LLM key missing — calibration/summary disabled; "
                    "plain transcript / Amy MD → /view still works"
                ),
            }
        return {
            "healthy": True,
            "optional": True,
            "base_url": llm.get("base_url") or "",
            "summary_model": llm.get("summary_model") or "",
        }
    except Exception as e:
        return {
            "healthy": False,
            "optional": True,
            "error": str(e),
            "degrade_hint": "LLM config unreadable",
        }


def _check_local_whisper() -> Dict[str, Any]:
    """Probe external Python for faster-whisper / openai-whisper fallback."""
    try:
        from ...transcriber.local_whisper_client import is_available

        lw = config.get("local_whisper", {}) or {}
        ok, detail = is_available(lw if isinstance(lw, dict) else {})
        if ok:
            return {
                "healthy": True,
                "optional": True,
                "detail": detail,
                "role": "CapsWriter degrade path",
            }
        return {
            "healthy": False,
            "optional": True,
            "error": detail,
            "degrade_hint": (
                "local Whisper unavailable — install openai-whisper or faster-whisper "
                "in LOCAL_WHISPER_PYTHON / config.local_whisper.python; "
                "or use Path A (Amy MD import)"
            ),
        }
    except Exception as e:
        return {
            "healthy": False,
            "optional": True,
            "error": str(e),
            "degrade_hint": "local Whisper probe failed",
        }
