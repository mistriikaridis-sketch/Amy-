"""Deploy busy lock: each in-flight transcription task holds a shared flock.

The deploy script takes an exclusive flock on the same bind-mounted file.
This module only does non-blocking shared admission against an EXISTING
lock file on Linux: the service never creates the lock file or its directory.

Windows note: ``fcntl`` is unavailable. Local uvicorn / Path A admits tasks
without flock (marker fd only). Docker/Linux keeps the original fail-closed
flock contract.
"""
from __future__ import annotations

import errno
import os
import threading
from typing import Optional

from .logging import setup_logger

logger = setup_logger("busy_lock")

try:
    import fcntl as _fcntl  # type: ignore
except ImportError:  # Windows
    _fcntl = None

# Linux deploy default; Windows local TEMP; override with VTA_BUSY_LOCK_PATH.
if os.environ.get("VTA_BUSY_LOCK_PATH"):
    BUSY_LOCK_PATH = os.environ["VTA_BUSY_LOCK_PATH"]
elif os.name == "nt":
    BUSY_LOCK_PATH = os.path.join(os.environ.get("TEMP", "."), "vta-busy.lock")
else:
    BUSY_LOCK_PATH = "/app/.deploy-state/busy.lock"


class BusyLock:
    """One shared flock fd covering a single task lifetime."""

    _warned_paths: set[str] = set()

    def __init__(self, path: str = BUSY_LOCK_PATH):
        self.path = path
        self._fd: Optional[int] = None
        self._disabled = False

    @property
    def disabled(self) -> bool:
        return self._disabled

    def _warn(self, message: str) -> None:
        if self.path in self._warned_paths:
            return
        self._warned_paths.add(self.path)
        logger.warning("BUSY LOCK WARN: " + message)

    @staticmethod
    def _os_error_reason(exc: OSError) -> str:
        if exc.errno in (errno.EACCES, errno.EPERM):
            return "permission denied"
        return "deploy-state mount/filesystem problem"

    def acquire(self) -> bool:
        if self._disabled:
            return False

        # Windows local: no fcntl — allow admission for Path A / local uvicorn.
        if _fcntl is None:
            try:
                parent = os.path.dirname(self.path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
                self._fd = fd
                return True
            except OSError as exc:
                self._warn(f"windows busy-lock open failed ({exc}); allowing anyway")
                self._fd = None
                return True

        try:
            fd = os.open(self.path, os.O_RDONLY)
            if not os.path.isfile(self.path):
                os.close(fd)
                self._disabled = True
                self._warn(
                    f"busy lock path {self.path} is not a regular file "
                    "(deploy-state mount misconfigured); "
                    "admission now denies new tasks until the mount is fixed"
                )
                return False
        except OSError as exc:
            self._disabled = True
            if exc.errno == errno.ENOENT:
                self._warn(
                    f"lock file missing — deployment mount likely broken: "
                    f"{self.path} ({exc}); "
                    "admission now denies new tasks until the mount is fixed"
                )
            else:
                self._warn(
                    f"cannot initialize {self.path} "
                    f"({self._os_error_reason(exc)}: {exc}); "
                    "admission now denies new tasks until it is fixed"
                )
            return False

        try:
            try:
                _fcntl.flock(fd, _fcntl.LOCK_SH | _fcntl.LOCK_NB)
                self._fd = fd
                return not self._disabled
            except BlockingIOError:
                os.close(fd)
                return False
            except OSError as exc:
                self._disabled = True
                self._warn(
                    f"cannot acquire {self.path} "
                    f"({self._os_error_reason(exc)}: {exc}); "
                    "admission now denies new tasks until it is fixed"
                )
                os.close(fd)
                return False
        except BaseException:
            os.close(fd)
            raise

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if _fcntl is not None:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
        finally:
            os.close(fd)


_held_locks: dict[str, BusyLock] = {}
_held_locks_guard = threading.Lock()


def acquire_for_task(task_id: str, path: str | None = None) -> bool:
    """Open a dedicated fd and hold shared flock until release_for_task."""
    lock = BusyLock(path or BUSY_LOCK_PATH)
    if not lock.acquire():
        return False
    with _held_locks_guard:
        previous = _held_locks.pop(task_id, None)
        _held_locks[task_id] = lock
    if previous is not None:
        previous.release()
    return not lock.disabled


def release_for_task(task_id: str) -> None:
    """Close the fd held for task_id. Unknown ids are a no-op."""
    with _held_locks_guard:
        lock = _held_locks.pop(task_id, None)
    if lock is not None:
        lock.release()
