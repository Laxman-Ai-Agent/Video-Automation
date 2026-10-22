"""Store Lock for Capability Finder Knowledge.

Provides thread-safe and process-safe mutual exclusion for knowledge store
operations (promotions, rollbacks, reads, baseline initialization).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, Optional

try:
    from filelock import FileLock, Timeout
except ImportError:
    FileLock = None  # type: ignore[assignment, misc]
    Timeout = TimeoutError  # type: ignore[assignment, misc]


class StoreLock:
    """Combines an in-process threading.RLock with an inter-process filelock.FileLock.

    Guarantees:
    1. Single-writer mutual exclusion within the same Python process via threading.RLock.
    2. Single-writer mutual exclusion across separate processes via filelock.FileLock.
    3. Thread reentrancy for nested operations (e.g. promote calling load_active_knowledge).
    4. Canonical singleton per canonical lockfile path via StoreLock.get().
    """

    _instances: Dict[str, StoreLock] = {}
    _registry_lock = threading.Lock()

    def __init__(self, lock_file_path: Path, timeout: float = 15.0) -> None:
        self.lock_file_path = lock_file_path.resolve()
        self.timeout = timeout
        self._thread_lock = threading.RLock()
        self._file_lock: Optional[FileLock] = (
            FileLock(str(self.lock_file_path), timeout=timeout)
            if FileLock is not None
            else None
        )

    @classmethod
    def get(cls, lock_file_path: Path, timeout: float = 15.0) -> StoreLock:
        """Retrieves or creates the canonical StoreLock for a given lockfile path."""
        norm_path = str(lock_file_path.resolve())
        with cls._registry_lock:
            if norm_path not in cls._instances:
                cls._instances[norm_path] = cls(lock_file_path, timeout=timeout)
            return cls._instances[norm_path]

    @classmethod
    def reset_registry_for_tests(cls) -> None:
        """Testing utility to clear singleton registry."""
        with cls._registry_lock:
            cls._instances.clear()

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquires in-process lock and then inter-process file lock."""
        t = timeout if timeout is not None else self.timeout
        self._thread_lock.acquire()
        if self._file_lock is not None:
            try:
                self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
                self._file_lock.acquire(timeout=t)
            except Exception:
                self._thread_lock.release()
                raise
        return True

    def release(self) -> None:
        """Releases inter-process file lock and then in-process lock."""
        try:
            if self._file_lock is not None and self._file_lock.is_locked:
                self._file_lock.release()
        finally:
            self._thread_lock.release()

    def __enter__(self) -> StoreLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
