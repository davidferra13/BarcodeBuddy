from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TextIO

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


class ServiceLockError(RuntimeError):
    """Raised when the workflow service lock cannot be acquired."""


class ServiceLock:
    def __init__(self, lock_file: Path, *, metadata: dict[str, Any]) -> None:
        self.lock_file = lock_file
        self.metadata = metadata
        self._handle: TextIO | None = None

    def acquire(self) -> "ServiceLock":
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_file.open("a+", encoding="utf-8")
        try:
            _lock_handle(handle)
        except OSError as exc:
            handle.close()
            raise ServiceLockError(
                f"Another Barcode Buddy instance already holds the workflow lock: {self.lock_file}"
            ) from exc

        try:
            handle.seek(0)
            handle.truncate()
            json.dump(self.metadata, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            try:
                _unlock_handle(handle)
            finally:
                handle.close()
            raise

        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is None:
            return

        try:
            _unlock_handle(self._handle)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "ServiceLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.release()


def _lock_handle(handle: TextIO) -> None:
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return

    raise OSError("No workflow lock implementation is available.")


def _unlock_handle(handle: TextIO) -> None:
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return
