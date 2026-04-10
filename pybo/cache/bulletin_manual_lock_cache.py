from __future__ import annotations

import threading
import time
from typing import Dict


class BulletinManualLockCache:
    _lock = threading.RLock()
    _locks: Dict[str, bool] = {}
    _expire_at = 0.0

    @classmethod
    def get_lock_map(cls) -> Dict[str, bool]:
        with cls._lock:
            if time.time() >= cls._expire_at:
                return {}
            return dict(cls._locks)

    @classmethod
    def set_lock_map(cls, lock_map: Dict[str, bool], ttl_seconds: int = 20) -> None:
        with cls._lock:
            cls._locks = {str(k): bool(v) for k, v in (lock_map or {}).items()}
            cls._expire_at = time.time() + max(1, int(ttl_seconds))

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._locks = {}
            cls._expire_at = 0.0
