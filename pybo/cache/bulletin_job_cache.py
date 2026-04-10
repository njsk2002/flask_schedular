from __future__ import annotations

import threading
import time
from typing import Any, Dict, List


class BulletinJobCache:
    _lock = threading.RLock()
    _active_jobs: List[Dict[str, Any]] = []
    _active_jobs_expire_at = 0.0

    _tick_marks: Dict[str, float] = {}

    @classmethod
    def get_active_jobs(cls) -> List[Dict[str, Any]]:
        with cls._lock:
            if time.time() >= cls._active_jobs_expire_at:
                return []
            return list(cls._active_jobs)

    @classmethod
    def set_active_jobs(cls, rows: List[Dict[str, Any]], ttl_seconds: int = 30) -> None:
        with cls._lock:
            cls._active_jobs = list(rows or [])
            cls._active_jobs_expire_at = time.time() + max(1, int(ttl_seconds))

    @classmethod
    def should_skip_minutely(cls, key: str, hold_seconds: int = 55) -> bool:
        now = time.time()
        with cls._lock:
            expire_at = cls._tick_marks.get(str(key), 0.0)
            if now < expire_at:
                return True
            cls._tick_marks[str(key)] = now + max(1, int(hold_seconds))
            return False
