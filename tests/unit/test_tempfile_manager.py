"""Unit tests for the task-scoped TempFileManager.

Covers the data/temp cleanup design:
- per-task directory isolation (clean_up_task deletes only one task's files)
- in-progress protection (sweep skips active task dirs even when stale)
- thread-local current-task binding (create_temp_file/dir land in the task dir)
- configurable retention + throttled lazy sweep
- shared singleton identity

All tests are filesystem-only, no network, no services.
"""
import os
import time
from pathlib import Path

import pytest

from src.video_transcript_api.utils.tempfile_manager import (
    TempFileManager,
    get_shared_temp_manager,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr(tmp_path):
    """A TempFileManager rooted at a throwaway temp dir."""
    return TempFileManager(str(tmp_path / "temp"), retention_hours=24)


def _age(path: Path, hours: float) -> None:
    """Backdate a file/dir mtime by `hours` so it looks stale to the sweep."""
    old = time.time() - hours * 3600
    os.utime(path, (old, old))


def _write(path: Path, size: int = 1024) -> None:
    path.write_bytes(b"x" * size)


# ---------------------------------------------------------------------------
# Task directory lifecycle
# ---------------------------------------------------------------------------

def test_create_task_dir_under_base(mgr):
    d = mgr.create_task_dir("abc")
    assert d.exists() and d.is_dir()
    assert d.parent == mgr.base_dir
    assert d.name == "task_abc"


def test_clean_up_task_isolation(mgr):
    """clean_up_task removes only its own task's files, never another task's."""
    da = mgr.create_task_dir("A")
    db = mgr.create_task_dir("B")
    _write(da / "video.mp4")
    _write(db / "video.mp4")  # same filename, different task — must not collide

    mgr.clean_up_task("A")

    assert not da.exists()
    assert db.exists() and (db / "video.mp4").exists()


def test_clean_up_task_missing_dir_no_crash(mgr):
    """Cleaning a task that was never registered is a no-op, not an error."""
    assert mgr.clean_up_task("never-existed") == 0


def test_clean_up_task_returns_freed_bytes(mgr):
    d = mgr.create_task_dir("A")
    _write(d / "a.bin", 2048)
    _write(d / "b.bin", 1024)
    freed = mgr.clean_up_task("A")
    assert freed == 3072


# ---------------------------------------------------------------------------
# Thread-local current-task binding
# ---------------------------------------------------------------------------

def test_create_temp_file_lands_in_current_task_dir(mgr):
    mgr.create_task_dir("T1")
    mgr.set_current_task("T1")
    f = mgr.create_temp_file(suffix=".m4a")
    assert f.parent == mgr.get_task_dir("T1")
    assert f.suffix == ".m4a"


def test_create_temp_dir_lands_in_current_task_dir(mgr):
    mgr.create_task_dir("T1")
    mgr.set_current_task("T1")
    sub = mgr.create_temp_dir(prefix="bbdown_")
    assert sub.parent == mgr.get_task_dir("T1")


def test_create_temp_file_without_current_task_uses_base(mgr):
    mgr.clear_current_task()
    f = mgr.create_temp_file(suffix=".tmp")
    assert f.parent == mgr.base_dir


def test_clear_current_task_resets_binding(mgr):
    mgr.create_task_dir("T1")
    mgr.set_current_task("T1")
    mgr.clear_current_task()
    f = mgr.create_temp_file(suffix=".tmp")
    assert f.parent == mgr.base_dir


def test_get_current_task_dir_creates_when_set(mgr):
    """If a current task is set but its dir not yet created, it is created lazily."""
    mgr.set_current_task("LAZY")
    d = mgr.get_current_task_dir()
    assert d.exists()
    assert d.name == "task_LAZY"


# ---------------------------------------------------------------------------
# Active-task tracking + in-progress protection
# ---------------------------------------------------------------------------

def test_mark_active_and_done(mgr):
    mgr.mark_active("A")
    assert mgr.is_active("A")
    mgr.mark_done("A")
    assert not mgr.is_active("A")


def test_sweep_deletes_orphan_task_dir(mgr):
    """A stale task dir with no active task (crash leftover) is swept."""
    d = mgr.create_task_dir("ORPHAN")
    _write(d / "leftover.mp4")
    _age(d / "leftover.mp4", hours=48)
    _age(d, hours=48)

    count = mgr.clean_up_old_files(hours=24)

    assert count >= 1
    assert not d.exists()


def test_sweep_skips_active_task_dir_even_when_stale(mgr):
    """CRITICAL: an active (in-flight) task is protected from the sweep
    regardless of how old its files look (multi-hour live download)."""
    d = mgr.create_task_dir("LIVE")
    _write(d / "recording.mp4")
    _age(d / "recording.mp4", hours=48)
    _age(d, hours=48)
    mgr.mark_active("LIVE")

    mgr.clean_up_old_files(hours=24)

    assert d.exists() and (d / "recording.mp4").exists()


def test_sweep_deletes_stale_loose_file_keeps_recent(mgr):
    stale = mgr.base_dir / "stale.mp4"
    recent = mgr.base_dir / "recent.mp4"
    _write(stale)
    _write(recent)
    _age(stale, hours=48)

    mgr.clean_up_old_files(hours=24)

    assert not stale.exists()
    assert recent.exists()


def test_sweep_honors_hours_argument(mgr):
    f = mgr.base_dir / "f.mp4"
    _write(f)
    _age(f, hours=10)

    # 12h retention: 10h-old file survives
    mgr.clean_up_old_files(hours=12)
    assert f.exists()

    # 6h retention: now it is swept
    mgr.clean_up_old_files(hours=6)
    assert not f.exists()


def test_sweep_uses_configured_retention_by_default(tmp_path):
    mgr = TempFileManager(str(tmp_path / "temp"), retention_hours=6)
    f = mgr.base_dir / "f.mp4"
    _write(f)
    _age(f, hours=8)
    mgr.clean_up_old_files()  # no arg -> use configured 6h
    assert not f.exists()


# ---------------------------------------------------------------------------
# Consistency: no unbounded growth
# ---------------------------------------------------------------------------

def test_clean_up_task_drops_tracked_entries(mgr):
    """Files created via create_temp_file are dropped from the global tracked
    list once their task is cleaned, so the list cannot grow unbounded."""
    mgr.create_task_dir("A")
    mgr.set_current_task("A")
    mgr.create_temp_file(suffix=".m4a")
    assert any(mgr.base_dir / "task_A" in p.parents or p.parent == mgr.get_task_dir("A")
               for p in mgr.temp_files)
    mgr.clean_up_task("A")
    assert all(mgr.get_task_dir("A") != p.parent for p in mgr.temp_files)
    assert mgr.get_task_dir("A") is None


# ---------------------------------------------------------------------------
# Throttled lazy sweep
# ---------------------------------------------------------------------------

def test_maybe_sweep_throttled(mgr):
    """Second maybe_sweep within the interval is skipped (returns -1 sentinel)."""
    first = mgr.maybe_sweep(min_interval_seconds=1800)
    assert first >= 0  # ran
    second = mgr.maybe_sweep(min_interval_seconds=1800)
    assert second == -1  # throttled


def test_maybe_sweep_runs_after_interval(mgr):
    mgr.maybe_sweep(min_interval_seconds=1800)
    # interval 0 -> always allowed to run again
    assert mgr.maybe_sweep(min_interval_seconds=0) >= 0


# ---------------------------------------------------------------------------
# Shared singleton
# ---------------------------------------------------------------------------

def test_get_shared_temp_manager_is_singleton():
    a = get_shared_temp_manager()
    b = get_shared_temp_manager()
    assert a is b


def test_base_downloader_uses_shared_manager():
    """downloaders/base.py 与 utils 共享同一个 TempFileManager 实例。"""
    from src.video_transcript_api.downloaders import base as base_mod
    assert base_mod.get_temp_manager() is get_shared_temp_manager()
